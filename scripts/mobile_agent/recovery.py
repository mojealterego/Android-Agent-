"""Opt-in, owner-local checkpoints and fail-closed resource admission (POSIX)."""
from contextlib import suppress
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import time


class RecoveryError(Exception):
    """Sanitized checkpoint or admission error."""


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class CheckpointStore:
    """Single operator per private database; only validated role outputs are persisted."""
    def __init__(self, root, job, config, *, ttl=86400):
        if not isinstance(job, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', job):
            raise RecoveryError('Invalid checkpoint job identifier')
        if type(ttl) is not int or not 60 <= ttl <= 604800:
            raise RecoveryError('Invalid checkpoint lifetime')
        self.root, self.job, self.config, self.ttl = Path(root), job, config, ttl
        self.lock = self.db = None
        self.bound = False

    @staticmethod
    def _private_file(path):
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        s = os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o077 or s.st_nlink != 1:
            os.close(fd)
            raise RecoveryError('Checkpoint file must be owner-only and regular')
        return fd

    def __enter__(self):
        try:
            self.root.mkdir(mode=0o700, exist_ok=True)
            s = self.root.lstat()
            if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o077:
                raise RecoveryError('Checkpoint directory must be private (0700)')
            self.lock = self._private_file(self.root / 'checkpoint.lock')
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            path = self.root / 'checkpoints.sqlite3'
            # SQLite rollback files must not be attacker-supplied links.
            for suffix in ('-journal', '-wal', '-shm'):
                side = Path(str(path)+suffix)
                if side.exists() or side.is_symlink():
                    os.close(self._private_file(side))
            os.close(self._private_file(path))
            self.db = sqlite3.connect(path, timeout=1)
            self.db.execute('PRAGMA journal_mode=DELETE')
            self.db.execute('PRAGMA synchronous=FULL')
            self.db.execute('PRAGMA secure_delete=ON')
            self.db.execute('PRAGMA max_page_count=4096')
            with self.db:
                self.db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, updated INTEGER NOT NULL, stages TEXT NOT NULL)')
                self.db.execute('DELETE FROM jobs WHERE updated < ?', (int(time.time())-self.ttl,))
            return self
        except (OSError, sqlite3.Error, RecoveryError):
            self.__exit__(None,None,None)
            raise RecoveryError('Checkpoint unavailable, insecure or already in use') from None

    def __exit__(self, *_):
        if self.db is not None:
            with suppress(sqlite3.Error): self.db.close()
            self.db = None
        if self.lock is not None:
            os.close(self.lock); self.lock = None
        self.bound = False

    def bind(self, question, notes):
        fingerprint = digest({'version':'omega.checkpoint/1','config':self.config,'question':question,'notes':list(notes)})
        try:
            with self.db:
                row = self.db.execute('SELECT fingerprint, stages FROM jobs WHERE id=?',(self.job,)).fetchone()
                if row is None:
                    if self.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0] >= 128:
                        raise RecoveryError('Checkpoint capacity exceeded')
                    self.db.execute('INSERT INTO jobs VALUES (?,?,?,?)',(self.job,fingerprint,int(time.time()),'{}'))
                    stages = {}
                else:
                    if row[0] != fingerprint: raise RecoveryError('Checkpoint input or configuration changed; use a new job ID')
                    stages = json.loads(row[1])
                    if not isinstance(stages,dict) or len(stages)>3: raise RecoveryError('Invalid checkpoint stages')
                self.bound = True
                return stages
        except (sqlite3.Error, ValueError, RecursionError):
            raise RecoveryError('Checkpoint could not be loaded') from None

    def save(self, stages):
        if not self.bound: raise RecoveryError('Checkpoint not bound')
        payload = json.dumps(stages,ensure_ascii=True,separators=(',',':'),allow_nan=False)
        if len(payload)>80000: raise RecoveryError('Checkpoint stage budget exceeded')
        try:
            with self.db:
                self.db.execute('UPDATE jobs SET stages=?, updated=? WHERE id=?',(payload,int(time.time()),self.job))
        except sqlite3.Error:
            raise RecoveryError('Checkpoint could not be saved') from None

    def purge(self):
        try:
            with self.db: self.db.execute('DELETE FROM jobs WHERE id=?',(self.job,))
            self.bound = False
        except sqlite3.Error: raise RecoveryError('Checkpoint could not be deleted') from None


def available_memory_mib():
    with open('/proc/meminfo',encoding='ascii') as stream:
        for line in stream:
            if line.startswith('MemAvailable:'):
                return int(line.split()[1])/1024
    raise RecoveryError('Available memory sensor missing')


def thermal_reader(path):
    def read():
        with open(path,encoding='ascii') as stream: return int(stream.read(64).strip())/1000
    return read


class ResourceGuard:
    def __init__(self, *, min_memory_mib=1024, max_temperature=None, memory_reader=available_memory_mib, temperature_reader=None):
        if type(min_memory_mib) is not int or not 1 <= min_memory_mib <= 65536:
            raise RecoveryError('Invalid memory threshold')
        if max_temperature is not None and (type(max_temperature) not in (float,int) or not 20 <= max_temperature <= 100 or temperature_reader is None):
            raise RecoveryError('Invalid thermal threshold or missing sensor')
        self.min_memory_mib, self.max_temperature = min_memory_mib, max_temperature
        self.memory_reader, self.temperature_reader = memory_reader, temperature_reader

    def check(self):
        try:
            memory = self.memory_reader()
            if type(memory) not in (int,float) or not math.isfinite(memory) or memory < self.min_memory_mib:
                raise RecoveryError('Insufficient or unavailable memory; inference not started')
            if self.max_temperature is not None:
                temp = self.temperature_reader()
                if type(temp) not in (int,float) or not math.isfinite(temp) or not -20 <= temp < self.max_temperature:
                    raise RecoveryError('Thermal threshold exceeded or sensor unavailable; inference not started')
        except (OSError, ValueError, TypeError, OverflowError):
            raise RecoveryError('Resource sensor unavailable; inference not started') from None
