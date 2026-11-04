"""Regression checks for real upgrade/data preservation and false-green checks."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class Workspace(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='exam-kit-test-')
        self.ws=Path(self.tmp.name)
    def tearDown(self):
        self.tmp.cleanup()
    def put(self,name,content):
        p=self.ws/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(content if isinstance(content,bytes) else content.encode())
        return p
    def run_install(self,expected=0):
        r=subprocess.run([sys.executable,str(ROOT/'install.py'),str(self.ws)],capture_output=True,text=True)
        self.assertEqual(r.returncode,expected,r.stdout+r.stderr)
        return r


class InstallTests(Workspace):
    def test_fresh_preserves_project_instructions_and_notes(self):
        self.put('AGENTS.md','Project rules stay here.\n')
        self.put('notes/spec.md','Existing approved specification')
        self.put('notes/requirements.md','Legacy task requirements')
        self.run_install()
        self.assertTrue((self.ws/'AGENTS.md').read_text().startswith('Project rules stay here.\n'))
        self.assertEqual((self.ws/'notes/spec.md').read_text(),'Existing approved specification')
        self.assertEqual((self.ws/'notes/requirements.md').read_text(),'Legacy task requirements')
        self.assertTrue((self.ws/'kit/prompts/02-answer-update.md').is_file())
        self.assertTrue((self.ws/'kit/guide/index.html').is_file())

    def test_rerun_does_not_change_managed_payloads(self):
        self.run_install()
        before={str(p.relative_to(self.ws)):p.read_bytes() for p in self.ws.rglob('*') if p.is_file() and '.exam-kit' not in p.parts}
        r=self.run_install()
        after={str(p.relative_to(self.ws)):p.read_bytes() for p in self.ws.rglob('*') if p.is_file() and '.exam-kit' not in p.parts}
        self.assertEqual(before,after)
        self.assertIn('"updated": 0',r.stdout)

    def test_known_v1_upgrade_preserves_surrounding_text(self):
        old=(ROOT/'tests/fixtures/v1/AGENTS.md').read_bytes()
        self.put('AGENTS.md',b'PROJECT PREFIX\n'+old+b'\nPROJECT SUFFIX\n')
        self.put('.agents/skills/task-brief/SKILL.md',(ROOT/'tests/fixtures/v1/task-brief.md').read_bytes())
        self.put('notes/decisions.md','Previous decisions are user data')
        self.run_install()
        new=(self.ws/'AGENTS.md').read_text()
        self.assertTrue(new.startswith('PROJECT PREFIX\n'))
        self.assertTrue(new.endswith('\nPROJECT SUFFIX\n'))
        self.assertIn('작업 규칙 · v2',new)
        self.assertEqual((self.ws/'notes/decisions.md').read_text(),'Previous decisions are user data')
        self.assertEqual((self.ws/'.agents/skills/task-brief/SKILL.md').read_bytes(),(ROOT/'skills/task-brief/SKILL.md').read_bytes())
        self.assertTrue(list((self.ws/'.exam-kit/backups').rglob('AGENTS.md')))

    def test_modified_files_and_block_are_preserved_as_conflicts(self):
        self.run_install()
        p=self.ws/'kit/check.py'; p.write_bytes(p.read_bytes()+b'\n# user edit\n')
        a=self.ws/'AGENTS.md'; a.write_text(a.read_text().replace('작업 규칙 · v2','사용자 수정 규칙'))
        original=(p.read_bytes(),a.read_bytes())
        self.run_install(3)
        self.assertEqual((p.read_bytes(),a.read_bytes()),original)
        self.assertTrue((self.ws/'.exam-kit/incoming/kit/check.py').exists())
        self.assertTrue((self.ws/'.exam-kit/incoming/AGENTS.md').exists())
        self.run_install(3)  # rerun must not misclassify a user edit as a managed baseline
        self.assertEqual((p.read_bytes(),a.read_bytes()),original)

    def test_known_installed_hash_is_upgraded_and_backed_up(self):
        self.run_install()
        old=b'# known earlier installed tool\n';self.put('kit/check.py',old)
        m=self.ws/'.exam-kit/manifest.json';data=json.loads(m.read_text())
        data['files']['kit/check.py']=hashlib.sha256(old).hexdigest();m.write_text(json.dumps(data))
        self.run_install()
        self.assertEqual((self.ws/'kit/check.py').read_bytes(),(ROOT/'tools/check.py').read_bytes())
        self.assertIn(old,[p.read_bytes() for p in (self.ws/'.exam-kit/backups').rglob('check.py')])

    def test_symlink_destination_rejected_before_install(self):
        outside=self.ws/'outside';outside.mkdir()
        (self.ws/'.agents').symlink_to(outside,target_is_directory=True)
        self.run_install(2)
        self.assertEqual(list(outside.iterdir()),[])
        self.assertFalse((self.ws/'AGENTS.md').exists())

    def test_malformed_marker_is_not_replaced(self):
        original=b'Project text\n<!-- exam-kit:begin -->\ncustom unfinished block'
        self.put('AGENTS.md',original)
        self.run_install(3)
        self.assertEqual((self.ws/'AGENTS.md').read_bytes(),original)


class CheckTests(Workspace):
    def run_check(self,contract,expected):
        self.put('verify/contract.json',json.dumps(contract))
        self.put('notes/work.md','Keep current work\n')
        r=subprocess.run([sys.executable,str(ROOT/'tools/check.py'),'--root',str(self.ws),'--log'],capture_output=True,text=True)
        self.assertEqual(r.returncode,expected,r.stdout+r.stderr)
        return r
    def test_pass(self):
        self.put('output/result.txt','Expected result')
        r=self.run_check({'files':[{'path':'output/result.txt','contains':['Expected result']}]},0)
        self.assertIn('PASS',r.stdout)
        self.assertTrue((self.ws/'notes/work.md').read_text().startswith('Keep current work\n'))
        self.assertFalse((self.ws/'notes/verification.md').exists())
    def test_failure(self):
        r=self.run_check({'files':[{'path':'missing.txt'}]},1)
        self.assertIn('FAIL',r.stdout)
    def test_unexecuted_run_is_hold(self):
        r=self.run_check({'run':['must-not-run-command'],'files':[]},2)
        self.assertIn('HOLD',r.stdout)
        self.assertNotIn('· PASS',(self.ws/'notes/work.md').read_text())
    def test_zero_checks_are_not_pass(self):
        r=self.run_check({},2)
        self.assertIn('HOLD',r.stdout)
    def test_invalid_contract_shape(self):
        r=self.run_check({'files':'wrong type'},2)
        self.assertIn('형식 오류',r.stdout)


class PreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('kit_preview',ROOT/'tools/preview.py')
        cls.preview=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.preview)
    def test_pasted_html_is_text(self):
        out=self.preview.md_to_html('<script>alert(1)</script>')
        self.assertNotIn('<script>',out);self.assertIn('&lt;script&gt;',out)
    def test_script_link_is_not_clickable(self):
        self.assertNotIn('href=',self.preview.inline('[x](javascript:alert(1))'))
    def test_attribute_quotes_are_escaped(self):
        out=self.preview.inline('[x](https://example.com/"onclick="bad)')
        self.assertIn('&quot;',out);self.assertNotIn('"onclick=',out)
    def test_normal_link_remains(self):
        self.assertIn('href="https://example.com/"',self.preview.inline('[x](https://example.com/)'))


if __name__=='__main__':
    unittest.main()
