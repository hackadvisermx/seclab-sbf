import importlib.machinery
import importlib.util
import os
import pathlib
import tempfile
import unittest


SCRIPTS = (pathlib.Path(os.environ['CONTEXT_SCRIPTS']) if os.environ.get('CONTEXT_SCRIPTS')
           else pathlib.Path(__file__).resolve().parents[2] / 'scripts')
CONTEXT_FILE = SCRIPTS / 'pt-agent-context.py'
if not CONTEXT_FILE.is_file():
    CONTEXT_FILE = SCRIPTS / 'pt-agent-context'
loader = importlib.machinery.SourceFileLoader('agent_context', str(CONTEXT_FILE))
spec = importlib.util.spec_from_loader(loader.name, loader)
context = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context)


class ContextFindingSourceTests(unittest.TestCase):
    def test_duplicate_metadata_is_visible_without_adopting_either_value(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = pathlib.Path(temporary) / 'fixture'
            evidence = project / 'evidence'
            evidence.mkdir(parents=True)
            (project / 'target.yaml').write_text('scope:\n  in_scope:\n    domains: [example.test]\n')
            for extra in ('status: CANDIDATE', 'asset: other.test', 'severity: LOW',
                          'title: Otro titulo', 'id: OTHER'):
                with self.subTest(extra=extra):
                    source = evidence / 'finding.md'
                    original = ('---\nid: VULN-1\ntitle: Original\nasset: example.test\n'
                                'status: PROVEN\nseverity: HIGH\n' + extra + '\n---\n'
                                '# Cuerpo privado\n')
                    source.write_text(original, encoding='utf-8')
                    findings = context.collect_findings(project)
                    self.assertEqual(len(findings), 1)
                    finding = findings[0]
                    self.assertEqual(finding['file'], 'finding.md')
                    self.assertEqual(finding['status'], 'UNINTERPRETED')
                    self.assertEqual(finding['severity'], 'UNKNOWN')
                    self.assertEqual(finding['asset'], 'N/A')
                    self.assertEqual(finding['source_error'], 'duplicate_metadata')
                    self.assertNotIn('Original', str(finding))
                    self.assertNotIn('other.test', str(finding))
                    data = context.generate_context_dict(project)
                    self.assertEqual(data['findings']['severity_counts']['UNKNOWN'], 1)
                    self.assertFalse(data['coverage']['ready_for_closure'])
                    self.assertFalse(data['readiness']['ready_for_closure'])
                    markdown = context.format_markdown_context(data)
                    self.assertIn('Sin interpretar: 1', markdown)
                    self.assertIn('evidence/finding.md', markdown)
                    self.assertNotIn('PROVEN', markdown)
                    self.assertNotIn('other.test', markdown)
                    self.assertEqual(source.read_text(encoding='utf-8'), original)

    def test_unreadable_source_is_visible_without_raw_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = pathlib.Path(temporary)
            evidence = project / 'evidence'
            evidence.mkdir()
            source = evidence / 'broken.md'
            source.write_bytes(b'\xffstatus: PROVEN')
            findings = context.collect_findings(project)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]['status'], 'UNINTERPRETED')
            self.assertEqual(findings[0]['source_error'], 'unreadable')
            self.assertEqual(source.read_bytes(), b'\xffstatus: PROVEN')


if __name__ == '__main__':
    unittest.main()
