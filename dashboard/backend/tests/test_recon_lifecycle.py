import os
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
