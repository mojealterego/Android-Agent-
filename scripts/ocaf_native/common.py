"""Shared bounded primitives for OCAF native clients; no MCP dependency."""
import json
import os
from pathlib import Path
import re
import stat


class NativeError(Exception):
    """Fail-closed error without secret or remote payload disclosure."""


def segment(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value) is not None


def digest_hex(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def strict_decode(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError('duplicate field')
            result[k] = v
        return result
    def invalid(_):
        raise ValueError('invalid number')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)


def read_credential(path, *, private=False, max_bytes=1024*1024):
    """Absolute, regular, bounded file, no final symlink; trusted parent required."""
    fd = None
    try:
        p = Path(path)
        if not p.is_absolute() or '..' in p.parts:
            raise NativeError('Credential path must be absolute and normalized')
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= max_bytes or
                info.st_mode & 0o022 or (private and (info.st_mode & 0o077 or info.st_uid != os.getuid() or info.st_nlink != 1))):
            raise NativeError('Credential permissions or size rejected')
        with os.fdopen(fd, 'rb') as stream:
            fd = None
            raw = stream.read(max_bytes+1)
        if not 0 < len(raw) <= max_bytes:
            raise NativeError('Credential size rejected')
        return raw
    except (OSError, TypeError, ValueError):
        raise NativeError('Credential unavailable') from None
    finally:
        if fd is not None:
            os.close(fd)
