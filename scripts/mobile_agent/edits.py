"""Owner-approved reversible text replacement, with durable one-use plans and reconciliation."""
import argparse
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import sys
import time
from .private_store import PrivateStore, StoreError
from .inference import strict_json

MAX_BYTES=65536
MAX_PLANS=128
TTL=300
class EditError(StoreError): pass

def _sha(raw): return hashlib.sha256(raw).hexdigest()
def _name(name):
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\.(txt|md|csv|json|log)',name): raise EditError('Only explicit text basenames allowed')
    return name

def _text(text):
    if not isinstance(text,str) or '\0' in text: raise EditError('Invalid text')
    try: raw=text.encode('utf-8')
    except UnicodeError: raise EditError('Invalid UTF-8') from None
    if len(raw)>MAX_BYTES: raise EditError('Text size exceeded')
    return raw

class EditStore(PrivateStore):
    name='edits'; error=EditError
    def __init__(self,root,state,*,clock=time.time):
        super().__init__(state); self.root=Path(root); self.rootfd=None; self.rootlock=None; self.clock=clock

    def __enter__(self):
        try:
            self.rootfd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            s=os.fstat(self.rootfd)
            if s.st_uid!=os.getuid() or s.st_mode&0o077: raise EditError('Private root required')
            if (s.st_dev,s.st_ino)==(self.state.stat().st_dev,self.state.stat().st_ino): raise EditError('Separate state directory required')
            self.rootlock=os.open(".omega-edit.lock",os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,0o600,dir_fd=self.rootfd)
            lockstat=os.fstat(self.rootlock)
            if not stat.S_ISREG(lockstat.st_mode) or lockstat.st_uid!=os.getuid() or lockstat.st_mode&0o077 or lockstat.st_nlink!=1: raise EditError("Unsafe root lock")
            fcntl.flock(self.rootlock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            return super().__enter__()
        except (OSError,StoreError): self.__exit__(); raise EditError('Edit store unavailable') from None

    def __exit__(self,*_):
        super().__exit__()
        if self.rootlock is not None: os.close(self.rootlock); self.rootlock=None
        if self.rootfd is not None: os.close(self.rootfd); self.rootfd=None

    def initialize(self):
        with self.db:
            self.db.execute('CREATE TABLE IF NOT EXISTS plans (id TEXT PRIMARY KEY, envelope TEXT NOT NULL, before BLOB NOT NULL, after BLOB NOT NULL, status TEXT NOT NULL, observed TEXT)')

    def _root_identity(self):
        s=os.fstat(self.rootfd); t=self.root.lstat()
        if not stat.S_ISDIR(t.st_mode) or (s.st_dev,s.st_ino)!=(t.st_dev,t.st_ino) or t.st_mode&0o077 or t.st_uid!=os.getuid(): raise EditError('Root changed')
        return [s.st_dev,s.st_ino]

    def _read(self,name):
        self._root_identity(); fd=None
        try:
            fd=os.open(_name(name),os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=self.rootfd); s=os.fstat(fd)
            if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or s.st_nlink!=1 or stat.S_IMODE(s.st_mode)!=0o600 or s.st_size>MAX_BYTES: raise EditError('Private bounded regular file required')
            with os.fdopen(fd,'rb') as f:
                fd=None; raw=f.read(MAX_BYTES+1); t=os.fstat(f.fileno())
            fingerprint=[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
            if fingerprint!=[t.st_dev,t.st_ino,t.st_size,t.st_mtime_ns,t.st_ctime_ns] or len(raw)!=s.st_size: raise EditError('File changed during read')
            _text(raw.decode('utf-8')); return raw,fingerprint
        except (OSError,UnicodeError): raise EditError('File unavailable or invalid') from None
        finally:
            if fd is not None: os.close(fd)

    def preview(self,name,text):
        after=_text(text); before,stamp=self._read(name)
        if before==after: raise EditError('No change')
        p={'contract':'omega.edit/1','id':secrets.token_hex(16),'name':name,'root':self._root_identity(),'stamp':stamp,'before_sha256':_sha(before),'after_sha256':_sha(after),'expires':int(self.clock())+TTL}
        envelope=json.dumps(p,sort_keys=True,separators=(',',':'))
        with self.db:
            if self.db.execute('SELECT COUNT(*) FROM plans').fetchone()[0]>=MAX_PLANS: raise EditError('Edit history full; manually purge completed records')
            self.db.execute('INSERT INTO plans VALUES (?,?,?,?,?,NULL)',(p['id'],envelope,before,after,'previewed'))
        return dict(p,approval=_sha(envelope.encode()),before_text=before.decode(),after_text=text)

    def _get(self,id):
        if not isinstance(id,str) or not re.fullmatch(r'[0-9a-f]{32}',id): raise EditError('Invalid plan ID')
        row=self.db.execute('SELECT envelope,before,after,status,observed FROM plans WHERE id=?',(id,)).fetchone()
        if row is None: raise EditError('Unknown plan')
        env,before,after,status,observed=row; p=strict_json(env)
        if p['id']!=id or p['root']!=self._root_identity() or p['before_sha256']!=_sha(before) or p['after_sha256']!=_sha(after): raise EditError('Plan integrity or root mismatch')
        _name(p['name']); return p,env,before,after,status,strict_json(observed) if observed is not None else None

    def _status(self,id,status,observed=None):
        with self.db: self.db.execute('UPDATE plans SET status=?,observed=? WHERE id=?',(status,json.dumps(observed) if observed is not None else None,id))
        return {'id':id,'status':status}

    def _replace(self,name,after,stamp,before):
        tmp='.omega-edit-'+secrets.token_hex(16); created=False
        try:
            fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.rootfd); created=True
            with os.fdopen(fd,'wb') as f: f.write(after); f.flush(); os.fsync(f.fileno())
            # All participating writers must respect the same lock; no atomic OS CAS for arbitrary writers.
            if self._read(name)!=(before,stamp): raise EditError('File changed before publication')
            os.replace(tmp,name,src_dir_fd=self.rootfd,dst_dir_fd=self.rootfd); created=False
            os.fsync(self.rootfd)
        finally:
            if created: os.unlink(tmp,dir_fd=self.rootfd)

    def apply(self,id,approval):
        p,env,before,after,status,_=self._get(id)
        if status!='previewed' or int(self.clock())>=p['expires'] or not isinstance(approval,str) or not re.fullmatch(r'[0-9a-f]{64}',approval) or not hmac.compare_digest(approval,_sha(env.encode())): raise EditError('Plan expired, consumed or approval mismatch')
        if self._read(p['name'])!=(before,p['stamp']): raise EditError('Stale plan')
        if self.db.execute("SELECT 1 FROM plans WHERE status='pending' LIMIT 1").fetchone(): raise EditError('Reconcile pending operation first')
        self._status(id,'pending')
        try:
            self._replace(p['name'],after,p['stamp'],before)
            actual,stamp=self._read(p['name'])
            if actual!=after: raise EditError('Publication not confirmed')
            return self._status(id,'applied',stamp)
        except (OSError,sqlite3.Error,EditError): raise EditError('Outcome uncertain; recover explicitly, never replay') from None

    def recover(self,id):
        p,_,before,after,status,observed=self._get(id)
        if status!='pending': raise EditError('Only pending plans can be reconciled')
        try: current,stamp=self._read(p['name'])
        except EditError: raise EditError('File unavailable; pending plan remains fenced') from None
        if current==after:
            try: os.fsync(self.rootfd)
            except OSError: raise EditError('Directory sync unavailable; pending plan remains fenced') from None
            return self._status(id,'applied',stamp)
        if current==before and stamp==p['stamp']: return self._status(id,'aborted')
        return self._status(id,'conflict')

    def preview_rollback(self,id):
        p,_,before,after,status,observed=self._get(id)
        if status!='applied' or self._read(p['name'])!=(after,observed): raise EditError('Rollback requires matching applied content')
        return self.preview(p['name'],before.decode('utf-8'))

    def history(self):
        return [{"id":id,"status":status} for id,status in self.db.execute("SELECT id,status FROM plans ORDER BY id LIMIT ?",(MAX_PLANS,))]

    def forget(self,id):
        _,_,_,_,status,_=self._get(id)
        if status=='pending': raise EditError('Reconcile before deleting history')
        with self.db: self.db.execute('DELETE FROM plans WHERE id=?',(id,))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',required=True); p.add_argument('--state',required=True)
    sub=p.add_subparsers(dest='command',required=True); a=sub.add_parser('preview'); a.add_argument('name')
    for cmd in ('apply','recover','rollback','forget'):
        a=sub.add_parser(cmd); a.add_argument('id')
        if cmd=='apply': a.add_argument('--approve',required=True)
    sub.add_parser('history'); args=p.parse_args(argv)
    try:
        with EditStore(args.root,args.state) as e:
            if args.command=='preview':
                raw=sys.stdin.buffer.read(262145)
                if len(raw)>262144: raise EditError('Input too large')
                result=e.preview(args.name,strict_json(raw))
            elif args.command=='apply': result=e.apply(args.id,args.approve)
            elif args.command=='recover': result=e.recover(args.id)
            elif args.command=='rollback': result=e.preview_rollback(args.id)
            elif args.command=='history': result={'plans':e.history()}
            else: e.forget(args.id); result={'forgotten':True}
        print(json.dumps(result,ensure_ascii=True)); return 0
    except (EditError,OSError,sqlite3.Error,ValueError,TypeError,KeyError,RecursionError):
        print('Edit denied or uncertain; inspect state before any new plan',file=sys.stderr); return 1
    except KeyboardInterrupt: return 130

if __name__=='__main__': sys.exit(main())
