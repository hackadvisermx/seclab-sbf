import copy
import json
import pathlib
import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import closing
from unittest.mock import patch
from app.core.recon_jobs import ReconJobStore
from app.core.recon_results import METRICS, STAGE_COUNTS, PATTERNS, result_summary
from app.services import recon_service as module


class TestReconResults(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        self.db = self.root / 'state/jobs.db'
        self.store = ReconJobStore(self.db)
        self.key = ('engagement', 'fixture')

    def raw(self, run_id, count=2, status='completed'):
        raw = {'run_id': run_id, 'scope_revision': 'a' * 64, 'timestamp': '2026-10-09T12:00:00+00:00',
               'status': status, 'dry_run': False, 'metrics_source': 'artifacts' if status == 'completed' else 'previous_artifacts',
               'stages_executed': ['urls'], 'stage_results': {'urls': {'status': status,
               'urls_count': count, 'js_files_count': 1, 'failure_kind': None if status == 'completed' else 'technical',
               'error': 'private-error', 'urls': ['https://user:password@example.test/private?key=secret']}},
               'scope_contract': {'authorization': {'reference': 'private-reference'}},
               'commands': ['curl https://example.test/?key=secret'], 'gf_patterns': {'secret-name': 3}}
        raw.update({key: count for key in METRICS})
        return raw

    def finish(self, key=None, count=2):
        key = key or self.key
        job = self.store.begin(key, 'urls', False)
        value = result_summary(self.raw(job['run_id'], count), job['run_id'], 'urls', 'completed', False)
        self.store.finish(key, job['run_id'], 'completed', scope_revision='a' * 64, result_summary=value)
        return job['run_id'], value

    def test_results_survive_later_jobs_reopening_and_backup_without_private_raw_data(self):
        first, value = self.finish(count=2)
        second, _ = self.finish(count=5)
        jobs = ReconJobStore(self.db).history(self.key)['jobs']
        self.assertEqual([job['result_summary']['metrics']['urls_count'] for job in jobs], [5, 2])
        self.assertEqual(jobs[1]['result_summary'], value)
        stored = json.dumps(jobs)
        for private in ['password', 'private-error', 'private-reference', 'curl', 'secret-name', 'https://']:
            self.assertNotIn(private, stored)
        destination = self.root / 'backup/jobs.db'
        destination.parent.mkdir()
        with closing(self.store.connect()) as source, closing(sqlite3.connect(destination)) as target:
            source.backup(target)
        self.assertEqual(ReconJobStore(destination).history(self.key)['jobs'], jobs)
        self.assertEqual(self.store.get(self.key)['run_id'], second)

    def test_legacy_simulations_and_jobs_without_summary_never_receive_invented_results(self):
        completed = self.store.begin(self.key, 'urls', False)
        self.store.finish(self.key, completed['run_id'], 'completed')
        simulation = self.store.begin(self.key, 'urls', True)
        self.store.finish(self.key, simulation['run_id'], 'simulated')
        self.assertTrue(all(job['result_summary'] is None for job in self.store.history(self.key)['jobs']))
        with self.store.connect() as conn:
            conn.execute('DROP TABLE recon_job_history')
        migrated = ReconJobStore(self.db).history(self.key)['jobs']
        self.assertEqual(len(migrated), 1)
        self.assertEqual(migrated[0]['origin'], 'legacy-current')
        self.assertIsNone(migrated[0]['result_summary'])

    def test_summary_validation_rejects_mismatched_inconsistent_and_unbounded_metadata(self):
        raw = self.raw('fixture')
        changes = [{'run_id': 'another'}, {'dry_run': True}, {'status': 'failed'}, {'metrics_source': 'none'},
                   {'scope_revision': 'bad'}, {'timestamp': 'no-date'}, {'timestamp': '2026-10-09T12:00:00'},
                   {'urls_count': -1}, {'urls_count': True}, {'urls_count': 2 ** 53},
                   {'stages_executed': ['probe']}, {'stage_results': {}},
                   {'stage_results': {'urls': {'status': 'completed', 'urls_count': 1}}},
                   {'stage_results': {'urls': {'status': 'completed', 'urls_count': '1', 'js_files_count': 0}}}]
        for change in changes:
            with self.subTest(change=change):
                self.assertIsNone(result_summary(dict(raw, **change), 'fixture', 'urls', 'completed', False))
        for final in ['cancelled', 'interrupted', 'simulated', 'blocked']:
            self.assertIsNone(result_summary(raw, 'fixture', 'urls', final, False))
        self.assertIsNone(result_summary(raw, 'fixture', 'urls', 'completed', True))

    def test_failed_and_blocked_results_mark_previous_metrics_and_do_not_retain_error_text(self):
        for final, kind in [('failed', 'technical'), ('blocked', 'scope_guard')]:
            raw = self.raw('fixture', status='failed')
            raw['stage_results']['urls']['failure_kind'] = kind
            value = result_summary(raw, 'fixture', 'urls', final, False)
            self.assertEqual(value['metrics_source'], 'previous_artifacts')
            self.assertEqual(value['stages'][0]['counts'], {})
            self.assertEqual(value['stages'][0]['failure_kind'], kind)
            self.assertNotIn('private-error', json.dumps(value))

    def test_full_and_partial_pipeline_keep_order_and_only_known_pattern_counts(self):
        raw = self.raw('fixture')
        raw['stage_results'] = {name: dict(status='completed', **{key: 2 for key in counts})
                                for name, counts in STAGE_COUNTS.items()}
        raw['stage_results']['patterns']['patterns'] = {name: 1 for name in PATTERNS}
        raw['stage_results']['patterns']['patterns']['secret-pattern'] = 99
        raw['stages_executed'] = list(STAGE_COUNTS)
        value = result_summary(raw, 'fixture', 'all', 'completed', False)
        self.assertEqual([step['stage'] for step in value['stages']], list(STAGE_COUNTS))
        self.assertEqual(value['stages'][-1]['patterns'], {name: 1 for name in PATTERNS})
        raw['stages_executed'].reverse()
        self.assertIsNone(result_summary(raw, 'fixture', 'all', 'completed', False))
        raw.update(status='failed', metrics_source='previous_artifacts', stages_executed=['subdomains', 'probe'])
        raw['stage_results'] = {'subdomains': raw['stage_results']['subdomains'],
                                'probe': {'status': 'failed', 'failure_kind': 'scope_guard', 'error': 'private'}}
        value = result_summary(raw, 'fixture', 'all', 'blocked', False)
        self.assertEqual(value['stages'][0]['counts']['in_scope_count'], 2)
        self.assertEqual(value['stages'][1]['counts'], {})

    def resumed_raw(self, run_id):
        raw = self.raw(run_id)
        raw['stage_results'] = {name: dict(status='completed', execution='current', origin_run_id=run_id,
                                         **{key: 2 for key in counts}) for name, counts in STAGE_COUNTS.items()}
        raw['stage_results']['patterns']['patterns'] = {name: 1 for name in PATTERNS}
        raw['stage_results']['subdomains'].update(execution='recovered', origin_run_id='a' * 32)
        raw['stages_executed'] = ['probe', 'urls', 'patterns']
        raw['stages_recovered'] = ['subdomains']
        return raw

    def test_resumed_origin_survives_history_reopening_and_later_legacy_jobs(self):
        job = self.store.begin(self.key, 'all', False)
        raw = self.resumed_raw(job['run_id'])
        raw['stage_results']['subdomains']['private'] = 'https://user:password@example.test/private'
        value = result_summary(raw, job['run_id'], 'all', 'completed', False)
        self.assertEqual(value['schema_version'], 2)
        self.assertEqual(value['stages'][0]['execution'], 'recovered')
        self.assertEqual(value['stages'][0]['origin_run_id'], 'a' * 32)
        self.assertEqual(value['stages'][1]['origin_run_id'], job['run_id'])
        self.store.finish(self.key, job['run_id'], 'completed', scope_revision='a' * 64, result_summary=value)
        self.finish(count=7)
        jobs = ReconJobStore(self.db).history(self.key)['jobs']
        self.assertEqual(jobs[1]['result_summary'], value)
        self.assertEqual(jobs[0]['result_summary']['schema_version'], 1)
        self.assertNotIn('password', json.dumps(jobs))

    def test_origin_validation_rejects_malformed_forged_current_and_inconsistent_recovery(self):
        raw = self.resumed_raw('b' * 32)
        edits = [lambda r: r['stage_results']['probe'].update(origin_run_id='a' * 32),
                 lambda r: r['stage_results']['subdomains'].update(origin_run_id=True),
                 lambda r: r['stage_results']['subdomains'].update(origin_run_id='b' * 32),
                 lambda r: r['stage_results']['subdomains'].update(origin_run_id='private/path'),
                 lambda r: r['stage_results']['urls'].update(execution='recovered'),
                 lambda r: r.update(stages_recovered=[]),
                 lambda r: r.update(stages_executed=list(STAGE_COUNTS)),
                 lambda r: r['stage_results']['probe'].pop('origin_run_id')]
        for edit in edits:
            changed = copy.deepcopy(raw)
            edit(changed)
            self.assertIsNone(result_summary(changed, 'b' * 32, 'all', 'completed', False))
        raw['stage_results']['subdomains']['origin_run_id'] = None
        self.assertIsNone(result_summary(raw, 'b' * 32, 'urls', 'completed', False))
        self.assertIsNotNone(result_summary(raw, 'b' * 32, 'all', 'completed', False))
        for invalid in (None, True, 'private/path'):
            self.assertIsNone(result_summary(self.resumed_raw(invalid), invalid, 'all', 'completed', False))

    def test_failed_resumed_run_keeps_recovered_origin_and_current_failure_separate(self):
        raw = self.resumed_raw('b' * 32)
        raw.update(status='failed', metrics_source='previous_artifacts', stages_executed=['probe'])
        raw['stage_results'] = {name: raw['stage_results'][name] for name in ('subdomains', 'probe')}
        raw['stage_results']['probe'].update(status='failed', failure_kind='scope_guard')
        value = result_summary(raw, 'b' * 32, 'all', 'blocked', False)
        self.assertEqual(value['stages'][0]['execution'], 'recovered')
        self.assertEqual(value['stages'][1]['execution'], 'current')
        self.assertEqual(value['stages'][1]['counts'], {})

    def artifact_raw(self, run_id):
        raw = self.raw(run_id)
        raw['stages_recovered'] = []
        raw['stage_results']['urls'].update(execution='current', origin_run_id=run_id)
        raw['stage_artifacts'] = {'urls': {'status': 'recorded', 'refs': [
            {'path': 'recon/urls_all.txt', 'sha256': 'c' * 64, 'size': 9},
            {'path': 'recon/js_files.txt', 'sha256': 'd' * 64, 'size': 0}]}}
        return raw

    def test_artifact_versions_survive_reopening_backup_and_later_legacy_run(self):
        job = self.store.begin(self.key, 'urls', False)
        raw = self.artifact_raw(job['run_id'])
        value = result_summary(raw, job['run_id'], 'urls', 'completed', False)
        self.assertEqual(value['schema_version'], 3)
        self.store.finish(self.key, job['run_id'], 'completed', scope_revision='a' * 64, result_summary=value)
        self.finish(count=8)
        jobs = ReconJobStore(self.db).history(self.key)['jobs']
        self.assertEqual(jobs[1]['result_summary']['stages'][0]['artifact_capture'], raw['stage_artifacts']['urls'])
        with closing(self.store.connect()) as source, closing(sqlite3.connect(self.root / 'backup.db')) as target:
            source.backup(target)
        self.assertEqual(ReconJobStore(self.root / 'backup.db').history(self.key)['jobs'], jobs)
        self.assertNotIn('password', json.dumps(jobs))

    def test_artifact_capture_rejects_paths_inventories_hashes_sizes_and_failed_claims(self):
        raw = self.artifact_raw('b' * 32)
        edits = [lambda r: r['stage_artifacts']['urls']['refs'][0].update(path='../private'),
                 lambda r: r['stage_artifacts']['urls']['refs'][0].update(sha256='secret'),
                 lambda r: r['stage_artifacts']['urls']['refs'][0].update(size=True),
                 lambda r: r['stage_artifacts']['urls']['refs'][0].update(size=32*1024*1024+1),
                 lambda r: r['stage_artifacts']['urls']['refs'][0].update(private='secret'),
                 lambda r: r['stage_artifacts']['urls']['refs'].reverse(),
                 lambda r: r['stage_artifacts']['urls']['refs'].pop(),
                 lambda r: r['stage_artifacts'].update(probe={'status': 'unavailable', 'refs': []}),
                 lambda r: r.update(stage_artifacts={}),
                 lambda r: r['stage_artifacts']['urls'].update(status='unavailable'),
                 lambda r: r['stage_artifacts']['urls'].update(status='invented'),
                 lambda r: r.update(stages_recovered=['urls'])]
        for edit in edits:
            changed = copy.deepcopy(raw); edit(changed)
            self.assertIsNone(result_summary(changed, 'b' * 32, 'urls', 'completed', False))
        raw.update(status='failed', metrics_source='previous_artifacts')
        raw['stage_results']['urls'].update(status='failed', failure_kind='technical')
        self.assertIsNone(result_summary(raw, 'b' * 32, 'urls', 'failed', False))
        raw['stage_artifacts'] = {}
        value = result_summary(raw, 'b' * 32, 'urls', 'failed', False)
        self.assertIsNone(value['stages'][0]['artifact_capture'])

    def test_artifact_capture_budget_recovered_origin_and_unavailable_manual_stage(self):
        raw = self.resumed_raw('b' * 32)
        from app.core.artifact_snapshot import RECON_STAGE_ARTIFACTS, HASH_LIMIT
        raw['stage_artifacts'] = {name: {'status': 'recorded', 'refs': [
            {'path': 'recon/' + path, 'sha256': 'c' * 64, 'size': 1} for path in paths]}
            for name, paths in RECON_STAGE_ARTIFACTS.items()}
        value = result_summary(raw, 'b' * 32, 'all', 'completed', False)
        self.assertEqual(value['stages'][0]['origin_run_id'], 'a' * 32)
        self.assertLess(len(json.dumps(value)), 16384)
        raw['stage_artifacts']['subdomains']['refs'][0]['size'] = HASH_LIMIT
        self.assertIsNone(result_summary(raw, 'b' * 32, 'all', 'completed', False))
        raw = self.artifact_raw('b' * 32)
        raw['stage_artifacts']['urls'] = {'status': 'unavailable', 'refs': []}
        self.assertIsNotNone(result_summary(raw, 'b' * 32, 'urls', 'completed', False))

    def test_result_and_job_finalization_are_atomic_and_stale_completion_cannot_replace_results(self):
        job = self.store.begin(self.key, 'urls', False)
        value = result_summary(self.raw(job['run_id']), job['run_id'], 'urls', 'completed', False)
        with self.store.connect() as conn:
            conn.execute("CREATE TRIGGER reject_result BEFORE INSERT ON recon_job_results BEGIN SELECT RAISE(ABORT, 'fixture'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.finish(self.key, job['run_id'], 'completed', scope_revision='a' * 64, result_summary=value)
        self.assertEqual(self.store.get(self.key)['status'], 'running')
        self.assertEqual(self.store.history(self.key)['jobs'][0]['status'], 'running')
        with self.store.connect() as conn:
            conn.execute('DROP TRIGGER reject_result')
        self.store.finish(self.key, job['run_id'], 'completed', scope_revision='a' * 64, result_summary=value)
        later, _ = self.finish(count=5)
        altered = copy.deepcopy(value)
        altered['metrics']['urls_count'] = 99
        self.store.finish(self.key, job['run_id'], 'completed', scope_revision='a' * 64, result_summary=altered)
        self.assertEqual(self.store.history(self.key)['jobs'][1]['result_summary'], value)
        self.assertEqual(self.store.get(self.key)['run_id'], later)

    def test_corrupt_results_are_unavailable_and_deletion_is_scoped_to_project_type(self):
        first, value = self.finish()
        other, _ = self.finish(('reto', 'fixture'))
        for corrupt in ['{broken', '[]', json.dumps(dict(value, run_id=other)), json.dumps(dict(value, commands=['private'])), ' ' * 16385]:
            with self.store.connect() as conn:
                conn.execute('UPDATE recon_job_results SET result_summary=? WHERE engagement_type=? AND engagement_id=?', (corrupt, *self.key))
            self.assertIsNone(self.store.history(self.key)['jobs'][0]['result_summary'])
        self.store.delete(self.key)
        self.assertEqual(self.store.history(self.key)['jobs'], [])
        self.assertIsNotNone(self.store.history(('reto', 'fixture'))['jobs'][0]['result_summary'])

    def test_worker_retains_own_summary_once_and_does_not_attach_it_to_later_jobs(self):
        target = self.root / 'workspace/engagements/fixture'
        target.mkdir(parents=True)
        with patch.object(module, 'WORKSPACE_DIR', self.root / 'workspace'):
            service = module.ReconService(self.db)
            service.startup()
            self.addCleanup(service.shutdown)
            pipeline = self.root / 'pipeline.py'
            service.pipeline_script = pipeline
            def run(raw, dry_run=False):
                script = 'import os,json,pathlib,sys\n'
                if raw is not None:
                    script += 'data=' + repr(raw) + '\ndata["run_id"]=os.environ["SECLAB_RECON_RUN_ID"]\n'
                    script += 'p=pathlib.Path(sys.argv[2])/"recon/summary.json"\np.write_text(json.dumps(data))\n'
                pipeline.write_text(script)
                started = service.run_pipeline('fixture', 'urls', dry_run)
                self.assertTrue(started['success'])
                deadline = time.monotonic() + 5
                while service.store.get(self.key)['status'] == 'running' and time.monotonic() < deadline:
                    threading.Event().wait(.01)
                self.assertIn(service.store.get(self.key)['status'], ['completed', 'simulated'])
                return started['job']['run_id']
            first = run(self.raw('replaced', 2))
            second = run(self.raw('replaced', 4))
            run(None, True)
            jobs = service.get_history('fixture')['jobs']
            self.assertIsNone(jobs[0]['result_summary'])
            self.assertEqual(jobs[1]['run_id'], second)
            self.assertEqual(jobs[2]['run_id'], first)
            self.assertEqual([job['result_summary']['metrics']['urls_count'] for job in jobs[1:]], [4, 2])
            (target / 'recon/summary.json').write_text('{broken')
            self.assertEqual(module.ReconService(self.db).get_history('fixture')['jobs'], jobs)
