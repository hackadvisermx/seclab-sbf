#!/usr/bin/env python3
import copy
import hashlib
import importlib.util
import io
import pathlib
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


installer = load('ci_linters', ROOT/'scripts/install-ci-linters.py')
shell = load('ci_shell', ROOT/'scripts/verify/check-ci-shell.py')


class TestCILinters(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.cache = self.root/'cache'
        self.destination = self.root/'bin'
        self.data = b'fixture-not-executed'
        self.digest = hashlib.sha256(self.data).hexdigest()
        self.lock = {'schema_version': 1, 'tools': {
            name: {'version': 'fixture', 'assets': {'amd64': {
                'url': 'https://github.com/example/releases/download/v1/tool',
                'sha256': self.digest}}}
            for name in ('actionlint', 'hadolint', 'shellcheck')}}

    def install(self, offline=False):
        with patch('sys.stdout', new=io.StringIO()):
            installer.install(self.lock, 'amd64', self.cache, self.destination, offline)

    def test_verified_cache_runs_without_network_and_replaces_old_binary(self):
        with patch.object(installer, 'download', return_value=self.data) as download:
            self.install()
            self.assertEqual(download.call_count, 1)
        (self.destination/'actionlint').chmod(0o755)
        (self.destination/'actionlint').write_bytes(b'old')
        with patch.object(installer, 'download', side_effect=AssertionError('network')):
            self.install(offline=True)
        for name in self.lock['tools']:
            self.assertEqual((self.destination/name).read_bytes(), self.data)
            self.assertEqual((self.destination/name).stat().st_mode & 0o777, 0o555)

    def test_corrupt_cache_is_rejected_offline_and_repaired_only_after_verification(self):
        self.cache.mkdir()
        (self.cache/self.digest).write_bytes(b'corrupted')
        with patch.object(installer, 'download') as download:
            with self.assertRaisesRegex(ValueError, 'Cache'):
                self.install(offline=True)
            download.assert_not_called()
        with patch.object(installer, 'download', return_value=self.data):
            self.install()
        self.assertEqual((self.cache/self.digest).read_bytes(), self.data)

    def test_bad_download_does_not_install_or_replace_cache(self):
        self.cache.mkdir()
        (self.cache/self.digest).write_bytes(b'corrupted')
        with patch.object(installer, 'download', return_value=b'tampered'):
            with self.assertRaisesRegex(ValueError, 'Checksum'):
                self.install()
        self.assertEqual((self.cache/self.digest).read_bytes(), b'corrupted')
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_missing_offline_cache_does_not_download(self):
        with patch.object(installer, 'download', side_effect=AssertionError('network')):
            with self.assertRaisesRegex(ValueError, 'Cache'):
                self.install(offline=True)

    def test_cache_and_destination_links_are_rejected_without_writing_target(self):
        victim = self.root/'victim'
        victim.mkdir()
        for directory in (self.cache, self.destination):
            directory.symlink_to(victim, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'enlazado'):
                self.install()
            directory.unlink()
        self.cache.mkdir(exist_ok=True)
        target = victim/'original'
        target.write_bytes(b'untouched')
        (self.cache/self.digest).symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'enlazada'):
            self.install()
        self.assertEqual(target.read_bytes(), b'untouched')

    def test_archive_extracts_only_regular_pinned_member(self):
        for symlink in (False, True):
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode='w:gz') as archive:
                other = tarfile.TarInfo('../outside')
                other.size = len(self.data)
                archive.addfile(other, io.BytesIO(self.data))
                member = tarfile.TarInfo('bin/tool')
                if symlink:
                    member.type = tarfile.SYMTYPE
                    member.linkname = '../outside'
                    archive.addfile(member)
                else:
                    member.size = len(self.data)
                    archive.addfile(member, io.BytesIO(self.data))
            data = stream.getvalue()
            for tool in self.lock['tools'].values():
                tool['assets']['amd64'].update(sha256=hashlib.sha256(data).hexdigest(), member='bin/tool')
            with patch.object(installer, 'download', return_value=data):
                if symlink:
                    with self.assertRaisesRegex(ValueError, 'archivo'):
                        self.install()
                else:
                    self.install()
                    self.assertEqual((self.destination/'actionlint').read_bytes(), self.data)
            self.assertFalse((self.root/'outside').exists())

    def test_invalid_lock_or_pin_fails_before_network(self):
        with patch.object(installer, 'download', side_effect=AssertionError('network')):
            for change in ({'url': 'http://github.com/tool'}, {'url': 'https://github.com.evil/tool'}, {'sha256': '../file'}):
                original = copy.deepcopy(self.lock)
                self.lock['tools']['actionlint']['assets']['amd64'].update(change)
                with self.assertRaisesRegex(ValueError, 'Pin'):
                    self.install()
                self.lock = original
            self.lock['schema_version'] = 0
            with self.assertRaisesRegex(ValueError, 'Lock'):
                self.install()

    def test_oversized_cache_is_not_accepted(self):
        self.cache.mkdir()
        (self.cache/self.digest).write_bytes(self.data)
        with patch.object(installer, 'LIMIT', 4), patch.object(installer, 'download', side_effect=AssertionError('network')):
            with self.assertRaisesRegex(ValueError, 'Cache'):
                self.install(offline=True)

    def test_shell_selection_retains_recursive_names_and_executable_shebang(self):
        root = self.root/'scripts'
        nested = root/'nested'
        nested.mkdir(parents=True)
        expected = ['nested/with space.sh', '.bashrc', 'script.shlib', 'lab']
        for name in expected + ['ignore.py', 'plain', 'mvnw', 'fake.go']:
            path = root/name
            path.write_text('#!/usr/bin/env bash\ntrue\n')
            path.chmod(0o755 if name in {'lab', 'mvnw', 'fake.go'} else 0o644)
        (root/'linked.sh').symlink_to(root/'lab')
        (root/'.git').mkdir()
        (root/'.git/ignore.sh').write_text('true')
        self.assertEqual({str(path.relative_to(root)) for path in shell.shell_files(root)}, set(expected))


if __name__ == '__main__':
    unittest.main()
