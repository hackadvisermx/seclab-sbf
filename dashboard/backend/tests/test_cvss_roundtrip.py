import pathlib
import tempfile
import unittest
from app.api.endpoints.findings import calculate_cvss_score
from app.models.schemas import FindingCreate
from app.services.workspace_sync import WorkspaceSyncService


class TestCvssRoundTrip(unittest.TestCase):
    def test_known_base_vectors_and_severity(self):
        cases = [
            ('N L N N U N N N', 0.0, 'INFO'),
            ('N L N N C N N N', 0.0, 'INFO'),
            ('N L N N U H H H', 9.8, 'CRITICAL'),
            ('N L N N C H H H', 10.0, 'CRITICAL'),
            ('N L L N U L L N', 5.4, 'MEDIUM'),
            ('N L N R C L L N', 6.1, 'MEDIUM'),
            ('P H H R U L N N', 1.6, 'LOW'),
        ]
        for values, score, severity in cases:
            payload = dict(zip(('AV','AC','PR','UI','S','C','I','A'), values.split()))
            with self.subTest(payload=payload):
                result = calculate_cvss_score(payload)
                self.assertEqual(result['score'], score)
                self.assertEqual(result['severity'], severity)
                self.assertEqual(result['vector'], 'CVSS:3.1/' + '/'.join(f'{k}:{v}' for k,v in payload.items()))

    def test_zero_survives_create_read_edit_and_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            service = WorkspaceSyncService(pathlib.Path(directory))
            service.create_engagement('fixture')
            calculated = calculate_cvss_score(dict(AV='N', AC='L', PR='N', UI='N', S='U', C='N', I='N', A='N'))
            saved = service.save_finding('fixture', FindingCreate(slug='zero', title='Zero', cvss_score=calculated['score'],
                                      cvss_vector=calculated['vector'], severity=calculated['severity']))
            edited = service.save_finding('fixture', FindingCreate(slug='zero', title='Zero edited', body=saved.body,
                                      cvss_score=saved.frontmatter.cvss_score, cvss_vector=saved.frontmatter.cvss_vector,
                                      severity=saved.frontmatter.severity))
            self.assertEqual(edited.frontmatter.cvss_score, 0.0)
            self.assertEqual(edited.frontmatter.severity, 'INFO')
            self.assertEqual(edited.frontmatter.cvss_vector, calculated['vector'])
            self.assertEqual(service.list_findings('fixture')[0].frontmatter.cvss_score, 0.0)
