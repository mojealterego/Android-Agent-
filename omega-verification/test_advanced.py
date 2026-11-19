import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import subprocess
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mobile_agent.advanced import (AdvancedError, EmbeddingClient, semantic_search,
    preview_create, apply_create, ResourceLease)

class AdvancedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)/'private'; self.root.mkdir(mode=0o700)
    def tearDown(self): self.tmp.cleanup()
    def test_semantic_rank_and_use_single_batch(self):
        calls=[]
        def embed(texts):
            calls.append(texts); return [[1,0],[0,1],[1,0]]
        r=semantic_search('query',[{'id':'b','text':'unrelated'},{'id':'a','text':'relevant'}],embed)
        self.assertEqual([x['id'] for x in r],['a','b']); self.assertEqual(len(calls),1)
    def test_invalid_vectors(self):
        for vectors in ([[0,0],[1,0]],[[1,0],[1]],[[float('nan'),0],[1,0]],[[1,0],[True,0]]):
            with self.assertRaises(AdvancedError): semantic_search('q',[{'id':'a','text':'t'}],lambda _:vectors)
    def test_documents_are_bounded_and_unique(self):
        for docs in ([{'id':'a','text':'t'}]*2,[{'id':'a','text':'x'*4097}],[],[{'id':'a','text':'t','path':'/etc'}]):
            with self.assertRaises(AdvancedError): semantic_search('q',docs,lambda _:self.fail('invalid input reached model'))
    def test_real_loopback_embeddings(self):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.path!='/v1/embeddings' or data['input']!=['q','t'] or self.headers.get('Authorization')!='Bearer test':
                    self.send_error(400); return
                body=json.dumps({'data':[{'index':1,'embedding':[0,1]},{'index':0,'embedding':[1,0]}]}).encode()
                self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(body)
            def log_message(self,*_): pass
        server=HTTPServer(('127.0.0.1',0),Handler); thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try: self.assertEqual(EmbeddingClient(port=server.server_port,token='test').embed(['q','t']),[[1,0],[0,1]])
        finally: server.shutdown(); thread.join(); server.server_close()
    def test_preview_is_read_only_and_apply_creates(self):
        p=preview_create(self.root,'note.txt','hello'); self.assertFalse((self.root/'note.txt').exists())
        apply_create(self.root,'note.txt','hello',p['approval']); self.assertEqual((self.root/'note.txt').read_text(),'hello')
        self.assertEqual((self.root/'note.txt').stat().st_mode & 0o777,0o600)
    def test_changed_content_or_wrong_root_denied(self):
        p=preview_create(self.root,'note.txt','hello'); other=self.root/'other'; other.mkdir(mode=0o700)
        for root,text in ((self.root,'modified'),(other,'hello')):
            with self.assertRaises(AdvancedError): apply_create(root,'note.txt',text,p['approval'])
        self.assertFalse((self.root/'note.txt').exists())
    def test_no_overwrite_or_symlink(self):
        p=preview_create(self.root,'note.txt','hello'); (self.root/'note.txt').symlink_to('/dev/null')
        with self.assertRaises(AdvancedError): apply_create(self.root,'note.txt','hello',p['approval'])
        self.assertTrue((self.root/'note.txt').is_symlink())
    def test_path_and_permissions(self):
        for name in ('../x.txt','/x.txt','x.sh','.secret.txt'):
            with self.assertRaises(AdvancedError): preview_create(self.root,name,'test')
        os.chmod(self.root,0o755)
        with self.assertRaises(AdvancedError): preview_create(self.root,'x.txt','test')
    def test_lease_excludes_and_releases(self):
        with ResourceLease(self.root):
            with self.assertRaises(AdvancedError):
                with ResourceLease(self.root): pass
        with ResourceLease(self.root): pass
    def test_legacy_cli_respects_shared_lease(self):
        env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]/'scripts'))
        with ResourceLease(self.root):
            result=subprocess.run([sys.executable,'-m','mobile_agent','--lease-dir',str(self.root)],input=b'{"question":"q"}',env=env,capture_output=True,timeout=5)
        self.assertEqual(result.returncode,1); self.assertIn(b'lease unavailable',result.stderr)
    def test_cli_preview_apply_and_replay(self):
        env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]/'scripts'))
        cmd=[sys.executable,'-m','mobile_agent.advanced']; data=b'{"name":"x.txt","text":"hello"}'
        preview=subprocess.run(cmd+['preview','--root',str(self.root)],input=data,env=env,capture_output=True,timeout=5,check=True)
        token=json.loads(preview.stdout)['approval']; self.assertFalse((self.root/'x.txt').exists())
        args=cmd+['apply','--root',str(self.root),'--approve',token]
        subprocess.run(args,input=data,env=env,capture_output=True,timeout=5,check=True)
        self.assertNotEqual(subprocess.run(args,input=data,env=env,capture_output=True,timeout=5).returncode,0)
        self.assertEqual((self.root/'x.txt').read_text(),'hello')
    def test_lease_rejects_symlink(self):
        (self.root/'inference.lock').symlink_to('/dev/null')
        with self.assertRaises(AdvancedError):
            with ResourceLease(self.root): pass

if __name__=='__main__': unittest.main(verbosity=2)
