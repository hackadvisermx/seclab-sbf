import importlib.machinery
import importlib.util
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = (pathlib.Path(os.environ['FINDING_SCRIPTS']) if os.environ.get('FINDING_SCRIPTS')
           else pathlib.Path(__file__).resolve().parents[2] / 'scripts')


def load_script(name):
    path = SCRIPTS / (name + '.py')
    if not path.is_file():
        path = SCRIPTS / ('pt-next' if name == 'pt-audit-next' else name)
    loader = importlib.machinery.SourceFileLoader(name.replace('-', '_'), str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


context = load_script('pt-agent-context')
checklist = load_script('pt-audit-checklist')
audit_next = load_script('pt-audit-next')
packer = load_script('pt-engagement-packer')
read_finding_source = getattr(context, 'read_finding_source', None)


class FindingSourceLinksTests(unittest.TestCase):
    def test_nonregular_fifo_is_rejected_without_waiting_for_a_writer(self):
        with tempfile.TemporaryDirectory() as temporary:
            evidence = pathlib.Path(temporary) / 'evidence'
            evidence.mkdir()
            pipe = evidence / 'blocked.md'
            os.mkfifo(pipe)
            with self.assertRaises(OSError):
                read_finding_source(pipe)

    def test_external_finding_link_is_never_adopted_by_context_or_decisions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            project = root / 'engagement'
            evidence = project / 'evidence'
            evidence.mkdir(parents=True)
            (project / 'target.yaml').write_text('scope:\n  in_scope:\n    domains: [example.test]\n')
            (project / 'REPORT.md').write_text('Previous report\n')
            outside = root / 'private.md'
            original = ('---\nid: PRIVATE\ntitle: Private title\nasset: private.test\n'
                        'status: PROVEN\nseverity: HIGH\n---\nPRIVATE BODY\n')
            outside.write_text(original, encoding='utf-8')
            (evidence / 'linked.md').symlink_to(outside)

            rows = context.collect_findings(project)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['status'], 'UNINTERPRETED')
            self.assertEqual(rows[0]['source_error'], 'linked_source')
            self.assertNotIn('PRIVATE', str(rows))
            self.assertNotIn('private.test', str(rows))

            checklist_rows = checklist.AuditChecklistEvaluator(project).collect_evidence_findings()
            self.assertEqual(len(checklist_rows), 1)
            self.assertEqual(checklist_rows[0]['status'], 'UNINTERPRETED')
            self.assertNotIn('PRIVATE', str(checklist_rows))

            steps = audit_next.determine_roadmap(project)
            self.assertTrue(any(step['id'] == 'verify_findings' for step in steps))
            ready, blocking, _ = packer.check_closure_readiness(project)
            self.assertFalse(ready)
            self.assertTrue(any('hallazgos sin verificar' in issue for issue in blocking))
            original_is_file = pathlib.Path.is_file
            with patch.object(packer.pathlib.Path, 'is_file', autospec=True,
                              side_effect=lambda path: False if path.name.startswith('pt-audit-checklist')
                              else original_is_file(path)):
                ready, blocking, _ = packer.check_closure_readiness(project)
            self.assertFalse(ready)
            self.assertTrue(any('hallazgos sin verificar' in issue for issue in blocking))
            self.assertEqual(outside.read_text(encoding='utf-8'), original)

    def test_linked_evidence_directory_is_rejected_without_reading_private_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            outside = root / 'outside'
            outside.mkdir()
            (outside / 'private.md').write_text('---\ntitle: PRIVATE\nstatus: PROVEN\n---\n')
            project = root / 'engagement'
            project.mkdir()
            (project / 'evidence').symlink_to(outside, target_is_directory=True)
            if read_finding_source is not None:
                with self.assertRaises((OSError, ValueError)):
                    read_finding_source(project / 'evidence' / 'private.md')
            rows = context.collect_findings(project)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['status'], 'UNINTERPRETED')
            self.assertEqual(rows[0]['source_error'], 'linked_source')
            self.assertNotIn('PRIVATE', str(rows))


if __name__ == '__main__':
    unittest.main()
