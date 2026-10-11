import hashlib
import json
import pathlib
import sqlite3
import tempfile
import unittest
from app.models.schemas import FindingCreate
from app.services.workspace_sync import WorkspaceSyncService, FindingUpdateError


class TestFindingProvenance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws_dir = pathlib.Path(self.tmp.name) / 'workspace'
        self.db_path = pathlib.Path(self.tmp.name) / 'recon-jobs.db'
        self.service = WorkspaceSyncService(self.ws_dir, recon_db_path=self.db_path)
        self.service.create_engagement('test-proj', domain='example.test')
        self.target_dir = self.service._resolve_dir('test-proj')
        (self.target_dir / 'recon').mkdir(parents=True, exist_ok=True)
        self.art_file = self.target_dir / 'recon/live-hosts.txt'
        self.art_file.write_text('host1.example.test\n')
        self.art_hash = hashlib.sha256(self.art_file.read_bytes()).hexdigest()
        self.valid_job_id = 'a' * 32

    def init_db(self, jobs=True, with_results=True, stage='probe'):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS recon_job_history (
                engagement_type TEXT NOT NULL, engagement_id TEXT NOT NULL,
                run_id TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL,
                dry_run INTEGER NOT NULL, started_at TEXT NOT NULL,
                finished_at TEXT, error TEXT, scope_revision TEXT,
                origin TEXT NOT NULL, PRIMARY KEY (engagement_type, engagement_id, run_id))''')
            conn.execute('''CREATE TABLE IF NOT EXISTS recon_job_results (
                engagement_type TEXT NOT NULL, engagement_id TEXT NOT NULL,
                run_id TEXT NOT NULL, result_summary TEXT NOT NULL,
                PRIMARY KEY (engagement_type, engagement_id, run_id))''')
            if jobs:
                conn.execute(
                    "INSERT INTO recon_job_history VALUES (?, ?, ?, ?, ?, 0, ?, ?, NULL, ?, 'dashboard')",
                    ('engagement', 'test-proj', self.valid_job_id, 'completed', stage,
                     '2026-10-11T12:00:00Z', '2026-10-11T12:05:00Z', 'b' * 64)
                )
            if with_results:
                summary = {
                    'stages': [{
                        'stage': stage,
                        'artifact_capture': {
                            'refs': [{'path': 'recon/live-hosts.txt', 'sha256': self.art_hash, 'size': len('host1.example.test\n')}]
                        }
                    }]
                }
                conn.execute(
                    "INSERT INTO recon_job_results VALUES (?, ?, ?, ?)",
                    ('engagement', 'test-proj', self.valid_job_id, json.dumps(summary))
                )

    def test_finding_provenance_create_and_reload(self):
        self.init_db()
        created = self.service.save_finding('test-proj', FindingCreate(
            slug='vuln-1',
            title='Vuln With Provenance',
            source_job_id=self.valid_job_id,
            source_stage='probe',
            artifact_refs=[{'path': 'recon/live-hosts.txt', 'sha256': self.art_hash}]
        ))
        self.assertEqual(created.source_job_id, self.valid_job_id)
        self.assertEqual(created.source_stage, 'probe')
        self.assertIsNone(created.source_job_error)

        # Verify on-disk file
        file_path = self.target_dir / 'evidence/vuln-1.md'
        content = file_path.read_text(encoding='utf-8')
        self.assertIn(f"source_job_id: {self.valid_job_id}", content)
        self.assertIn("source_stage: probe", content)

        # Reload via get_finding and list_findings
        loaded = self.service.get_finding('test-proj', 'vuln-1')
        self.assertEqual(loaded.source_job_id, self.valid_job_id)
        self.assertEqual(loaded.source_stage, 'probe')
        self.assertEqual(loaded.frontmatter.source_job_id, self.valid_job_id)
        self.assertEqual(loaded.frontmatter.source_stage, 'probe')

    def test_invalid_source_job_id_format(self):
        for invalid_id in ('not-hex', '1234', 'a' * 31, 'g' * 32, ' ' + 'a' * 32):
            with self.subTest(invalid_id=invalid_id), self.assertRaises(FindingUpdateError):
                self.service.save_finding('test-proj', FindingCreate(
                    slug='bad-job',
                    title='Bad Job ID',
                    source_job_id=invalid_id
                ))

    def test_invalid_source_stage_format(self):
        for invalid_stage in ('stage with spaces', 'probe$', 'a' * 65):
            with self.subTest(invalid_stage=invalid_stage), self.assertRaises(FindingUpdateError):
                self.service.save_finding('test-proj', FindingCreate(
                    slug='bad-stage',
                    title='Bad Stage',
                    source_job_id=self.valid_job_id,
                    source_stage=invalid_stage
                ))

    def test_unknown_job_id_rejected_when_db_exists(self):
        self.init_db()
        unknown_id = 'f' * 32
        with self.assertRaises(FindingUpdateError) as ctx:
            self.service.save_finding('test-proj', FindingCreate(
                slug='unknown-job',
                title='Unknown Job',
                source_job_id=unknown_id,
                source_stage='probe'
            ))
        self.assertIn('El job de origen no existe en el historial', str(ctx.exception))

    def test_mismatched_stage_rejected(self):
        self.init_db(stage='probe')
        with self.assertRaises(FindingUpdateError) as ctx:
            self.service.save_finding('test-proj', FindingCreate(
                slug='mismatched-stage',
                title='Mismatched Stage',
                source_job_id=self.valid_job_id,
                source_stage='subdomains'
            ))
        self.assertIn('La etapa declarada (subdomains) no coincide con la etapa del job (probe)', str(ctx.exception))

    def test_mismatched_artifact_version_rejected(self):
        self.init_db(stage='probe')
        different_hash = '0' * 64
        # We need an actual file with that hash to pass artifact_refs validation
        tampered_file = self.target_dir / 'recon/tampered.txt'
        tampered_file.write_bytes(b'tampered')
        tampered_hash = hashlib.sha256(b'tampered').hexdigest()

        # Update db to have recon/tampered.txt with different hash
        with sqlite3.connect(self.db_path) as conn:
            summary = {
                'stages': [{
                    'stage': 'probe',
                    'artifact_capture': {
                        'refs': [{'path': 'recon/tampered.txt', 'sha256': '1' * 64, 'size': 8}]
                    }
                }]
            }
            conn.execute("UPDATE recon_job_results SET result_summary=? WHERE run_id=?", (json.dumps(summary), self.valid_job_id))

        with self.assertRaises(FindingUpdateError) as ctx:
            self.service.save_finding('test-proj', FindingCreate(
                slug='tampered-artifact',
                title='Tampered Artifact',
                source_job_id=self.valid_job_id,
                source_stage='probe',
                artifact_refs=[{'path': 'recon/tampered.txt', 'sha256': tampered_hash}]
            ))
        self.assertIn('no coincide con la registrada por el job', str(ctx.exception))

    def test_legacy_finding_without_job_origin(self):
        created = self.service.save_finding('test-proj', FindingCreate(
            slug='legacy-f',
            title='Legacy Finding'
        ))
        self.assertIsNone(created.source_job_id)
        self.assertIsNone(created.source_stage)
        self.assertIsNone(created.source_job_error)
        content = (self.target_dir / 'evidence/legacy-f.md').read_text(encoding='utf-8')
        self.assertNotIn('source_job_id', content)
        self.assertNotIn('source_stage', content)


if __name__ == '__main__':
    unittest.main()
