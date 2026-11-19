#!/usr/bin/env python3
"""Download or import pinned public build inputs into a private cache. Never execute/build."""
import argparse
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
from urllib.parse import urlsplit

class IntakeFailure(Exception): pass

@dataclass(frozen=True)
class Artifact:
    name: str
    url: str
    sha256: str
    max_bytes: int
    def __post_init__(self):
        u=urlsplit(self.url)
        if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,199}',self.name) or
            u.scheme!='https' or not u.hostname or u.username is not None or u.password is not None or u.fragment or u.query or
            not re.fullmatch(r'[0-9a-f]{64}',self.sha256) or type(self.max_bytes) is not int or not 1<=self.max_bytes<=2**31):
            raise IntakeFailure('Invalid dependency lock entry')

ARTIFACTS={
 'gradle':Artifact('gradle-9.7.1-bin.zip','https://services.gradle.org/distributions/gradle-9.7.1-bin.zip','acd53f1edaf02f1a8ff99879f8a34b302661a057d9b063ae9e35b552f804d20a',512*1024**2),
 'sdk-tools':Artifact('commandlinetools-linux-15859902_latest.zip','https://dl.google.com/android/repository/commandlinetools-linux-15859902_latest.zip','4e4c464f145a7512b57d088ac6c278c03c9eea610886b35a5e0804e74eedf583',512*1024**2),
 'go-linux-amd64':Artifact('go1.27.4.linux-amd64.tar.gz','https://go.dev/dl/go1.27.4.linux-amd64.tar.gz','7226736c2339719cda28fbf3a54d71aa63bcefe376e98cef00034268dab24840',256*1024**2),
 'go-linux-arm64':Artifact('go1.27.4.linux-arm64.tar.gz','https://go.dev/dl/go1.27.4.linux-arm64.tar.gz','3392582988a273a87ab5043ee1b2c9c17a2c3c00580bf9326c47a2e0aaaeac92',256*1024**2),
}
WRAPPER_JAR='7d3a4ac4de1c32b59bc6a4eb8ecb8e612ccd0cf1ae1e99f66902da64df296172'


def _digest(path,maximum):
    fd=None
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0<before.st_size<=maximum: raise IntakeFailure('Invalid artifact size or type')
        sha=hashlib.sha256(); length=0
        with os.fdopen(fd,'rb') as src:
            fd=None
            while chunk:=src.read(1024**2):
                length+=len(chunk)
                if length>maximum: raise IntakeFailure('Artifact too large')
                sha.update(chunk)
            after=os.fstat(src.fileno())
        if (length!=before.st_size or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)):
            raise IntakeFailure('Artifact changed during verification')
        return sha.hexdigest()
    except OSError: raise IntakeFailure('Artifact unavailable') from None
    finally:
        if fd is not None: os.close(fd)


def verify(artifact,path):
    try: return hmac.compare_digest(_digest(path,artifact.max_bytes),artifact.sha256)
    except IntakeFailure: return False


def wrapper_integrity(root):
    try:
        props=(Path(root)/'gradle/wrapper/gradle-wrapper.properties').read_text()
        expected='distributionUrl='+ARTIFACTS['gradle'].url.replace(':',r'\:')
        fields=['distributionBase=GRADLE_USER_HOME','distributionPath=wrapper/dists',expected,'distributionSha256Sum='+ARTIFACTS['gradle'].sha256,'networkTimeout=10000','validateDistributionUrl=true','zipStoreBase=GRADLE_USER_HOME','zipStorePath=wrapper/dists']
        return props.splitlines()==fields and hmac.compare_digest(_digest(Path(root)/'gradle/wrapper/gradle-wrapper.jar',1024**2),WRAPPER_JAR)
    except (OSError,IntakeFailure): return False


def _cache(cache):
    p=Path(cache).absolute()
    try: s=p.lstat()
    except OSError: raise IntakeFailure('Existing private cache directory required') from None
    if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.getuid() or s.st_mode&0o077: raise IntakeFailure('Private cache directory required')
    return p


def _existing(a,p):
    if p.exists() or p.is_symlink():
        if not verify(a,p): raise IntakeFailure('Existing artifact invalid; inspect manually')
        return p
    return None


def _stage(a,cache,produce):
    cache=_cache(cache); target=cache/a.name
    if _existing(a,target): return target
    tmp=cache/('.omega-download-'+secrets.token_hex(16))
    created=False
    try:
        fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600); created=True; os.close(fd)
        produce(a,tmp)
        if not verify(a,tmp): raise IntakeFailure('Artifact SHA-256 mismatch')
        with tmp.open('rb') as f: os.fsync(f.fileno())
        try: os.link(tmp,target,follow_symlinks=False)
        except FileExistsError:
            if not _existing(a,target): raise IntakeFailure('Cache collision')
        d=os.open(cache,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try: os.fsync(d)
        finally: os.close(d)
        return target
    except OSError: raise IntakeFailure('Cache write failed; inspect target before retry') from None
    finally:
        if created: tmp.unlink(missing_ok=True)


def store(a,source,cache):
    def copy(a,tmp):
        fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        with os.fdopen(fd,'rb') as src,tmp.open('wb') as dst:
            s=os.fstat(src.fileno())
            if not stat.S_ISREG(s.st_mode) or not 0<s.st_size<=a.max_bytes: raise IntakeFailure('Invalid source type or size')
            length=0
            while chunk:=src.read(1024**2):
                length+=len(chunk)
                if length>a.max_bytes: raise IntakeFailure('Artifact too large')
                dst.write(chunk)
    return _stage(a,cache,copy)


def _download(a,tmp):
    # curl config disabled; only HTTPS permitted through redirects. No credentials passed.
    try:
        result=subprocess.run(['curl','-q','--fail','--silent','--show-error','--location','--max-redirs','4','--proto','=https','--proto-redir','=https','--connect-timeout','10','--max-time','600','--max-filesize',str(a.max_bytes),'--output',str(tmp),'--',a.url],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=610)
    except (OSError,subprocess.TimeoutExpired): raise IntakeFailure('Dependency download unavailable') from None
    if result.returncode!=0: raise IntakeFailure(f'Dependency download failed (curl exit {result.returncode})')


def fetch(a,cache,*,download=_download): return _stage(a,cache,download)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='action',required=True); sub.add_parser('list')
    for action in ('fetch','import','verify'):
        q=sub.add_parser(action); q.add_argument('artifact',choices=ARTIFACTS); q.add_argument('--cache',type=Path,required=True)
        if action=='import': q.add_argument('source',type=Path)
    args=p.parse_args(argv)
    try:
        if args.action=='list': result={'artifacts':{k:vars(v) for k,v in ARTIFACTS.items()},'apk_build_invoked':False}
        else:
            a=ARTIFACTS[args.artifact]
            if args.action=='verify':
                path=_cache(args.cache)/a.name
                if not verify(a,path): raise IntakeFailure('Artifact missing or invalid')
            else: path=fetch(a,args.cache) if args.action=='fetch' else store(a,args.source,args.cache)
            result={'artifact':args.artifact,'path':str(path),'sha256':a.sha256,'status':'verified_cache_only','installed':False,'apk_build_invoked':False}
        print(json.dumps(result,indent=2)); return 0
    except (IntakeFailure,OSError) as e: print(str(e) if isinstance(e,IntakeFailure) else 'Dependency operation failed',file=sys.stderr); return 1
    except KeyboardInterrupt: return 130

if __name__=='__main__': sys.exit(main())
