from contextlib import closing
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('dashboard_backup', Path(__file__).resolve().parents[1] / 'host/dashboard-backup.py')
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class DashboardBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ws = self.root / 'workspace'
        self.state = self.root / 'dashboard'
        self.ws.mkdir()
        self.state.mkdir()
        (self.ws / 'retos/demo').mkdir(parents=True)
        (self.ws / 'retos/demo/evidence.md').write_text('fixture local')
        (self.state / '.vault.key').write_bytes(bytes(range(32)))
        (self.state / '.vault.key').chmod(0o600)
        (self.state / 'recon-jobs.db.lock').touch()
        with closing(sqlite3.connect(self.state / 'vault.db')) as conn, conn:
            conn.executescript("CREATE TABLE dashboard_sessions (token_hash TEXT); INSERT INTO dashboard_sessions VALUES ('fixture'); CREATE TABLE dashboard_settings (value TEXT); INSERT INTO dashboard_settings VALUES ('preservado');")
        with closing(sqlite3.connect(self.state / 'recon-jobs.db')) as conn, conn:
            conn.executescript("CREATE TABLE recon_jobs (status TEXT); INSERT INTO recon_jobs VALUES ('completed');")
        self.dest = self.root / 'backups'

    def make_backup(self):
        return backup.backup(self.ws, self.state, self.dest)

    def targets(self):
        return self.root / 'restored-workspace', self.root / 'restored-state'

    def test_round_trip_key_settings_jobs_permissions_and_sessions_revoked(self):
        archive = self.make_backup()
        ws, state = self.targets()
        with patch.object(os, 'geteuid', return_value=1000):
            backup.restore(ws, state, archive)
        self.assertEqual((ws / 'retos/demo/evidence.md').read_text(), 'fixture local')
        self.assertEqual((state / '.vault.key').read_bytes(), bytes(range(32)))
        self.assertEqual((state / '.vault.key').stat().st_mode & 0o777, 0o600)
        self.assertEqual(archive.stat().st_mode & 0o777, 0o600)
        with closing(sqlite3.connect(state / 'vault.db')) as conn, conn:
            self.assertEqual(conn.execute('SELECT * FROM dashboard_sessions').fetchall(), [])
            self.assertEqual(conn.execute('SELECT * FROM dashboard_settings').fetchall(), [('preservado',)])
        with closing(sqlite3.connect(state / 'recon-jobs.db')) as conn, conn:
            self.assertEqual(conn.execute('SELECT * FROM recon_jobs').fetchall(), [('completed',)])

    def test_wal_committed_data_is_preserved(self):
        conn = sqlite3.connect(self.state / 'vault.db')
        self.addCleanup(conn.close)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute("INSERT INTO dashboard_settings VALUES ('wal')")
        conn.commit()
        archive = self.make_backup()
        with tarfile.open(archive) as tar:
            data = tar.extractfile('dashboard/vault.db').read()
        target = self.root / 'snapshot.db'
        target.write_bytes(data)
        with closing(sqlite3.connect(target)) as snapshot, snapshot:
            self.assertEqual(snapshot.execute('SELECT count(*) FROM dashboard_settings').fetchone(), (2,))

    def test_missing_key_invalid_key_and_corrupt_database_fail_closed(self):
        (self.state / '.vault.key').unlink()
        with self.assertRaises(ValueError):
            self.make_backup()
        (self.state / '.vault.key').write_bytes(b'invalid')
        (self.state / '.vault.key').chmod(0o600)
        with self.assertRaises(ValueError):
            self.make_backup()
        (self.state / '.vault.key').write_bytes(bytes(range(32)))
        (self.state / 'vault.db').write_bytes(b'corrupt')
        with self.assertRaises(sqlite3.DatabaseError):
            self.make_backup()

    def test_links_special_files_and_nested_destination_rejected(self):
        (self.ws / 'link').symlink_to(self.state / '.vault.key')
        with self.assertRaises(ValueError):
            self.make_backup()
        (self.ws / 'link').unlink()
        os.mkfifo(self.ws / 'fifo')
        with self.assertRaises(ValueError):
            self.make_backup()
        (self.ws / 'fifo').unlink()
        with self.assertRaises(ValueError):
            backup.backup(self.ws, self.state, self.ws / 'backups')

    def test_checksum_required_and_tampering_does_not_write_targets(self):
        archive = self.make_backup()
        checksum = Path(str(archive) + '.sha256')
        checksum.unlink()
        with self.assertRaises(ValueError):
            backup.restore(*self.targets(), archive)
        checksum.write_text('invalid')
        with self.assertRaises(ValueError):
            backup.restore(*self.targets(), archive)
        self.assertFalse(self.targets()[0].exists())

    def test_existing_target_preserved(self):
        archive = self.make_backup()
        ws, state = self.targets()
        ws.mkdir()
        (ws / 'keep').write_text('original')
        with self.assertRaises(ValueError):
            backup.restore(ws, state, archive)
        self.assertEqual((ws / 'keep').read_text(), 'original')

    def malicious(self, name, link=False):
        archive = self.dest / 'malicious.tar.gz'
        self.dest.mkdir(mode=0o700)
        with tarfile.open(archive, 'w:gz') as tar:
            member = tarfile.TarInfo(name)
            if link:
                member.type = tarfile.SYMTYPE
                member.linkname = '/etc/passwd'
            else:
                member.size = 1
            tar.addfile(member, None if link else io.BytesIO(b'x'))
        archive.chmod(0o600)
        Path(str(archive) + '.sha256').write_text(backup.digest(archive) + '  ' + archive.name + '\n')
        return archive

    def test_tar_path_traversal_rejected_even_with_matching_checksum(self):
        archive = self.malicious('workspace/../../escape')
        with self.assertRaises(ValueError):
            backup.restore(*self.targets(), archive)
        self.assertFalse((self.root / 'escape').exists())

    def test_tar_symlink_rejected(self):
        archive = self.malicious('workspace/link', True)
        with self.assertRaises(ValueError):
            backup.restore(*self.targets(), archive)

    def test_manifest_detects_payload_change(self):
        archive = self.make_backup()
        altered = self.dest / 'altered.tar.gz'
        with tarfile.open(archive) as source, tarfile.open(altered, 'w:gz') as output:
            for member in source:
                if member.name == 'workspace/retos/demo/evidence.md':
                    member.size = 3
                    output.addfile(member, io.BytesIO(b'bad'))
                else:
                    output.addfile(member, source.extractfile(member) if member.isfile() else None)
        altered.chmod(0o600)
        Path(str(altered) + '.sha256').write_text(backup.digest(altered) + '  ' + altered.name + '\n')
        with self.assertRaises(ValueError):
            backup.restore(*self.targets(), altered)

    def test_active_container_rejected_before_mounts(self):
        with patch.object(backup, 'docker_json', return_value=[{'State': {'Running': True}}]):
            with self.assertRaises(ValueError):
                backup.offline_mounts('fixture')

    def test_shared_volume_writer_rejected(self):
        info = {'State': {'Running': False}, 'Image': 'sha256:fixture', 'Mounts': [
            {'Destination': '/workspace', 'Type': 'bind', 'Source': '/fixture'},
            {'Destination': '/var/lib/seclab', 'Type': 'volume', 'Name': 'fixture-state'}]}
        other = {'Mounts': [{'Type': 'volume', 'Name': 'fixture-state'}]}
        with patch.object(backup, 'docker_json', side_effect=[[info], [other]]), patch.object(backup.subprocess, 'check_output', return_value='other'):
            with self.assertRaises(ValueError):
                backup.offline_mounts('fixture')

    def test_restore_rolls_back_on_move_failure(self):
        archive = self.make_backup()
        real_move = backup.shutil.move
        calls = []
        def failing_move(source, target):
            calls.append(source)
            if len(calls) == 2:
                raise OSError('fixture failure')
            return real_move(source, target)
        with patch.object(backup.shutil, 'move', side_effect=failing_move):
            with self.assertRaises(OSError):
                backup.restore(*self.targets(), archive)
        for target in self.targets():
            self.assertFalse(target.exists() and any(target.iterdir()))


if __name__ == '__main__':
    unittest.main()
