import pathlib
import tempfile
import unittest
from app.services.workspace_sync import WorkspaceSyncService, ScopeValidationError


class TestAuthorizationScope(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = WorkspaceSyncService(pathlib.Path(temporary.name) / 'workspace')
        self.workspace.create_engagement('fixture', domain='example.test')

    def test_new_project_does_not_assume_any_operational_permission(self):
        data = self.workspace.get_target_yaml('fixture')
        self.assertFalse(data['authorization']['allow_active'])
        self.assertFalse(data['authorization']['allow_passive'])
        self.assertEqual(data['authorization']['reference'], '')
        self.assertEqual(data['authorization']['valid_until'], '')

    def test_valid_authorization_roundtrips_without_expanding_scope(self):
        data = self.workspace.get_target_yaml('fixture')
        data['authorization'] = {'reference': 'fixture-only', 'valid_from': '2000-01-01T00:00:00Z',
                                 'valid_until': '2099-01-01T00:00:00Z',
                                 'allow_passive': True, 'allow_active': False}
        expected_scope = data['scope']
        self.workspace.save_target_yaml('fixture', data)
        stored = self.workspace.get_target_yaml('fixture')
        self.assertEqual(stored['authorization'], data['authorization'])
        self.assertEqual(stored['scope'], expected_scope)

    def test_invalid_or_partial_authorization_cannot_overwrite_configuration(self):
        path = self.workspace._resolve_dir('fixture') / 'target.yaml'
        original = path.read_bytes()
        for supplied in [{'allow_active': True}, {'allow_active': 'true'},
                         {'reference': 'fixture', 'allow_active': True, 'valid_from': 'bad', 'valid_until': 'bad'},
                         {'unknown_permission': True}]:
            with self.subTest(supplied=supplied):
                data = self.workspace.get_target_yaml('fixture')
                data['authorization'] = supplied
                with self.assertRaises(ScopeValidationError):
                    self.workspace.save_target_yaml('fixture', data)
                self.assertEqual(path.read_bytes(), original)
        with self.assertRaises(ScopeValidationError):
            self.workspace.save_target_yaml('fixture', {'authorization': {'allow_active': True}})
        self.assertEqual(path.read_bytes(), original)
