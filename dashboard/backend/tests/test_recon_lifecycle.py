import os
import json
import pathlib
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from app.services import recon_service as module
from app.core.recon_jobs import ReconJobStore


class TestReconLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.db = self.root / 'state/jobs.db'
        self.target = self.root / 'workspace/engagements/fixture'
        self.target.mkdir(parents=True)
        self.patch = patch.object(module, 'WORKSPACE_DIR', self.root / 'workspace')
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.service = module.ReconService(self.db)
        self.addCleanup(self.service.shutdown)
        self.service.startup()
        self.pipeline = self.root / 'pipeline.py'
        self.service.pipeline_script = self.pipeline
        self.pipeline.write_text('import sys\nprint("fixture complete", flush=True)\nsys.exit(0)\n')
        self.key = ('engagement', 'fixture')

    def wait_for(self, predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if predicate():
                return
            threading.Event().wait(.01)
        self.fail('Timed out waiting for fixture')

    def test_worker_history_retains_revision_only_for_its_own_summary(self):
        revision = 'a' * 64
        self.pipeline.write_text('import os,json,pathlib,sys\n'
            'p=pathlib.Path(sys.argv[2])/"recon"/"summary.json"\n'
            'p.write_text(json.dumps({"run_id":os.environ["SECLAB_RECON_RUN_ID"],"scope_revision":"' + revision + '"}))\n')
        self.service.run_pipeline('fixture')
        self.wait_for(lambda: self.service.store.get(self.key)['status'] == 'completed')
        first = self.service.store.get(self.key)['run_id']
        self.pipeline.write_text('print("fixture without a new summary")\n')
        self.service.run_pipeline('fixture', dry_run=True)
        self.wait_for(lambda: self.service.store.get(self.key)['status'] == 'simulated')
        jobs = self.service.get_history('fixture')['jobs']
        self.assertEqual(len(jobs), 2)
        self.assertIsNone(jobs[0]['scope_revision'])
        self.assertEqual(jobs[1]['run_id'], first)
        self.assertEqual(jobs[1]['scope_revision'], revision)

    def test_progress_is_visible_while_running_and_never_reuses_another_run(self):
        self.pipeline.write_text('import os,json,pathlib,time\n'
            'p=pathlib.Path(__import__("sys").argv[2])/"recon"/"progress.json"\n'
            'p.write_text(json.dumps({"run_id":os.environ["SECLAB_RECON_RUN_ID"],"command":"fixture --slow","recent_output":["first"],"events":[]}))\n'
            'print("first",flush=True)\ntime.sleep(2)\n')
        self.assertTrue(self.service.run_pipeline('fixture')['success'])
        self.wait_for(lambda: self.service.get_status('fixture')['progress'] is not None and 'first' in self.service.get_log('fixture'))
        status = self.service.get_status('fixture')
        self.assertEqual(status['job']['status'], 'running')
        self.assertEqual(status['progress']['command'], 'fixture --slow')
        self.assertIn('first', self.service.get_log('fixture'))
        path = self.target / 'recon/progress.json'
        path.write_text(json.dumps({'run_id': 'another-run', 'command': 'stale'}))
        self.assertIsNone(self.service.get_status('fixture')['progress'])
        path.write_text('{broken')
        self.assertIsNone(self.service.get_status('fixture')['progress'])

    def test_worker_records_scope_block_only_for_matching_failed_summary(self):
        cases = [(1, 'scope_guard', 'failed', True, 'Falta permiso activo', 'blocked'),
                 (1, 'technical', 'failed', True, 'Falta herramienta', 'failed'),
                 (1, 'scope_guard', 'failed', False, 'Error antiguo', 'failed'),
                 (0, 'scope_guard', 'failed', True, 'Error inesperado', 'completed'),
                 (1, 'scope_guard', 'completed', True, 'Inconsistente', 'failed'),
                 (1, 'scope_guard', 'failed', True, None, 'failed')]
        for code, kind, outcome_status, matches, reason, expected in cases:
            with self.subTest(expected=expected, code=code, matches=matches, kind=kind):
                self.pipeline.write_text('import os,json,pathlib,sys\n'
                    'p=pathlib.Path(sys.argv[2])/"recon"/"summary.json"\n'
                    'data=' + repr({'status': outcome_status, 'failure_kind': kind, 'error': reason}) + '\n'
                    'data["run_id"]=' + ('os.environ["SECLAB_RECON_RUN_ID"]' if matches else '"old-run"') + '\n'
                    'p.write_text(json.dumps(data))\n'
                    f'sys.exit({code})\n')
                self.assertTrue(self.service.run_pipeline('fixture')['success'])
                self.wait_for(lambda: self.service.store.get(self.key)['status'] == expected)
                job = self.service.store.get(self.key)
                self.assertEqual(job['error'], reason if expected == 'blocked' else (f'Código de salida: {code}' if code else None))
                self.assertEqual(self.service.get_history('fixture')['jobs'][0]['status'], expected)
        reopened = module.ReconService(self.db).get_history('fixture')['jobs']
        self.assertTrue(any(j['status'] == 'blocked' and j['error'] == 'Falta permiso activo' for j in reopened))

    def test_completion_simulation_failure_survive_service_recreation(self):
        for dry_run, code, expected in ((False, 0, 'completed'), (True, 0, 'simulated'), (False, 7, 'failed')):
            self.pipeline.write_text(f'import sys\nprint("fixture", flush=True)\nsys.exit({code})\n')
            self.assertTrue(self.service.run_pipeline('fixture', dry_run=dry_run)['success'])
            self.wait_for(lambda: self.service.store.get(self.key)['status'] == expected)
            job = module.ReconService(self.db).get_status('fixture')['job']
            self.assertEqual(job['status'], expected)
            self.assertEqual(job['dry_run'], dry_run)
            self.assertTrue(job['finished_at'])
            self.assertEqual(job['error'], 'Código de salida: 7' if code else None)

    def test_recovery_never_resumes_or_signals_persisted_jobs(self):
        completed = self.service.store.begin(('reto', 'fixture'), 'urls', False)
        self.service.store.finish(('reto', 'fixture'), completed['run_id'], 'completed')
        pending = self.service.store.begin(self.key, 'probe', False)
        self.service.store.request_cancel(self.key)
        self.service.shutdown()
        restored = module.ReconService(self.db)
        with patch.object(module.subprocess, 'Popen') as launch, patch.object(module.os, 'killpg') as kill:
            restored.startup()
            job = restored.get_status('fixture')['job']
            self.assertEqual(job['status'], 'interrupted')
            self.assertEqual(job['started_at'], pending['started_at'])
            self.assertTrue(job['finished_at'])
            self.assertEqual(restored.store.get(('reto', 'fixture'))['status'], 'completed')
            launch.assert_not_called()
            kill.assert_not_called()
            restored.shutdown()

    def test_live_owner_prevents_false_interruption(self):
        self.service.store.begin(self.key, 'all', False)
        other = module.ReconService(self.db)
        with self.assertRaises(BlockingIOError):
            other.startup()
        self.assertEqual(self.service.store.get(self.key)['status'], 'running')

    def test_pipeline_keeps_owner_lease_after_dashboard_descriptor_closes(self):
        self.pipeline.write_text('import pathlib, signal, sys, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\npathlib.Path(sys.argv[2], "ready").touch()\ntime.sleep(60)\n')
        self.service.run_pipeline('fixture')
        self.wait_for((self.target / 'ready').exists)
        os.close(self.service._lease)
        self.service._lease = None
        restored = module.ReconService(self.db)
        with self.assertRaises(BlockingIOError):
            restored.startup()
        self.assertEqual(self.service.store.get(self.key)['status'], 'running')
        self.service.cancel_pipeline('fixture')
        self.wait_for(lambda: self.service.store.get(self.key)['status'] == 'cancelled')
        restored.startup()
        self.assertEqual(restored.store.get(self.key)['status'], 'cancelled')
        restored.shutdown()

    def test_old_completion_cannot_overwrite_new_run(self):
        old = self.service.store.begin(self.key, 'all', False)
        self.service.store.finish(self.key, old['run_id'], 'completed')
        new = self.service.store.begin(self.key, 'probe', False)
        self.service.store.finish(self.key, old['run_id'], 'failed', 'stale')
        self.assertEqual(self.service.store.get(self.key)['run_id'], new['run_id'])
        self.assertEqual(self.service.store.get(self.key)['status'], 'running')

    def test_cancel_before_launch_never_starts_process(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.endpoints import recon
        with patch.object(module.threading.Thread, 'start'):
            job = self.service.run_pipeline('fixture')['job']
        app = FastAPI()
        app.include_router(recon.router)
        with patch.object(recon, 'recon_service', self.service), TestClient(app) as client:
            response = client.post('/recon/fixture/cancel')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['job']['status'], 'cancelling')
        with patch.object(module.subprocess, 'Popen') as launch:
            self.service._execute_pipeline_worker(self.key, self.target, 'all', False,
                self.target / 'recon/recon.log', job['run_id'])
            launch.assert_not_called()
        self.service._threads.clear()
        self.assertEqual(self.service.store.get(self.key)['status'], 'cancelled')

    def test_cancel_kills_process_group_and_allows_new_run(self):
        self.pipeline.write_text('''import pathlib, signal, subprocess, sys, time
root = pathlib.Path(sys.argv[2])
signal.signal(signal.SIGTERM, signal.SIG_IGN)
code = "import pathlib,signal,sys,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);p=pathlib.Path(sys.argv[1]);\\nwhile True: p.write_text(str(time.monotonic()));time.sleep(.02)"
child = subprocess.Popen([sys.executable, '-c', code, str(root/'heartbeat')])
print('child ready', flush=True)
while True: time.sleep(.1)
''')
        job = self.service.run_pipeline('fixture')['job']
        heartbeat = self.target / 'heartbeat'
        self.wait_for(heartbeat.exists)
        self.assertFalse(self.service.run_pipeline('fixture')['success'])
        self.assertTrue(self.service.cancel_pipeline('fixture')['success'])
        self.wait_for(lambda: self.service.store.get(self.key)['status'] == 'cancelled')
        last = heartbeat.read_text()
        threading.Event().wait(.1)
        self.assertEqual(heartbeat.read_text(), last)
        self.assertFalse(self.service.cancel_pipeline('fixture')['success'])
        self.pipeline.write_text('print("next fixture", flush=True)\n')
        next_job = self.service.run_pipeline('fixture')['job']
        self.assertNotEqual(next_job['run_id'], job['run_id'])
        self.wait_for(lambda: self.service.store.get(self.key)['status'] == 'completed')

    def test_symlink_database_is_rejected(self):
        outside = self.root / 'outside'
        outside.write_text('preserve')
        link = self.root / 'linked.db'
        link.symlink_to(outside)
        with self.assertRaises(OSError):
            ReconJobStore(link)
        self.assertEqual(outside.read_text(), 'preserve')

    def test_shutdown_stops_worker_and_releases_owner_lease(self):
        # Keep the leader alive until KILL to exercise shutdown escalation and
        # lease release without relying on host-specific zombie signalling.
        self.pipeline.write_text('import pathlib, signal, sys, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\npathlib.Path(sys.argv[2], "ready").touch()\ntime.sleep(60)\n')
        self.service.run_pipeline('fixture')
        self.wait_for((self.target / 'ready').exists)
        self.service.shutdown()
        self.assertEqual(self.service.store.get(self.key)['status'], 'cancelled')
        self.assertFalse(self.service._processes)
        restored = module.ReconService(self.db)
        restored.startup()
        self.assertEqual(restored.store.get(self.key)['status'], 'cancelled')
        restored.shutdown()

    def test_stop_handles_gone_groups_but_preserves_permission_errors(self):
        from unittest.mock import Mock
        proc = Mock(pid=12345)
        with patch.object(module.os, 'killpg', side_effect=ProcessLookupError), \
                patch.object(module.threading.Event, 'wait'):
            self.service._stop_processes([proc])
        with patch.object(module.os, 'killpg', side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                self.service._stop_processes([proc])

    def test_cancelling_job_blocks_deletion(self):
        from app.services import workspace_sync
        self.service.store.begin(self.key, 'all', False)
        self.service.store.request_cancel(self.key)
        with patch.object(workspace_sync.workspace_service, 'delete_engagement') as delete:
            with self.assertRaises(RuntimeError):
                self.service.delete_engagement('fixture')
            delete.assert_not_called()

    def test_get_status_exposes_parsed_probe_results_and_skips_corrupt_lines(self):
        recon_dir = self.target / 'recon'
        recon_dir.mkdir()
        rows = [
            '{"host": "a.example.test", "url": "https://a.example.test", "address": "10.0.0.1", "status": "response", "http_status": 200, "location": null}',
            'esto no es json',
            '{"host": "b.example.test", "status": "blocked", "reason": "Endpoint excluido del alcance."}',
        ]
        (recon_dir / 'probe_observations.jsonl').write_text('\n'.join(rows) + '\n')
        status = self.service.get_status('fixture')
        self.assertEqual(len(status['probe_results']), 2)
        self.assertEqual(status['probe_results'][0]['host'], 'a.example.test')
        self.assertEqual(status['probe_results'][0]['http_status'], 200)
        self.assertEqual(status['probe_results'][1]['status'], 'blocked')

    def test_get_status_without_probe_observations_returns_empty_list(self):
        status = self.service.get_status('fixture')
        self.assertEqual(status['probe_results'], [])

    def test_cancel_api_missing_idle_and_type_validation(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.endpoints import recon
        app = FastAPI()
        app.include_router(recon.router)
        with patch.object(recon, 'recon_service', self.service), TestClient(app) as client:
            self.assertEqual(client.post('/recon/missing/cancel').status_code, 404)
            self.assertEqual(client.post('/recon/fixture/cancel').status_code, 409)
            self.assertEqual(client.post('/recon/fixture/cancel?type=bad').status_code, 422)
