import hashlib
import pathlib
import tempfile
import unittest
import uuid
from unittest.mock import patch
import yaml
from app.models.schemas import FindingCreate
from app.services.workspace_sync import WorkspaceSyncService, FindingUpdateError


class TestFindingIdentity(unittest.TestCase):
    def current_version(self, slug):
        path = self.service._resolve_dir('identity') / 'evidence' / (slug + '.md')
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = WorkspaceSyncService(pathlib.Path(self.tmp.name))
        self.service.create_engagement('identity', domain='example.test')
        self.root = self.service._resolve_dir('identity')

    def create(self, slug='first'):
        return self.service.save_finding('identity', FindingCreate(slug=slug, title='Original'))

    def test_identity_survives_edit_rename_and_reopen(self):
        created = self.create()
        first = self.service.get_finding("identity", "first")
        self.assertEqual(first.finding_id, created.finding_id)
        ident = first.finding_id
        self.assertEqual(uuid.UUID(hex=ident).version, 4)
        second = self.create('second')
        self.assertNotEqual(second.finding_id, ident)
        self.service.save_finding('identity', FindingCreate(slug='first', title='Edited', body=first.body, finding_id=ident, expected_source_sha256=self.current_version('first')))
        path = self.root / 'evidence/first.md'
        path.rename(path.with_name('renamed.md'))
        reopened = WorkspaceSyncService(pathlib.Path(self.tmp.name)).get_finding('identity', 'renamed')
        self.assertEqual(reopened.finding_id, ident)
        self.assertEqual(reopened.frontmatter.title, 'Edited')
        self.assertEqual(reopened.body, first.body)

    def test_legacy_reads_do_not_rewrite_and_first_edit_assigns_once(self):
        path = self.root / 'evidence/legacy.md'
        path.write_text('---\nid: VULN-42\ntitle: Legacy\nstatus: CANDIDATE\n---\nbody')
        before = path.read_bytes()
        self.assertIsNone(self.service.get_finding('identity', 'legacy').finding_id)
        self.assertEqual(path.read_bytes(), before)
        edited = self.service.save_finding('identity', FindingCreate(slug='legacy', title='Legacy', body='body', expected_source_sha256=self.current_version('legacy')))
        self.assertEqual(uuid.UUID(hex=edited.finding_id).version, 4)
        metadata = yaml.safe_load(path.read_text().split('---\n')[1])
        self.assertEqual(metadata['id'], 'VULN-42')
        edited_again = self.service.save_finding('identity', FindingCreate(slug='legacy', title='Again', body='body', expected_source_sha256=self.current_version('legacy')))
        self.assertEqual(edited_again.finding_id, edited.finding_id)

    def test_replacement_stale_identity_corruption_and_duplicate_block_without_writes(self):
        original = self.create()
        path = self.root / 'evidence/first.md'
        for invalid in (uuid.uuid4().hex, 'bad', ''):
            before = path.read_bytes()
            with self.assertRaises(FindingUpdateError):
                self.service.save_finding('identity', FindingCreate(slug='first', title='Replace', body=original.body, finding_id=invalid, expected_source_sha256=self.current_version('first')))
            self.assertEqual(path.read_bytes(), before)
        duplicate = path.with_name('duplicate.md')
        duplicate.write_bytes(path.read_bytes())
        before = path.read_bytes()
        with self.assertRaises(FindingUpdateError):
            self.service.save_finding('identity', FindingCreate(slug='first', title='Ambiguous', body=original.body, expected_source_sha256=self.current_version('first')))
        self.assertEqual(path.read_bytes(), before)
        duplicate.unlink()
        path.write_text(path.read_text().replace(original.finding_id, 'bad'))
        self.assertIsNotNone(self.service.get_finding('identity', 'first').identity_error)
        before = path.read_bytes()
        with self.assertRaises(FindingUpdateError):
            self.service.save_finding('identity', FindingCreate(slug='first', title='Corrupt', body=original.body, expected_source_sha256=self.current_version('first')))
        self.assertEqual(path.read_bytes(), before)
        with self.assertRaises(FindingUpdateError):
            self.service.save_finding('identity', FindingCreate(slug='import', title='Chosen', finding_id=uuid.uuid4().hex))

    def test_concurrent_creator_cannot_replace_an_existing_identity(self):
        path = self.root / 'evidence/race.md'
        competing = '---\ntitle: Concurrent\nfinding_id: ' + uuid.uuid4().hex + '\n---\noriginal'
        def race(source, destination):
            pathlib.Path(destination).write_text(competing)
            raise FileExistsError('concurrent creator')
        with patch('app.services.workspace_sync.os.link', side_effect=race):
            with self.assertRaises(FindingUpdateError):
                self.create('race')
        self.assertEqual(path.read_text(), competing)
        self.assertEqual(list(path.parent.glob('.*.tmp')), [])
