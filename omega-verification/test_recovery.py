import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from mobile_agent.recovery import CheckpointStore, RecoveryError, ResourceGuard
from mobile_agent.orchestrator import run_task
from mobile_agent.inference import ModelError

class Model:
    def __init__(self, fail=None): self.calls=0; self.fail=fail
    def complete(self, *args):
        self.calls+=1
        if self.calls==self.fail: raise ModelError('failure')
        return json.dumps({'text':f'output {self.calls}', 'citations':['e1']})

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)/'private'
    def tearDown(self): self.tmp.cleanup()
    def run_model(self, model, question='q', **kwargs):
        with CheckpointStore(self.root, 'job', 'config') as checkpoint:
            return run_task(model,question,notes=['note'],checkpoint=checkpoint,**kwargs)
    def test_resume_after_failed_second_role(self):
        with self.assertRaises(ModelError): self.run_model(Model(2))
        model=Model(); r=self.run_model(model)
        self.assertEqual(model.calls,2); self.assertEqual(r['reused_model_calls'],1)
        self.assertEqual(len(r['graph']['nodes']),4)
    def test_completed_job_is_reused_without_inference(self):
        self.run_model(Model()); model=Model(); r=self.run_model(model)
        self.assertEqual(model.calls,0); self.assertEqual(r['reused_model_calls'],3)
    def test_modified_question_or_config_rejected(self):
        self.run_model(Model())
        with self.assertRaises(RecoveryError): self.run_model(Model(),'other')
        with CheckpointStore(self.root,'job','other-config') as c:
            with self.assertRaises(RecoveryError): run_task(Model(),'q',notes=['note'],checkpoint=c)
    def test_reject_remote_evidence_and_image(self):
        for args in ({'workflow':{}},{'image':'data:image/png;base64,AA=='}):
            with self.assertRaises(RecoveryError): self.run_model(Model(),**args)
    def test_lock_and_permissions(self):
        with CheckpointStore(self.root,'job','config'):
            with self.assertRaises(RecoveryError):
                with CheckpointStore(self.root,'job','config'): pass
        self.assertEqual(self.root.stat().st_mode & 0o777,0o700)
        self.assertEqual((self.root/'checkpoints.sqlite3').stat().st_mode & 0o777,0o600)
    def test_reject_insecure_directory(self):
        self.root.mkdir(mode=0o755)
        with self.assertRaises(RecoveryError):
            with CheckpointStore(self.root,'job','config'): pass
    def test_delete_job(self):
        self.run_model(Model())
        with CheckpointStore(self.root,'job','config') as c: c.purge()
        self.assertEqual(self.run_model(Model())['reused_model_calls'],0)
    def test_guard_blocks_before_model_call(self):
        model=Model()
        guard=ResourceGuard(min_memory_mib=1024, memory_reader=lambda:512)
        with self.assertRaises(RecoveryError): self.run_model(model,before_call=guard.check)
        self.assertEqual(model.calls,0)
    def test_guard_thermal_limit_and_bad_sensor(self):
        for reading in (43.0,None,float('nan')):
            g=ResourceGuard(min_memory_mib=1,max_temperature=43,temperature_reader=lambda:reading,memory_reader=lambda:1024)
            with self.assertRaises(RecoveryError): g.check()
    def test_guard_passes_safe_readings(self):
        ResourceGuard(min_memory_mib=1,max_temperature=43,temperature_reader=lambda:39,memory_reader=lambda:1024).check()
if __name__=='__main__': unittest.main(verbosity=2)
