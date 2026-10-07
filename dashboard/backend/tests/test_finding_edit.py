import pathlib
import tempfile
import unittest
from unittest.mock import patch
import yaml
from app.models.schemas import FindingCreate
from app.services.workspace_sync import WorkspaceSyncService, FindingUpdateError


class TestFindingEdit(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service = WorkspaceSyncService(pathlib.Path(self.temp.name))
        self.service.create_engagement('fixture')
        self.path = self.service._resolve_dir('fixture') / 'evidence/legacy.md'
        self.metadata = {'title': 'Original --- título', 'status': 'PROVEN', 'severity': 'HIGH', 'date': '2025-01-01',
                         'author': 'auditora', 'id': 'VULN-42', 'owasp': 'A01', 'custom': {'nested': ['kept']},
                         'cvss_v31': 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H'}
        self.body = '## Descripción\nOriginal\n\n## Control negativo\nPrueba personalizada\n\n```http\nGET / HTTP/1.1\n```\n\n## Remediación\nCorrección real'
        self.path.write_text('---\n' + yaml.safe_dump(self.metadata, allow_unicode=True) + '---\n\n' + self.body)
        self.path.chmod(0o600)

    def test_round_trip_and_title_change_preserve_body_and_unknown_metadata(self):
        for title in ('Original --- título', 'Nuevo título', 'Nuevo título'):
            original = self.service.get_finding('fixture', 'legacy')
            self.service.save_finding('fixture', FindingCreate(slug='legacy', title=title, body=original.body))
            result = self.service.get_finding('fixture', 'legacy')
            meta = yaml.safe_load(self.path.read_text().split('---\n')[1])
            self.assertEqual(result.body, self.body)
            self.assertEqual(meta, dict(self.metadata, title=title))
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_structured_update_cannot_overwrite_existing_markdown(self):
        before = self.path.read_bytes()
        with self.assertRaises(FindingUpdateError):
            self.service.save_finding('fixture', FindingCreate(slug='legacy', title='new', description='partial'))
        self.assertEqual(self.path.read_bytes(), before)

    def test_failed_atomic_write_keeps_original(self):
        before = self.path.read_bytes()
        with patch.object(pathlib.Path, 'replace', side_effect=OSError('fixture disk failure')):
            with self.assertRaises(OSError):
                self.service.save_finding('fixture', FindingCreate(slug='legacy', title='new', body='new body'))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob('.*.tmp')), [])

    def test_invalid_frontmatter_fails_closed(self):
        for text in ('---\ntitle: [\n---\nbody', '---\n- list\n---\nbody', '---\nunterminated'):
            self.path.write_text(text)
            with self.assertRaises(FindingUpdateError):
                self.service.save_finding('fixture', FindingCreate(slug='legacy', title='new', body='new'))
            self.assertEqual(self.path.read_text(), text)
