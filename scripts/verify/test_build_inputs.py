import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('build_inputs', ROOT / 'scripts/build-inputs.py')
inputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inputs)


class BuildInputsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        for directory in inputs.FULL_DIRS:
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        for name in inputs.BASE_FILES + inputs.FULL_FILES:
            self.write(name, 'fixture')

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
        return path

    def hashes(self):
        return tuple(inputs.build_hash(self.root, profile) for profile in ('base', 'full'))

    def test_frontend_backend_and_workspace_edits_preserve_base_hash(self):
        previous = self.hashes()
        for name in ('dashboard/frontend/src/App.vue', 'dashboard/frontend/vite.config.js',
                     'dashboard/frontend/package-lock.json', 'dashboard/backend/app/config.py',
                     'workspace-seed/templates/target.yaml', 'workspace-seed/data/fixture.txt'):
            self.write(name, 'changed')
            current = self.hashes()
            self.assertEqual(current[0], previous[0])
            self.assertNotEqual(current[1], previous[1], name)
            previous = current

    def test_base_change_updates_both_hashes(self):
        previous = self.hashes()
        self.write('scripts/entrypoint/base-entrypoint.sh', 'changed')
        current = self.hashes()
        self.assertNotEqual(current[0], previous[0])
        self.assertNotEqual(current[1], previous[1])

    def test_generated_assets_runtime_data_and_secrets_do_not_trigger_builds(self):
        previous = self.hashes()
        for name in ('dashboard/frontend/dist/stale.js', 'dashboard/frontend/node_modules/example/index.js',
                     'dashboard/backend/data/vault.db', 'dashboard/backend/app/__pycache__/app.pyc',
                     'dashboard/frontend/.env.local', 'dashboard/backend/.env'):
            self.write(name, 'must-not-enter-source-hash')
        self.assertEqual(self.hashes(), previous)

    def test_file_rename_or_executable_mode_affects_hash(self):
        path = self.write('scripts/helper.sh', 'same bytes')
        previous = self.hashes()
        path.chmod(0o755)
        self.assertNotEqual(self.hashes()[1], previous[1])
        previous = self.hashes()
        path.rename(path.with_name('other.sh'))
        self.assertNotEqual(self.hashes()[1], previous[1])

    def test_missing_or_symbolic_input_fails_instead_of_returning_partial_hash(self):
        (self.root / 'Makefile').unlink()
        with self.assertRaises(ValueError):
            inputs.build_hash(self.root, 'full')
        self.write('Makefile', 'fixture')
        outside = self.write('outside', 'private fixture')
        (self.root / 'scripts/linked').symlink_to(outside)
        with self.assertRaises(ValueError):
            inputs.build_hash(self.root, 'full')


if __name__ == '__main__':
    unittest.main(verbosity=2)
