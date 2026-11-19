import hashlib
import os
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from integration_intake import inspect_zip, IntakeError

class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.archive=self.root/'input.zip'
    def tearDown(self): self.tmp.cleanup()
    def make(self,entries):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',UserWarning)
            with zipfile.ZipFile(self.archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
                for name,data in entries: z.writestr(name,data)
    def test_manifest_is_deterministic_and_content_hashed(self):
        self.make([('dir/',b''),('dir/b.txt',b'world'),('a.txt',b'hello')]); a=inspect_zip(self.archive); b=inspect_zip(self.archive)
        self.assertEqual(a,b); self.assertEqual(a['archive_sha256'],hashlib.sha256(self.archive.read_bytes()).hexdigest()); self.assertEqual([x['path'] for x in a['files']],['a.txt','dir/b.txt']); self.assertEqual(a['files'][0]['sha256'],hashlib.sha256(b'hello').hexdigest()); self.assertEqual(a['state'],'validated_not_integrated')
        self.assertEqual(sorted(p.name for p in self.root.iterdir()),['input.zip'])
    def test_unsafe_paths(self):
        for name in ('../evil','/root','C:/x','a\\b','a/../b','a//b','CON.txt','a/..','a/dir.','a/dir ','a\x01b','a:stream','.git/config','dir/.GIT/hooks/x'):
            with self.subTest(name=name):
                self.make([(name,b'x')]); self.assertRaises(IntakeError,inspect_zip,self.archive)
    def test_duplicate_casefold_unicode_or_file_parent(self):
        for entries in [[('same',b'a'),('same',b'b')],[('A/x',b'a'),('a/y',b'b')],[('café',b'a'),('cafe\u0301',b'b')],[('a',b'a'),('a/b',b'b')]]:
            self.make(entries);self.assertRaises(IntakeError,inspect_zip,self.archive)
    def test_symlink_and_special_file_denied(self):
        for mode in (0o120777,0o010600,0o060600):
            info=zipfile.ZipInfo('link');info.create_system=3;info.external_attr=mode<<16
            self.make([(info,b'target')]);self.assertRaises(IntakeError,inspect_zip,self.archive)
    def test_symlink_archive_denied_and_hash_pin(self):
        self.make([('f',b'x')]);link=self.root/'alias.zip';link.symlink_to(self.archive)
        self.assertRaises(IntakeError,inspect_zip,link);self.assertRaises(IntakeError,inspect_zip,self.archive,expected_sha256='0'*64)
        self.assertEqual(inspect_zip(self.archive,expected_sha256=hashlib.sha256(self.archive.read_bytes()).hexdigest())['file_count'],1)
    def test_limits(self):
        self.make([('a',b'a'*10000),('b',b'b'*10000)])
        for options in ({'max_files':1},{'max_expanded':15000},{'max_member':9999},{'max_ratio':10}):
            self.assertRaises(IntakeError,inspect_zip,self.archive,**options)
    def test_corrupt_crc_and_trailing_data(self):
        with zipfile.ZipFile(self.archive,'w') as z:z.writestr('a',b'UNIQUE_payload')
        data=self.archive.read_bytes();self.archive.write_bytes(data.replace(b'UNIQUE_payload',b'XNIQUE_payload',1));self.assertRaises(IntakeError,inspect_zip,self.archive)
        self.make([('a',b'x')]);self.archive.write_bytes(self.archive.read_bytes()+b'trailing');self.assertRaises(IntakeError,inspect_zip,self.archive)
    def test_no_empty_or_executable_symlink(self):
        self.make([('dir/',b'')]);self.assertRaises(IntakeError,inspect_zip,self.archive)
        self.make([('dir/',b'nonempty')]);self.assertRaises(IntakeError,inspect_zip,self.archive)
    def test_protected_atomic_stage(self):
        self.make([('sub/a.txt',b'one'),('b.txt',b'two')]);stage=self.root/'staging';stage.mkdir(mode=0o700)
        result=inspect_zip(self.archive,stage_root=stage);output=Path(result['staged_directory']);self.assertEqual(result['state'],'staged_not_integrated');self.assertEqual(output.parent,stage);self.assertEqual((output/'sub/a.txt').read_bytes(),b'one');self.assertEqual((output/'b.txt').stat().st_mode&0o777,0o600);self.assertEqual(output.stat().st_mode&0o777,0o700)
        self.make([('../evil',b'bad')]);before=list(stage.iterdir());self.assertRaises(IntakeError,inspect_zip,self.archive,stage_root=stage);self.assertEqual(list(stage.iterdir()),before)
    def test_corrupt_member_removes_quarantine(self):
        with zipfile.ZipFile(self.archive,'w') as z:z.writestr('a',b'UNIQUE_payload')
        data=self.archive.read_bytes();self.archive.write_bytes(data.replace(b'UNIQUE_payload',b'XNIQUE_payload',1))
        stage=self.root/'staging';stage.mkdir(mode=0o700)
        self.assertRaises(IntakeError,inspect_zip,self.archive,stage_root=stage);self.assertEqual(list(stage.iterdir()),[])
    def test_insecure_stage_denied(self):
        self.make([('a',b'x')]);stage=self.root/'staging';stage.mkdir(mode=0o755);self.assertRaises(IntakeError,inspect_zip,self.archive,stage_root=stage)

if __name__=='__main__': unittest.main(verbosity=2)
