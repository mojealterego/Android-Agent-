"""Durable, opt-in local provenance DAG with cascading expiry/revocation."""
import argparse
import json
import re
import secrets
import sqlite3
import sys
import time
from .private_store import PrivateStore, StoreError
from .inference import strict_json

MAX_NODES=512
MAX_TEXT=4096
MAX_PARENTS=12

def _id(value):
    return isinstance(value,str) and re.fullmatch(r'[0-9a-f]{32}',value) is not None

class GraphStore(PrivateStore):
    name='graph'
    def __init__(self,state,*,clock=time.time):
        super().__init__(state); self.clock=clock

    def initialize(self):
        with self.db:
            self.db.execute('CREATE TABLE IF NOT EXISTS nodes (id TEXT PRIMARY KEY, kind TEXT NOT NULL, body TEXT NOT NULL, expires INTEGER NOT NULL)')
            self.db.execute('CREATE TABLE IF NOT EXISTS edges (child TEXT REFERENCES nodes(id) ON DELETE CASCADE, parent TEXT REFERENCES nodes(id) ON DELETE CASCADE, PRIMARY KEY(child,parent))')
            self.db.execute('CREATE INDEX IF NOT EXISTS edge_parent ON edges(parent)')
            self._expire()

    def _delete(self,selector,params):
        # UNION deduplicates convergent ancestry and caps work at MAX_NODES.
        sql='WITH RECURSIVE doomed(id) AS ('+selector+' UNION SELECT e.child FROM edges e JOIN doomed d ON e.parent=d.id) DELETE FROM nodes WHERE id IN (SELECT id FROM doomed)'
        before=self.count(); self.db.execute(sql,params); return before-self.count()

    def _expire(self):
        return self._delete('SELECT id FROM nodes WHERE expires<=?',(int(self.clock()),))

    def count(self): return self.db.execute('SELECT COUNT(*) FROM nodes').fetchone()[0]

    def _add(self,kind,text,parents,ttl):
        if (kind not in ('source','derived') or not isinstance(text,str) or not 0<len(text.strip())<=MAX_TEXT or len(text)>MAX_TEXT or '\0' in text or
            not isinstance(parents,(list,tuple)) or len(parents)>MAX_PARENTS or not all(_id(x) for x in parents) or len(set(parents))!=len(parents) or
            bool(parents)!=(kind=='derived') or type(ttl) is not int or not 60<=ttl<=604800): raise StoreError('Invalid graph node or retention')
        if self.count()>=MAX_NODES: raise StoreError('Graph capacity exceeded')
        for p in parents:
            if self.db.execute('SELECT 1 FROM nodes WHERE id=?',(p,)).fetchone() is None: raise StoreError('Unknown or expired parent')
        node=secrets.token_hex(16)
        self.db.execute('INSERT INTO nodes VALUES (?,?,?,?)',(node,kind,text,int(self.clock())+ttl))
        self.db.executemany('INSERT INTO edges VALUES (?,?)',((node,p) for p in parents))
        return node

    def add(self,kind,text,parents=(),ttl=86400):
        with self.db: self._expire()
        with self.db: return self._add(kind,text,parents,ttl)

    def recall(self,node):
        if not _id(node): raise StoreError('Invalid graph ID')
        with self.db: self._expire()
        with self.db:
            row=self.db.execute('SELECT kind,body,expires FROM nodes WHERE id=?',(node,)).fetchone()
            if row is None: raise StoreError('Unknown or revoked graph ID')
            ancestors=self.db.execute('WITH RECURSIVE parents(id) AS (SELECT parent FROM edges WHERE child=? UNION SELECT e.parent FROM edges e JOIN parents p ON e.child=p.id) SELECT n.id,n.kind,n.body,n.expires FROM nodes n JOIN parents p ON n.id=p.id ORDER BY n.id LIMIT ?', (node,MAX_NODES+1)).fetchall()
            if len(ancestors)>MAX_NODES: raise StoreError('Graph ancestor capacity exceeded')
            # Return ancestry identifiers, not ancestor bodies. No implicit prompt expansion.
            return {'id':node,'kind':row[0],'text':row[1],'expires':row[2],'ancestors':[{'id':a,'kind':b,'expires':d} for a,b,c,d in ancestors],'untrusted':True}

    def record_analysis(self,question,notes,critique,answer,parents=(),ttl=86400):
        if not isinstance(notes,(list,tuple)) or len(notes)>2 or not isinstance(parents,(list,tuple)) or len(parents)>2: raise StoreError('Invalid analysis inputs')
        with self.db: self._expire()
        with self.db:
            # All inputs remain dependencies, even if the model omits their citations.
            input_ids=[*parents,self._add('source',question,(),ttl)]
            input_ids.extend(self._add('source',n,(),ttl) for n in notes)
            critical=self._add('derived',critique,input_ids,ttl)
            return self._add('derived',answer,[*input_ids,critical],ttl)

    def revoke(self,node):
        if not _id(node): raise StoreError('Invalid graph ID')
        with self.db:
            self._expire(); return self._delete('SELECT id FROM nodes WHERE id=?',(node,))

    def purge(self):
        with self.db: self.db.execute('DELETE FROM nodes')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--state',required=True)
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('add'); a.add_argument('--parent',action='append',default=[]); a.add_argument('--ttl',type=int,default=86400)
    for name in ('recall','revoke'):
        a=sub.add_parser(name); a.add_argument('id')
    sub.add_parser('purge'); args=p.parse_args(argv)
    try:
        with GraphStore(args.state) as graph:
            if args.command=='add':
                raw=sys.stdin.buffer.read(65537)
                if len(raw)>65536: raise StoreError('Input budget exceeded')
                result={'id':graph.add('derived' if args.parent else 'source',strict_json(raw),args.parent,args.ttl)}
            elif args.command=='recall': result=graph.recall(args.id)
            elif args.command=='revoke': result={'revoked':graph.revoke(args.id)}
            else: graph.purge(); result={'purged':True}
        print(json.dumps(result,ensure_ascii=True)); return 0
    except (StoreError,sqlite3.Error,OSError,ValueError,RecursionError):
        print('Graph operation rejected or unavailable',file=sys.stderr); return 1
    except KeyboardInterrupt: return 130

if __name__=='__main__': sys.exit(main())
