import datetime
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from app.services.workspace_sync import WorkspaceSyncService


class TestLootIdentity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service = WorkspaceSyncService(pathlib.Path(self.temp.name))
        self.service.create_engagement('fixture')

    def test_many_creations_at_same_timestamp_remain_distinct(self):
        with patch('app.services.workspace_sync.datetime.datetime') as clock:
            clock.now.return_value = datetime.datetime(2026, 10, 7)
            rows = [self.service.save_loot_credential('fixture', {'username': f'user-{i}'}) for i in range(30)]
        stored = self.service.get_loot('fixture')['credentials']
        self.assertEqual(len(stored), 30)
        self.assertEqual(len({r['id'] for r in rows}), 30)
        self.assertEqual([r['username'] for r in stored], [f'user-{i}' for i in range(30)])

    def test_legacy_id_update_and_delete_preserve_other_rows(self):
        self.service.save_loot_credential('fixture', {'id': 'cred-1700000000', 'username': 'old'})
        other = self.service.save_loot_credential('fixture', {'username': 'other'})
        self.service.save_loot_credential('fixture', {'id': 'cred-1700000000', 'username': 'updated'})
        rows = self.service.get_loot('fixture')['credentials']
        self.assertEqual([r['username'] for r in rows], ['updated', 'other'])
        self.assertTrue(self.service.delete_loot_credential('fixture', 'cred-1700000000'))
        self.assertEqual(self.service.get_loot('fixture')['credentials'], [other])

    def test_write_failure_does_not_return_success(self):
        with patch('app.services.workspace_sync.json.dump', side_effect=OSError('fixture disk error')):
            with self.assertRaises(OSError):
                self.service.save_loot_credential('fixture', {'username': 'fixture'})
