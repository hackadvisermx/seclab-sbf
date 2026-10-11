import importlib.machinery
import importlib.util
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = (pathlib.Path(os.environ['CHECKLIST_SCRIPTS']) if os.environ.get('CHECKLIST_SCRIPTS')
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


checklist = load_script('pt-audit-checklist')
audit_next = load_script('pt-audit-next')
packer = load_script('pt-engagement-packer')


class ChecklistMetadataParityTests(unittest.TestCase):
    def test_repeated_literal_metadata_stays_uninterpreted_across_advisory_consumers(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = pathlib.Path(temporary) / 'engagement'
            evidence = project / 'evidence'
            evidence.mkdir(parents=True)
            (project / 'target.yaml').write_text('scope:\n  in_scope:\n    domains: [example.test]\n')
            (project / 'REPORT.md').write_text('Previous report\n')
            source = evidence / 'finding.md'
            for extra in ('id: OTHER', 'title: Private title', 'severity: LOW',
                          'asset: private.test', 'status: CANDIDATE'):
                with self.subTest(extra=extra):
                    original = ('---\nid: VULN-1\ntitle: Original\nseverity: HIGH\n'
                                'asset: example.test\nstatus: PROVEN\n' + extra + '\n---\n'
                                '## 2. Pasos\nBody status: PROVEN is not metadata.\n')
                    source.write_text(original, encoding='utf-8')
                    rows = checklist.AuditChecklistEvaluator(project).collect_evidence_findings()
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0]['status'], 'UNINTERPRETED')
                    self.assertEqual(rows[0]['id'], 'finding')
                    self.assertEqual(rows[0]['source_error'], 'duplicate_metadata')
                    self.assertNotIn('PRIVATE', str(rows))
                    self.assertNotIn('private.test', str(rows))
                    self.assertFalse(checklist.AuditChecklistEvaluator(project).evaluate()['readiness']['ready_for_closure'])
                    self.assertTrue(any(step['id'] == 'verify_findings'
                                        for step in audit_next.determine_roadmap(project)))
                    self.assertFalse(packer.check_closure_readiness(project)[0])
                    original_is_file = pathlib.Path.is_file
                    with patch.object(packer.pathlib.Path, 'is_file', autospec=True,
                                      side_effect=lambda path: False if path.name.startswith('pt-audit-checklist')
                                      else original_is_file(path)):
                        self.assertFalse(packer.check_closure_readiness(project)[0])
                    self.assertEqual(source.read_text(encoding='utf-8'), original)

            valid = ('---\nid: VULN-1\ntitle: Original\nseverity: HIGH\n'
                     'asset: example.test\nstatus: "PROVEN" # review\n---\n'
                     'Body status: CANDIDATE is not metadata.\n')
            source.write_text(valid, encoding='utf-8')
            rows = checklist.AuditChecklistEvaluator(project).collect_evidence_findings()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['status'], 'PROVEN')
            self.assertNotIn('source_error', rows[0])
            self.assertEqual(source.read_text(encoding='utf-8'), valid)


if __name__ == '__main__':
    unittest.main()
