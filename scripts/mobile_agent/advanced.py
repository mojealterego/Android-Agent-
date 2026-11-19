"""Owner-invoked semantic retrieval, preview-bound creation and cooperative inference leases."""
import argparse
from contextlib import contextmanager, nullcontext
import fcntl
import hashlib
import hmac
import http.client
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import sys

from .inference import LocalModel, ModelError, strict_json
from .recovery import ResourceGuard, RecoveryError, thermal_reader


class AdvancedError(Exception):
    """Sanitized validation, transport or local operation failure."""


MAX_INPUT = 256 * 1024
MAX_EMBEDDING_RESPONSE = 8 * 1024 * 1024


def _vectors(values, count):
    if not isinstance(values, list) or len(values) != count:
        raise AdvancedError('Embedding count mismatch')
    dimension = None
    normalized = []
    for vector in values:
        if not isinstance(vector, list) or not 1 <= len(vector) <= 4096:
            raise AdvancedError('Invalid embedding dimension')
        if dimension is None:
            dimension = len(vector)
        if len(vector) != dimension or any(type(x) not in (int, float) or abs(x) > 1e12 or not math.isfinite(x) for x in vector):
            raise AdvancedError('Invalid embedding values')
        norm = math.hypot(*vector)
        if not norm:
            raise AdvancedError('Zero embedding')
        normalized.append([x/norm for x in vector])
    return normalized


class EmbeddingClient:
    """Explicit local embedding model, OpenAI-compatible, no redirect or external host."""
    def __init__(self, *, port=8083, model='local', token='', timeout=60):
        self.config = LocalModel(port=port, model=model, token=token, timeout=timeout)

    def embed(self, texts):
        if not isinstance(texts, list) or not 1 <= len(texts) <= 33 or any(not isinstance(t,str) or not 0<len(t)<=4096 for t in texts):
            raise AdvancedError('Embedding input out of bounds')
        payload=json.dumps({'model':self.config.model,'input':texts,'encoding_format':'float'},ensure_ascii=False).encode('utf-8')
        if len(payload)>MAX_INPUT: raise AdvancedError('Embedding request too large')
        headers={'Content-Type':'application/json','Accept':'application/json','Connection':'close'}
        if self.config.token: headers['Authorization']='Bearer '+self.config.token
        connection=http.client.HTTPConnection('127.0.0.1',self.config.port,timeout=self.config.timeout)
        try:
            connection.request('POST','/v1/embeddings',body=payload,headers=headers)
            response=connection.getresponse()
            if response.status!=200 or response.getheader('Content-Type','').split(';',1)[0].strip().lower()!='application/json':
                raise AdvancedError('Embedding HTTP failure')
            raw=response.read(MAX_EMBEDDING_RESPONSE+1)
            if len(raw)>MAX_EMBEDDING_RESPONSE: raise AdvancedError('Embedding response too large')
            reply=strict_json(raw)
            data=reply.get('data') if isinstance(reply,dict) else None
            if not isinstance(data,list) or len(data)!=len(texts): raise AdvancedError('Invalid embedding envelope')
            ordered={}
            for entry in data:
                if not isinstance(entry,dict) or type(entry.get('index')) is not int or not 0<=entry['index']<len(texts) or entry['index'] in ordered:
                    raise AdvancedError('Invalid embedding index')
                ordered[entry['index']]=entry.get('embedding')
            vectors=[ordered[i] for i in range(len(texts))]
            _vectors(vectors,len(texts))
            return vectors
        except (OSError,http.client.HTTPException,ValueError,RecursionError,OverflowError):
            raise AdvancedError('Embedding transport or decoding failure') from None
        finally:
            connection.close()


def semantic_search(query, documents, embed, *, limit=5):
    if not isinstance(query,str) or not 0<len(query.strip())<=4096 or len(query)>4096 or type(limit) is not int or not 1<=limit<=32 or not isinstance(documents,list) or not 1<=len(documents)<=32:
        raise AdvancedError('Invalid semantic query or limit')
    ids=set(); texts=[query]
    for d in documents:
        if not isinstance(d,dict) or set(d)!={'id','text'} or not isinstance(d['id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',d['id']) or d['id'] in ids or not isinstance(d['text'],str) or not 0<len(d['text'])<=4096:
            raise AdvancedError('Invalid or duplicate document')
        ids.add(d['id']); texts.append(d['text'])
    if sum(len(t.encode('utf-8')) for t in texts)>MAX_INPUT: raise AdvancedError('Document budget exceeded')
    vectors=_vectors(embed(texts),len(texts)); q=vectors[0]
    ranked=[{'id':d['id'],'score':max(-1.0,min(1.0,math.fsum(a*b for a,b in zip(q,v)))),'text':d['text']} for d,v in zip(documents,vectors[1:])]
    return sorted(ranked,key=lambda x:(-x['score'],x['id']))[:limit]


@contextmanager
def _private_root(root):
    fd=None
    try:
        fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        s=os.fstat(fd)
        if s.st_uid!=os.getuid() or s.st_mode & 0o077:
            raise AdvancedError('Use an existing owner-only directory (0700)')
        yield fd,s
    except OSError:
        raise AdvancedError('Private directory operation failed') from None
    finally:
        if fd is not None: os.close(fd)


def _plan(s,name,text):
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\.txt',name) or not isinstance(text,str):
        raise AdvancedError('Only a named new text file is supported')
    try: content=text.encode('utf-8')
    except UnicodeError: raise AdvancedError('Invalid text encoding') from None
    if not 0<len(content)<=65536 or '\0' in text: raise AdvancedError('Invalid text size or content')
    plan={'contract':'omega.create-text/1','operation':'create_new_text','directory_device':s.st_dev,'directory_inode':s.st_ino,'name':name,'bytes':len(content),'content_sha256':hashlib.sha256(content).hexdigest()}
    approval=hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode('ascii')).hexdigest()
    return dict(plan,approval=approval),content


def preview_create(root,name,text):
    with _private_root(root) as (fd,s):
        plan,_=_plan(s,name,text)
        try: os.stat(name,dir_fd=fd,follow_symlinks=False)
        except FileNotFoundError: return plan
        raise AdvancedError('Destination already exists')


def apply_create(root,name,text,approval):
    """Publish an fsynced file atomically, never replacing an existing path."""
    with _private_root(root) as (fd,s):
        plan,content=_plan(s,name,text)
        if not isinstance(approval,str) or not re.fullmatch(r'[0-9a-f]{64}',approval) or not hmac.compare_digest(approval,plan['approval']):
            raise AdvancedError('Explicit approval does not match exact plan')
        tmp='.omega-'+secrets.token_hex(16); created=False; published=False
        try:
            out=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=fd)
            created=True
            with os.fdopen(out,'wb') as stream:
                stream.write(content); stream.flush(); os.fsync(stream.fileno())
            os.link(tmp,name,src_dir_fd=fd,dst_dir_fd=fd,follow_symlinks=False); published=True
            os.unlink(tmp,dir_fd=fd); created=False
            os.fsync(fd)
        except OSError:
            if published: raise AdvancedError('File published; durability uncertain; inspect destination before retry') from None
            raise AdvancedError('Creation failed; existing destination not replaced') from None
        finally:
            if created:
                try: os.unlink(tmp,dir_fd=fd)
                except OSError: pass
        return dict(plan,status='created')


class ResourceLease:
    """Cooperative one-inference-at-a-time lock; not a GPU/NPU reservation."""
    def __init__(self,root): self.root=root; self.fd=None
    def __enter__(self):
        if self.fd is not None: raise AdvancedError('Lease already acquired')
        with _private_root(self.root) as (directory,_):
            try:
                self.fd=os.open('inference.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,0o600,dir_fd=directory)
                s=os.fstat(self.fd)
                if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or s.st_mode&0o077 or s.st_nlink!=1:
                    raise AdvancedError('Unsafe inference lock')
                fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except (OSError,AdvancedError):
                self.__exit__(); raise AdvancedError('Inference lease unavailable or insecure') from None
        return self
    def __exit__(self,*_):
        if self.fd is not None: os.close(self.fd); self.fd=None


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    search=sub.add_parser('search'); search.add_argument('--port',type=int,default=8083); search.add_argument('--model',default='local'); search.add_argument('--limit',type=int,default=5); search.add_argument('--lease-dir',type=Path,required=True); search.add_argument('--min-memory-mib',type=int,default=1024); search.add_argument('--thermal-sensor',type=Path); search.add_argument('--max-temperature',type=float,default=43.0)
    for command in ('preview','apply'):
        s=sub.add_parser(command); s.add_argument('--root',required=True,type=Path)
        if command=='apply': s.add_argument('--approve',required=True)
    args=p.parse_args(argv)
    try:
        raw=sys.stdin.buffer.read(MAX_INPUT+1)
        if len(raw)>MAX_INPUT: raise AdvancedError('Input exceeds size limit')
        data=strict_json(raw)
        if args.command=='search':
            if not isinstance(data,dict) or set(data)!={'query','documents'}: raise AdvancedError('Invalid search envelope')
            guard=ResourceGuard(min_memory_mib=args.min_memory_mib,max_temperature=args.max_temperature if args.thermal_sensor else None,temperature_reader=thermal_reader(args.thermal_sensor) if args.thermal_sensor else None)
            client=EmbeddingClient(port=args.port,model=args.model,token=os.environ.get('OMEGA_EMBEDDING_TOKEN',''))
            with ResourceLease(args.lease_dir):
                guard.check(); result={'contract':'omega.semantic/1','untrusted_document_data':True,'matches':semantic_search(data['query'],data['documents'],client.embed,limit=args.limit)}
        else:
            if not isinstance(data,dict) or set(data)!={'name','text'}: raise AdvancedError('Invalid creation envelope')
            result=preview_create(args.root,**data) if args.command=='preview' else apply_create(args.root,**data,approval=args.approve)
        print(json.dumps(result,ensure_ascii=True,allow_nan=False)); return 0
    except (AdvancedError,RecoveryError,ModelError,OSError,ValueError,RecursionError,OverflowError):
        print('Advanced operation rejected or failed; inspect destination before any retry',file=sys.stderr); return 1
    except KeyboardInterrupt:
        return 130


if __name__=='__main__': sys.exit(main())
