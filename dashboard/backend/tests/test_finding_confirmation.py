import hashlib
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.endpoints import findings
from app.models.schemas import FindingCreate
from app.services.workspace_sync import WorkspaceSyncService, FindingUpdateError, ScopeValidationError


class TestFindingConfirmation(unittest.TestCase):
    def current_version(self, slug):
        path = self.service._resolve_dir('fixture') / 'evidence' / (slug + '.md')
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.service = WorkspaceSyncService(pathlib.Path(temporary.name))
        self.service.create_engagement('fixture', domain='example.test')
        self.root = self.service._resolve_dir('fixture')
        self.artifact = self.root / 'recon/raw.txt'
        self.artifact.write_bytes(b'Fixture HTTP')
        self.reference = {'path': 'recon/raw.txt', 'sha256': hashlib.sha256(b'Fixture HTTP').hexdigest()}
        self.valid = {'slug': 'confirmed', 'title': 'Fixture', 'asset': 'example.test', 'status': 'PROVEN',
                      'artifact_refs': [self.reference], 'verification_rationale': 'Operador revisó respuesta y control sintéticos'}

    def test_confirmation_requires_asset_refs_rationale_and_scope_for_every_alias(self):
        for status in ['PROVEN', 'VERIFIED', ' confirmado ']:
            for invalid in [{'asset': ''}, {'asset': 'outside.test'}, {'artifact_refs': []},
                            {'verification_rationale': None}, {'verification_rationale': '   '}]:
                with self.subTest(status=status, invalid=invalid), self.assertRaises(FindingUpdateError):
                    self.service.save_finding('fixture', FindingCreate(**dict(self.valid, status=status, **invalid)))
                self.assertFalse((self.root / 'evidence/confirmed.md').exists())
        (self.root / 'target.yaml').write_text('scope: [')
        with self.assertRaises(FindingUpdateError):
            self.service.save_finding('fixture', FindingCreate(**self.valid))

    def test_confirmation_preserves_review_on_omission_and_revalidates_unchanged_refs(self):
        for status in ['PROVEN', 'VERIFIED', 'CONFIRMADO']:
            (self.root / 'evidence/confirmed.md').unlink(missing_ok=True)
            detail = self.service.save_finding('fixture', FindingCreate(**dict(self.valid, status=status)))
            edited = self.service.save_finding('fixture', FindingCreate(slug=detail.slug, title='Edit', body=detail.body, expected_source_sha256=self.current_version(detail.slug)))
            self.assertEqual(edited.verification_rationale, self.valid['verification_rationale'])
            self.assertEqual(edited.artifact_refs, [self.reference])
            self.assertIsNone(edited.confirmation_error)
        path = self.root / 'evidence/confirmed.md'
        prior = path.read_bytes()
        self.artifact.write_bytes(b'Changed')
        with self.assertRaises(FindingUpdateError):
            self.service.save_finding('fixture', FindingCreate(slug=detail.slug, title='Bad edit', body=detail.body, expected_source_sha256=self.current_version(detail.slug)))
        self.assertEqual(path.read_bytes(), prior)

    def test_legacy_is_readable_and_requires_repair_or_explicit_demotion_without_data_loss(self):
        path = self.root / 'evidence/legacy.md'
        original = '---\ntitle: Legacy\nstatus: PROVEN\nauthor: auditora\n---\nOriginal body'
        path.write_text(original)
        detail = self.service.get_finding('fixture', 'legacy')
        self.assertEqual(detail.frontmatter.status, 'PROVEN')
        self.assertIsNotNone(detail.confirmation_error)
        self.assertEqual(self.service.list_findings('fixture')[0].body, 'Original body')
        self.assertEqual(path.read_text(), original)
        with self.assertRaises(FindingUpdateError):
            self.service.save_finding('fixture', FindingCreate(slug='legacy', title='Edit', body=detail.body, expected_source_sha256=self.current_version('legacy')))
        changed = self.service.save_finding('fixture', FindingCreate(slug='legacy', title='Edit', body=detail.body, status='CANDIDATE', expected_source_sha256=self.current_version('legacy')))
        self.assertEqual(changed.body, 'Original body')
        self.assertEqual(changed.frontmatter.author, 'auditora')
        self.assertIsNone(changed.confirmation_error)

    def test_api_rejects_incomplete_confirmation_without_overwriting_and_accepts_valid_review(self):
        app = FastAPI()
        app.include_router(findings.router)
        with patch.object(findings, 'workspace_service', self.service), TestClient(app) as client:
            created = client.post('/findings/fixture', json=dict(self.valid, status='CANDIDATE', artifact_refs=[], verification_rationale=''))
            self.assertEqual(created.status_code, 200)
            detail = client.get('/findings/fixture/confirmed').json()
            path = self.root / 'evidence/confirmed.md'
            before = path.read_bytes()
            rejected = client.post('/findings/fixture', json={'slug': detail['slug'], 'title': 'Edit', 'body': detail['body'], 'expected_source_sha256': detail['source_sha256'], 'status': 'VERIFIED'})
            self.assertEqual(rejected.status_code, 409)
            self.assertEqual(path.read_bytes(), before)
            accepted = client.post('/findings/fixture', json=dict(self.valid, body=detail['body'], expected_source_sha256=detail['source_sha256']))
            self.assertEqual(accepted.status_code, 200, accepted.text)
            self.assertEqual(accepted.json()['verification_rationale'], self.valid['verification_rationale'])
            self.assertEqual(accepted.json()['body'], detail['body'])

    def test_scope_changes_missing_scope_and_unavailable_validator_block_existing_confirmation(self):
        detail = self.service.save_finding('fixture', FindingCreate(**self.valid))
        path = self.root / 'evidence/confirmed.md'
        prior = path.read_bytes()
        scope = self.root / 'target.yaml'
        scope.unlink()
        with self.assertRaises(FindingUpdateError):
            self.service.save_finding('fixture', FindingCreate(slug=detail.slug, title='Edit', body=detail.body, expected_source_sha256=self.current_version(detail.slug)))
        scope.write_text('scope:\n  in_scope:\n    domains: [example.test]\n  out_of_scope:\n    domains: [example.test]\n')
        with self.assertRaises(FindingUpdateError):
            self.service.save_finding('fixture', FindingCreate(slug=detail.slug, title='Edit', body=detail.body, expected_source_sha256=self.current_version(detail.slug)))
        with patch('app.services.workspace_sync._scope_module', side_effect=ScopeValidationError('Validador no disponible')):
            with self.assertRaises(FindingUpdateError):
                self.service.save_finding('fixture', FindingCreate(slug=detail.slug, title='Edit', body=detail.body, expected_source_sha256=self.current_version(detail.slug)))
        self.assertEqual(path.read_bytes(), prior)

    def test_api_rejects_invalid_rationale_for_candidates_without_writing(self):
        app = FastAPI()
        app.include_router(findings.router)
        with patch.object(findings, 'workspace_service', self.service), TestClient(app) as client:
            payload = dict(self.valid, status='CANDIDATE', artifact_refs=[], verification_rationale='bad\0text')
            self.assertEqual(client.post('/findings/fixture', json=payload).status_code, 409)
            path = self.root / 'evidence/confirmed.md'
            self.assertFalse(path.exists())
            payload['verification_rationale'] = 'Revisión: "á"\nComparé con control sintético.'
            created = client.post('/findings/fixture', json=payload)
            self.assertEqual(created.status_code, 200, created.text)
            prior = path.read_bytes()
            self.assertEqual(client.get('/findings/fixture/confirmed').json()['verification_rationale'], payload['verification_rationale'])
            rejected = client.post('/findings/fixture', json=dict(payload, body=created.json()['body'], expected_source_sha256=created.json()['source_sha256'], verification_rationale='bad\0text'))
            self.assertEqual(rejected.status_code, 409)
            self.assertEqual(path.read_bytes(), prior)
