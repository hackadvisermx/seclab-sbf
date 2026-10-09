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

from seclab_recon_state import outcome_revision, read_current_job, recon_decision

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('context_recon', ROOT/'scripts/pt-agent-context.py')
context = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context)


class ContextReconStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.workspace = self.root/'workspace'
        self.project = self.workspace/'engagements/fixture'
        (self.project/'recon').mkdir(parents=True)
        (self.project/'target.yaml').write_text('scope:\n  in_scope:\n    domains: [example.test]\n')
        (self.project/'recon/live_hosts.txt').write_text('https://example.test\n')
        self.data = self.root/'data'
        self.data.mkdir()
        self.db = self.data/'recon-jobs.db'
        self.env = {**os.environ, 'WORKSPACE_DIR':str(self.workspace), 'SECLAB_DATA_DIR':str(self.data)}

    def database(self, status='failed'):
        with sqlite3.connect(self.db) as conn:
            conn.execute('CREATE TABLE recon_jobs (engagement_type TEXT, engagement_id TEXT, run_id TEXT, status TEXT, stage TEXT, dry_run INTEGER, started_at TEXT, finished_at TEXT, error TEXT)')
            conn.execute('INSERT INTO recon_jobs VALUES (?,?,?,?,?,?,?,?,?)', ('engagement','fixture','a'*32,status,'probe',int(status=='simulated'),'2026-10-09T01:00:00+01:00',None if status in ('running','cancelling') else '2026-10-09T00:01:00Z','SECRET https://private.test/?token=fixture'))

    def collect(self, project=None):
        with patch.dict(os.environ, self.env):
            return context.generate_context_dict(project or self.project)

    def test_all_states_are_sanitized_and_match_shared_decision_without_attributing_files(self):
        self.database()
        with sqlite3.connect(self.db) as conn:
            for table, column in (('recon_job_history','scope_revision'), ('recon_job_reviews','reviewed_plan'), ('recon_job_results','result_summary')):
                conn.execute(f'CREATE TABLE {table} (engagement_type TEXT, engagement_id TEXT, run_id TEXT, {column} TEXT)')
                conn.execute(f'INSERT INTO {table} VALUES (?,?,?,?)', ('engagement','fixture','a'*32,'SECRET metadata https://private.test/token'))
        for status in ('running','cancelling','failed','blocked','cancelled','interrupted','completed','simulated'):
            with self.subTest(status=status):
                with sqlite3.connect(self.db) as conn:
                    conn.execute('UPDATE recon_jobs SET status=?, dry_run=?, finished_at=?', (status, int(status=='simulated'),None if status in ('running','cancelling') else '2026-10-09T00:01:00Z'))
                before = self.db.read_bytes()
                data = self.collect()
                state = data['recon_state']
                self.assertEqual(state['availability'], 'available')
                self.assertEqual(state['job']['status'], status)
                self.assertEqual(state['job']['run_id'], 'a'*32)
                self.assertEqual(state['job']['started_at'], '2026-10-09T00:00:00+00:00')
                expected = recon_decision(read_current_job(self.project,self.workspace,self.db))
                self.assertEqual(state['decision'], expected['next_step'] if expected else None)
                self.assertEqual(data['readiness']['ready_for_closure'], bool(data['coverage']['ready_for_closure']) and expected is None)
                self.assertEqual(data['readiness']['recon_decision_required'], expected is not None)
                self.assertEqual(state['artifacts_origin'], 'workspace_unattributed')
                self.assertEqual(data['recon']['live_hosts'], ['https://example.test'])
                markdown = context.format_markdown_context(data)
                self.assertIn(f'**Estado:** `{status}`', markdown)
                self.assertIn('sin atribución a este job', markdown)
                self.assertLess(markdown.index('Estado persistido'),markdown.index('## 1. Alcance'))
                if expected:
                    self.assertNotIn('Listo para cerrar',markdown)
                self.assertIn('Pueden proceder de ejecuciones anteriores', markdown)
                self.assertNotIn('SECRET', json.dumps(data)+markdown)
                self.assertNotIn('private.test', json.dumps(data)+markdown)
                self.assertEqual(self.db.read_bytes(), before)

    def test_missing_database_unmanaged_project_and_project_type_are_not_inferred(self):
        data = self.collect()
        self.assertEqual(data['recon_state']['availability'], 'not_recorded')
        self.assertFalse(self.db.exists())
        self.assertEqual(list(self.data.iterdir()), [])
        self.database()
        outside = self.root/'engagements/fixture'
        outside.mkdir(parents=True)
        self.assertEqual(self.collect(outside)['recon_state']['availability'], 'not_recorded')
        other_type = self.workspace/'retos/fixture'
        other_type.mkdir(parents=True)
        self.assertEqual(self.collect(other_type)['recon_state']['availability'], 'not_recorded')

    def test_unreadable_unknown_and_linked_state_is_explicit_and_does_not_expose_details(self):
        self.db.write_text('SECRET /private/database')
        def assert_unavailable():
            data = self.collect()
            state = data['recon_state']
            self.assertEqual(state['availability'], 'unavailable')
            self.assertIsNone(state['job'])
            self.assertEqual(state['decision']['id'], 'recon_state_unavailable')
            self.assertIsNone(state['decision']['command'])
            markdown = context.format_markdown_context(data)
            self.assertIn('no disponible', markdown)
            self.assertNotIn('SECRET', str(data)+markdown)
            self.assertNotIn('/private/database', str(data)+markdown)
        assert_unavailable()
        self.db.unlink()
        self.database('unknown')
        assert_unavailable()
        original = self.data/'original.db'
        self.db.rename(original)
        self.db.symlink_to(original)
        assert_unavailable()

    def test_timestamps_that_cannot_be_rendered_in_utc_require_local_review(self):
        self.database()
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE recon_jobs SET started_at='9999-12-31T23:59:59-23:59'")
        data = self.collect()
        self.assertEqual(data['recon_state']['availability'], 'unavailable')
        self.assertIsNone(data['recon_state']['job'])
        self.assertFalse(data['readiness']['ready_for_closure'])
        self.assertNotIn('SECRET', context.format_markdown_context(data))

    def test_busy_database_requires_local_review(self):
        self.database()
        with sqlite3.connect(self.db) as conn:
            conn.execute('BEGIN EXCLUSIVE')
            state = self.collect()['recon_state']
        self.assertEqual(state['availability'], 'unavailable')
        self.assertEqual(state['decision']['id'], 'recon_state_unavailable')

    def test_review_is_current_and_does_not_confirm_results_or_expose_raw_metadata(self):
        self.database()
        with sqlite3.connect(self.db) as conn:
            conn.execute('CREATE TABLE recon_job_outcome_reviews (engagement_type TEXT, engagement_id TEXT, run_id TEXT, job_revision TEXT, reviewed_at TEXT)')
            conn.execute('INSERT INTO recon_job_outcome_reviews VALUES (?,?,?,?,?)',('engagement','fixture','a'*32,outcome_revision(read_current_job(self.project,self.workspace,self.db)),'2026-10-09T00:02:00Z'))
        data = self.collect()
        self.assertEqual(data['recon_state']['decision']['id'], 'recon_prepare_plan')
        self.assertEqual(data['recon_state']['job']['status'], 'failed')
        self.assertEqual(data['recon_state']['outcome_review'], {'reviewed_at':'2026-10-09T00:02:00+00:00','decision':'prepare_new_plan'})
        self.assertIn('Revisar no confirma resultados ni concede permisos', context.format_markdown_context(data))
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE recon_jobs SET error='changed SECRET'")
        state = self.collect()['recon_state']
        self.assertIsNone(state['outcome_review'])
        self.assertEqual(state['decision']['id'], 'recon_failed')
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE recon_jobs SET run_id=?, status='running', finished_at=NULL", ('b'*32,))
        state = self.collect()['recon_state']
        self.assertIsNone(state['outcome_review'])
        self.assertEqual(state['decision']['id'], 'recon_running')

    def test_job_started_during_context_collection_is_read_after_other_sources(self):
        def coverage(*args):
            self.database('running')
            return {'ready_for_closure':True}
        with patch.object(context, 'collect_coverage_summary', side_effect=coverage):
            data = self.collect()
            state = data['recon_state']
        self.assertTrue(data['coverage']['ready_for_closure'])
        self.assertFalse(data['readiness']['ready_for_closure'])
        self.assertEqual(state['job']['status'], 'running')
        self.assertEqual(state['decision']['id'], 'recon_running')

    def test_cli_json_and_markdown_use_same_persisted_job_and_keep_database_unchanged(self):
        self.database('blocked')
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        command = ['python3',str(ROOT/'scripts/pt-agent-context.py'),str(self.project)]
        data = json.loads(subprocess.run(command+['-j'],env=self.env,capture_output=True,text=True,check=True,timeout=10).stdout)
        markdown = subprocess.run(command,env=self.env,capture_output=True,text=True,check=True,timeout=10).stdout
        self.assertEqual(data['recon_state']['decision']['id'], 'recon_blocked')
        self.assertIn('Revisar alcance y autorización tras el bloqueo', markdown)
        self.assertIn('a'*32, markdown)
        self.assertNotIn('SECRET', markdown)
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), before)


if __name__ == '__main__':
    unittest.main()
