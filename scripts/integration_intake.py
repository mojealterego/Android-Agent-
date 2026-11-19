#!/usr/bin/env python3
"""Bounded, owner-invoked ZIP admission: inventory or quarantine staging, never integration/execution."""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import sys
import tempfile
import unicodedata
import zipfile
import zlib

MAX_ARCHIVE = 2 * 1024**3
MAX_EXPANDED = 4 * 1024**3
MAX_MEMBER = 1024**3
MAX_FILES = 50_000
MAX_CENTRAL = 32 * 1024**2
MAX_RATIO = 1000
CHUNK = 1024 * 1024

class IntakeError(Exception):
    """No admission on malformed, ambiguous or unbounded inputs."""


def _bound(value, maximum):
    if type(value) is not int or not 1 <= value <= maximum:
        raise IntakeError('Invalid admission limit')


def _stamp(fd):
    s = os.fstat(fd)
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def _hash(stream):
    stream.seek(0)
    digest = hashlib.sha256()
    while chunk := stream.read(CHUNK):
        digest.update(chunk)
    return digest.hexdigest()


def _end_record(stream, size, max_files):
    # Bound the central directory before ZipFile parses it into Python objects.
    length = min(size, 65557)
    stream.seek(size-length)
    tail = stream.read(length)
    pos = tail.rfind(b'PK\x05\x06')
    if pos < 0 or pos+22 > len(tail):
        raise IntakeError('Missing ZIP32 end record')
    _, disk, start_disk, disk_count, count, central_size, central_offset, comment = struct.unpack_from('<4s4H2LH', tail, pos)
    if (pos+22+comment != len(tail) or disk or start_disk or disk_count != count or not 1 <= count <= max_files
            or central_size in (0, 0xffffffff) or central_size > MAX_CENTRAL or central_offset == 0xffffffff
            or central_offset+central_size != size-length+pos):
        raise IntakeError('ZIP64, multi-volume, oversized or ambiguous directory rejected')
    return count, central_offset


def _name(info):
    original = info.orig_filename
    name = info.filename
    if (not isinstance(original,str) or original != name or not name or len(name.encode('utf-8')) > 1024 or '\\' in name
            or any(unicodedata.category(c) in ('Cc','Cf','Cs') for c in name) or unicodedata.normalize('NFC',name) != name):
        raise IntakeError('Invalid or ambiguous member name')
    directory = info.is_dir()
    parts = (name[:-1] if directory else name).split('/')
    if len(parts) > 32:
        raise IntakeError('Path depth exceeded')
    for p in parts:
        if (not p or p in ('.','..') or p.casefold() == '.git' or len(p.encode('utf-8')) > 255 or p[-1] in ' .' or any(c in p for c in ':<>"|?*')
                or re.fullmatch(r'(?i:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])',p.split('.')[0])):
            raise IntakeError('Unsafe member path')
    mode = (info.external_attr >> 16) & 0xffff
    kind = stat.S_IFMT(mode)
    if (kind not in (0, stat.S_IFREG, stat.S_IFDIR) or (kind == stat.S_IFDIR and not directory)
            or (kind == stat.S_IFREG and directory) or info.flag_bits & 1
            or info.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED)):
        raise IntakeError('Unsupported member type, encryption or compression')
    return parts, directory


def inspect_zip(path, *, expected_sha256=None, stage_root=None, max_files=MAX_FILES,
                max_expanded=MAX_EXPANDED, max_member=MAX_MEMBER, max_ratio=MAX_RATIO):
    """Validate every member and stream SHA-256; optional new private quarantine directory."""
    for value, bound in ((max_files,MAX_FILES),(max_expanded,MAX_EXPANDED),(max_member,MAX_MEMBER),(max_ratio,MAX_RATIO)):
        _bound(value,bound)
    if expected_sha256 is not None and (not isinstance(expected_sha256,str) or not re.fullmatch('[0-9a-f]{64}',expected_sha256)):
        raise IntakeError('Invalid expected archive digest')
    fd = None
    staged = None
    try:
        fd = os.open(path, os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or not 22 <= meta.st_size <= MAX_ARCHIVE:
            raise IntakeError('Archive must be bounded regular ZIP')
        if stage_root is not None:
            root = Path(stage_root).absolute()
            s = root.lstat()
            if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o077:
                raise IntakeError('Existing owner-private quarantine root required')
        with os.fdopen(fd,'rb') as stream:
            fd = None
            identity = _stamp(stream.fileno())
            count, central_offset = _end_record(stream,meta.st_size,max_files)
            sha = _hash(stream)
            if expected_sha256 is not None and not hmac.compare_digest(sha,expected_sha256):
                raise IntakeError('Archive digest mismatch')
            with zipfile.ZipFile(stream) as archive:
                infos = archive.infolist()
                if len(infos) != count:
                    raise IntakeError('Directory count mismatch')
                seen = set(); names = {}; files = set(); dirs = set(); entries = []; total = 0
                for info in infos:
                    parts,directory = _name(info)
                    pathstr = '/'.join(parts)
                    if pathstr in seen:
                        raise IntakeError('Duplicate member')
                    seen.add(pathstr)
                    for i in range(1,len(parts)+1):
                        prefix = '/'.join(parts[:i]); key = unicodedata.normalize('NFC',prefix.casefold())
                        if key in names and names[key] != prefix:
                            raise IntakeError('Ambiguous path casing')
                        names[key] = prefix
                        if i < len(parts): dirs.add(prefix)
                    if directory:
                        if info.file_size != 0: raise IntakeError('Nonempty directory member')
                        dirs.add(pathstr)
                    else:
                        files.add(pathstr)
                        entries.append((pathstr,info))
                        total += info.file_size
                    if (info.header_offset < 0 or info.header_offset >= central_offset or info.file_size < 0 or info.compress_size < 0
                            or info.file_size > max_member or total > max_expanded
                            or info.file_size > max(1,info.compress_size)*max_ratio):
                        raise IntakeError('Archive resource budget exceeded')
                if files & dirs or not files:
                    raise IntakeError('File/directory collision or empty archive')
                if stage_root is not None:
                    staged = Path(tempfile.mkdtemp(prefix='omega-quarantine-',dir=root))
                    for name in sorted(dirs, key=lambda x:(x.count('/'),x)):
                        (staged/name).mkdir(mode=0o700,parents=False,exist_ok=False)
                result = []
                # Read directories too: the local headers must agree with the directory inventory.
                for info in infos:
                    if info.is_dir():
                        with archive.open(info) as reader:
                            if reader.read(1): raise IntakeError('Nonempty directory stream')
                for name,info in sorted(entries):
                    digest = hashlib.sha256(); length = 0; sink = None
                    try:
                        if staged is not None:
                            sink = os.fdopen(os.open(staged/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600),'wb')
                        with archive.open(info) as reader:
                            while chunk := reader.read(CHUNK):
                                length += len(chunk)
                                if length > info.file_size or length > max_member:
                                    raise IntakeError('Member expansion exceeded declaration')
                                digest.update(chunk)
                                if sink is not None: sink.write(chunk)
                        if length != info.file_size:
                            raise IntakeError('Member size mismatch')
                        if sink is not None: sink.flush(); os.fsync(sink.fileno())
                    finally:
                        if sink is not None: sink.close()
                    result.append({'path':name,'bytes':length,'sha256':digest.hexdigest()})
            if _stamp(stream.fileno()) != identity or _hash(stream) != sha or _stamp(stream.fileno()) != identity:
                raise IntakeError('Archive changed during admission')
        report = {'contract':'omega.integration.intake/1','state':'staged_not_integrated' if staged is not None else 'validated_not_integrated',
                  'archive_sha256':sha,'file_count':len(result),'expanded_bytes':total,'files':result}
        if staged is not None: report['staged_directory'] = str(staged)
        staged = None
        return report
    except (OSError,ValueError,TypeError,UnicodeError,RuntimeError,NotImplementedError,zipfile.BadZipFile,struct.error,OverflowError,EOFError,zlib.error):
        raise IntakeError('Archive format, resource or quarantine admission rejected') from None
    finally:
        if fd is not None: os.close(fd)
        if staged is not None: shutil.rmtree(staged)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path); p.add_argument('--sha256'); p.add_argument('--stage-root',type=Path)
    a=p.parse_args(argv)
    try:
        print(json.dumps(inspect_zip(a.archive,expected_sha256=a.sha256,stage_root=a.stage_root),ensure_ascii=True,sort_keys=True,indent=2))
        return 0
    except IntakeError as e:
        print(str(e),file=sys.stderr); return 1
    except KeyboardInterrupt:
        return 130

if __name__=='__main__': sys.exit(main())
