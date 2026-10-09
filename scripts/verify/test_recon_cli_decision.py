import hashlib
import importlib.util
import json
import os
import pathlib
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[2]
from seclab_recon_state import read_current_job, outcome_revision, project_recon_decision


class ReconCliDecisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.workspace = self.root/'workspace'
        self.project = self.workspace/'engagements/fixture'
        self.project.mkdir(parents=True)
        (self.project/'target.yaml').write_text('scope:\n  in_scope:\n    domains: [example.test]\nauthorization:\n  reference: fixture-only\n  valid_from: "2000-01-01T00:00:00Z"\n  valid_until: "2099-01-01T00:00:00Z"\n  allow_passive: true\n  allow_active: true\n')
        self.data = self.root/'data'
        self.data.mkdir()
        self.db = self.data/'recon-jobs.db'
        self.env = {**os.environ, 'WORKSPACE_DIR':str(self.workspace), 'SECLAB_DATA_DIR':str(self.data), 'NO_COLOR':'1'}

    def database(self, status='failed'):
        with sqlite3.connect(self.db) as conn:
            conn.execute('CREATE TABLE recon_jobs (engagement_type TEXT, engagement_id TEXT, run_id TEXT, status TEXT, stage TEXT, dry_run INTEGER, started_at TEXT, finished_at TEXT, error TEXT)')
            conn.execute('INSERT INTO recon_jobs VALUES (?,?,?,?,?,?,?,?,?)', ('engagement','fixture','a'*32,status,'probe',0,'2026-10-09T00:00:00Z',None if status in ('running','cancelling') else '2026-10-09T00:01:00Z','SECRET https://private.test/?token=x'))

    def run_cli(self, *flags):
        return subprocess.run(['python3',str(ROOT/'scripts/pt-audit-next.py'),str(self.project),*flags], env=self.env, capture_output=True, text=True, check=True, timeout=10)

    def test_failed_legacy_job_blocks_all_commands_prompts_and_copy_without_mutation(self):
        self.database()
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        result = json.loads(self.run_cli('-j','-p','-a','-c').stdout)
        self.assertEqual(result['next_step']['id'],'recon_failed')
        self.assertEqual(result['decision_job']['run_id'],'a'*32)
        self.assertIsNone(result['next_step']['command'])
        self.assertFalse(result['prompt_available'])
        self.assertEqual(result['prompt'],'')
        self.assertEqual(len(result['roadmap']),1)
        self.assertNotIn('SECRET',str(result))
        self.assertNotIn('private.test',str(result))
        text = self.run_cli('-p','-a','-c')
        self.assertIn('Revisar el fallo',text.stdout)
        self.assertNotIn('pt-recon',text.stdout)
        self.assertNotIn('None',text.stdout)
        self.assertIn('no hay comando ni prompt',text.stderr)
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(),before)
        self.assertEqual(sorted(path.name for path in self.data.iterdir()),['recon-jobs.db'])

    def test_no_database_or_unmanaged_project_preserves_legacy_without_creating_state(self):
        self.assertEqual(json.loads(self.run_cli('-j').stdout)['next_step']['id'],'recon')
        self.assertFalse(self.db.exists())
        self.database()
        outside = self.root/'engagements/fixture'
        outside.mkdir(parents=True)
        self.assertIsNone(read_current_job(outside,self.workspace,self.db))
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE recon_jobs SET engagement_type='reto'")
        self.assertIsNone(read_current_job(self.project,self.workspace,self.db))

    def test_corrupt_schema_symlink_and_unknown_job_fail_to_local_review(self):
        self.db.write_text('PRIVATE database path /secret')
        result=json.loads(self.run_cli('-j','-p').stdout)
        self.assertEqual(result['next_step']['id'],'recon_state_unavailable')
        self.assertEqual(result['prompt'],'')
        self.assertNotIn('PRIVATE',str(result))
        self.db.unlink()
        self.database(status='unknown')
        self.assertEqual(json.loads(self.run_cli('-j').stdout)['next_step']['id'],'recon_state_unavailable')
        target=self.data/'original.db'
        self.db.rename(target)
        self.db.symlink_to(target)
        self.assertEqual(json.loads(self.run_cli('-j').stdout)['next_step']['id'],'recon_state_unavailable')

    def test_review_matches_raw_metadata_and_invalidates_after_changes(self):
        self.database()
        job=read_current_job(self.project,self.workspace,self.db)
        with sqlite3.connect(self.db) as conn:
            conn.execute('CREATE TABLE recon_job_outcome_reviews (engagement_type TEXT, engagement_id TEXT, run_id TEXT, job_revision TEXT, reviewed_at TEXT)')
            conn.execute('INSERT INTO recon_job_outcome_reviews VALUES (?,?,?,?,?)',('engagement','fixture','a'*32,outcome_revision(job),'2026-10-09T00:02:00+00:00'))
        self.assertEqual(json.loads(self.run_cli('-j','-p').stdout)['next_step']['id'],'recon_prepare_plan')
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE recon_jobs SET error='changed'")
        self.assertEqual(json.loads(self.run_cli('-j','-p').stdout)['next_step']['id'],'recon_failed')

    def test_busy_store_does_not_fall_back_to_execution(self):
        self.database()
        with sqlite3.connect(self.db) as conn:
            conn.execute('BEGIN EXCLUSIVE')
            self.assertEqual(json.loads(self.run_cli('-j').stdout)['next_step']['id'],'recon_state_unavailable')

    def test_job_started_during_heuristic_generation_is_rechecked(self):
        spec=importlib.util.spec_from_file_location('audit_next_cli',ROOT/'scripts/pt-audit-next.py')
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        def roadmap(*args):
            self.database(status='running')
            return [{'id':'recon','command':'pt-recon'}]
        with patch.dict(os.environ,self.env), patch.object(module,'determine_roadmap',side_effect=roadmap), patch('sys.argv',['pt-next',str(self.project),'-j','-p']), patch('builtins.print') as printed:
            self.assertEqual(module.main(),0)
        result=json.loads(printed.call_args.args[0])
        self.assertEqual(result['next_step']['id'],'recon_running')
        self.assertEqual(result['prompt'],'')

    def test_incomplete_terminal_job_duplicate_rows_and_linked_data_dir_fail_locally(self):
        self.database(status='completed')
        with sqlite3.connect(self.db) as conn:
            conn.execute('UPDATE recon_jobs SET finished_at=NULL')
        self.assertEqual(json.loads(self.run_cli('-j').stdout)['next_step']['id'],'recon_state_unavailable')
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE recon_jobs SET finished_at='2026-10-09T00:01:00Z'")
            conn.execute('INSERT INTO recon_jobs SELECT * FROM recon_jobs')
        self.assertEqual(json.loads(self.run_cli('-j').stdout)['next_step']['id'],'recon_state_unavailable')
        actual=self.root/'actual-data'
        self.data.rename(actual)
        self.data.symlink_to(actual,target_is_directory=True)
        self.assertEqual(json.loads(self.run_cli('-j').stdout)['next_step']['id'],'recon_state_unavailable')
