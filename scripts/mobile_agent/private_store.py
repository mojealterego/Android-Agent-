"""Shared owner-private SQLite lifecycle; cooperative single-process access."""
import fcntl
import os
from pathlib import Path
import sqlite3
import stat
from contextlib import suppress

class StoreError(Exception):
    """Local store unavailable, denied, or inconsistent."""

class PrivateStore:
    name = None
    error = StoreError
    def __init__(self, state):
        self.state=Path(state); self.db=None; self.lock=None

    def _file(self, path):
        fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,0o600)
        s=os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or s.st_mode&0o077 or s.st_nlink!=1:
            os.close(fd); raise self.error('Owner-private regular state file required')
        return fd

    def __enter__(self):
        try:
            s=self.state.lstat()
            if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.getuid() or s.st_mode&0o077:
                raise self.error('Existing owner-private state directory required')
            self.lock=self._file(self.state/(self.name+'.lock'))
            fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            path=self.state/(self.name+'.sqlite3')
            for suffix in ('','-journal','-wal','-shm'):
                p=Path(str(path)+suffix)
                if not suffix or p.exists() or p.is_symlink(): os.close(self._file(p))
            self.db=sqlite3.connect(path,timeout=1)
            for pragma in ('journal_mode=DELETE','synchronous=FULL','secure_delete=ON','trusted_schema=OFF','foreign_keys=ON','max_page_count=8192'):
                self.db.execute('PRAGMA '+pragma)
            if self.db.execute('PRAGMA page_count').fetchone()[0]>8192: raise self.error('State capacity exceeded')
            self.initialize()
            return self
        except (OSError,sqlite3.Error,StoreError,ValueError,OverflowError):
            self.__exit__(); raise self.error('Private state unavailable, corrupt or busy') from None

    def __exit__(self,*_):
        if self.db is not None:
            with suppress(sqlite3.Error): self.db.close()
            self.db=None
        if self.lock is not None: os.close(self.lock); self.lock=None
