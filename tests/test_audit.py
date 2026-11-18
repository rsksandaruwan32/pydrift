import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('audit',Path(__file__).resolve().parents[1]/'backend/audit.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
    def setUp(self): self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def write(self,path,value):
        p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value,encoding='utf-8');return p
    def rules(self): return [x['rule'] for x in m.audit(self.root)['findings']]
    def test_empty(self): self.assertEqual(self.rules(),[])
    def test_jsonc(self): self.assertEqual(m.jsonc('{/*c*/"url":"https://x",//hi\n"n":1,}'),{'url':'https://x','n':1})
    def test_windows_strings(self):
        obj={'p':'C:\\Users\\Sachin\\python.exe','s':'a"//b'};self.assertEqual(m.jsonc(json.dumps(obj)),obj)
    def test_duplicate(self):
        with self.assertRaises(ValueError): m.jsonc('{"x":1,"x":2}')
    def test_unclosed_comment(self):
        with self.assertRaises(ValueError):m.jsonc('{/*')
    def test_bad_json(self):self.write('.vscode/settings.json','bad');self.assertIn('PD000',self.rules())
    def test_root_array(self):self.write('.vscode/settings.json','[]');self.assertIn('PD000',self.rules())
    def test_drift(self):
        self.write('.vscode/settings.json',json.dumps({'python.defaultInterpreterPath':'envA'}))
        self.write('.vscode/launch.json',json.dumps({'configurations':[{'python':'envB'}]}));self.assertIn('PD001',self.rules())
    def test_same(self):
        self.write('.vscode/settings.json',json.dumps({'python.defaultInterpreterPath':'envA'}))
        self.write('.vscode/launch.json',json.dumps({'configurations':[{'python':'envA'}]}));self.assertNotIn('PD001',self.rules())
    def test_command_variable(self):
        self.write('.vscode/launch.json',json.dumps({'python':'${command:python.interpreterPath}'}));self.assertEqual(self.rules(),[])
    def test_missing(self):
        self.write('.vscode/settings.json',json.dumps({'python.defaultInterpreterPath':str(self.root/'missing')}));self.assertIn('PD002',self.rules())
    def test_legacy(self):self.write('.vscode/settings.json','{"pythonPath":"python"}');self.assertIn('PD004',self.rules())
    def test_pip_task(self):self.write('.vscode/tasks.json','{"command":"pip","args":["install"]}');self.assertIn('PD003',self.rules())
    def test_ci_pip(self):
        self.write('.github/workflows/ci.yml','run: pip install x\nrun: python -m pip install y\n# pip install z');self.assertEqual(self.rules().count('PD003'),1)
    def test_versions(self):
        self.write('.python-version','3.10.9');self.write('.github/workflows/ci.yml','python-version: "3.11"');self.assertIn('PD005',self.rules())
    def test_patch_ok(self):
        self.write('.python-version','3.10.9');self.write('.github/workflows/ci.yml','python-version: "3.10"');self.assertNotIn('PD005',self.rules())
    def test_size_limit(self):self.write('.vscode/settings.json',' '* (m.LIMIT+1));self.assertEqual(len(m.audit(self.root)['skipped']),1)
    def test_fingerprint(self):
        self.write('.vscode/tasks.json','{"command":"pip"}');self.assertEqual(m.audit(self.root),m.audit(self.root))
    def test_symlink(self):
        target=self.write('outside.json','{}');p=self.root/'.vscode/settings.json';p.parent.mkdir()
        try:p.symlink_to(target)
        except OSError:self.skipTest('Symlink privileges unavailable')
        self.assertEqual(len(m.audit(self.root)['skipped']),1)
    def test_cli(self):
        self.write('.vscode/settings.json','invalid')
        result=subprocess.run([sys.executable,'-I','-S',m.__file__,str(self.root),'--fail-on','error'],capture_output=True,text=True)
        self.assertEqual(result.returncode,1);self.assertEqual(json.loads(result.stdout)['schema_version'],1)
if __name__=='__main__':unittest.main()
