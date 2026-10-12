"""Matriz extendida de pruebas unitarias para evaluador de alcance y normalizador."""
import importlib.util
import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / 'scripts'))

from seclab_scope import (
    ScopeError,
    normalize_target,
    is_ip,
    domain_matches,
    endpoint_matches,
    check_scope,
    validate_scope,
)

validator_spec = importlib.util.spec_from_file_location(
    'pt_scope_validator', REPO_ROOT / 'scripts' / 'pt-scope-validator.py'
)
validator_mod = importlib.util.module_from_spec(validator_spec)
validator_spec.loader.exec_module(validator_mod)
extract_candidate_targets = validator_mod.extract_candidate_targets
validate_text_against_scope = validator_mod.validate_text_against_scope


class TestSeclabScopeMatrix(unittest.TestCase):
    """Pruebas exhaustivas de matriz de casos de borde en alcance."""

    def test_idna_punycode_domain_matching(self):
        # Normalización bidireccional de dominios internacionales
        self.assertEqual(normalize_target('bücher.de'), 'xn--bcher-kva.de')
        self.assertEqual(normalize_target('XN--BCHER-KVA.DE'), 'xn--bcher-kva.de')
        self.assertEqual(normalize_target('испытание.рф'), 'xn--80akhbyknj4f.xn--p1ai')

        # Coincidencia exacta Unicode vs Punycode
        self.assertTrue(domain_matches('bücher.de', 'xn--bcher-kva.de'))
        self.assertTrue(domain_matches('xn--bcher-kva.de', 'bücher.de'))

        # Coincidencia con comodines IDNA
        self.assertTrue(domain_matches('shop.bücher.de', '*.xn--bcher-kva.de'))
        self.assertTrue(domain_matches('shop.xn--bcher-kva.de', '*.bücher.de'))
        self.assertTrue(domain_matches('deep.sub.bücher.de', '*.bücher.de'))

        # No coincidencia en dominios distintos
        self.assertFalse(domain_matches('other.de', 'xn--bcher-kva.de'))
        self.assertFalse(domain_matches('not-bücher.de', '*.bücher.de'))

    def test_strict_subdomain_boundaries(self):
        # Wildcard solo debe abarcar subdominios legítimos
        self.assertTrue(domain_matches('sub.target.local', '*.target.local'))
        self.assertTrue(domain_matches('deep.sub.target.local', '*.target.local'))

        # Rechazo estricto de sufijos colisionantes o subdominios invertidos
        self.assertFalse(domain_matches('faketarget.local', '*.target.local'))
        self.assertFalse(domain_matches('attacker-target.local', '*.target.local'))
        self.assertFalse(domain_matches('target.local.attacker.com', '*.target.local'))
        self.assertFalse(domain_matches('target.local', '*.target.local'))

        # Apex domain explícito
        self.assertTrue(domain_matches('target.local', 'target.local'))
        self.assertFalse(domain_matches('sub.target.local', 'target.local'))

    def test_ipv6_matrix_and_normalization(self):
        # Detección de IP con y sin corchetes
        self.assertTrue(is_ip('2001:db8::1'))
        self.assertTrue(is_ip('[2001:db8::1]'))
        self.assertTrue(is_ip('::1'))
        self.assertTrue(is_ip('fe80::1'))
        self.assertFalse(is_ip('example.com'))
        self.assertFalse(is_ip('2001:db8:::1'))

        # Normalización canónica (comprimido)
        self.assertEqual(normalize_target('2001:0db8:0000:0000:0000:0000:0000:0001'), '2001:db8::1')
        self.assertEqual(normalize_target('[2001:db8::1]'), '2001:db8::1')
        self.assertEqual(normalize_target('[2001:db8::1]:8080'), '2001:db8::1')
        self.assertEqual(normalize_target('::ffff:192.0.2.1'), '192.0.2.1')

        # Verificación en check_scope con CIDR IPv6
        scope_v6 = {
            'scope': {
                'in_scope': {
                    'cidrs': ['2001:db8::/32'],
                    'ips': ['fe80::1']
                },
                'out_of_scope': {
                    'ips': ['2001:db8::99']
                }
            }
        }
        verdict, reason = check_scope('2001:db8::1', scope_v6)
        self.assertEqual(verdict, 'IN_SCOPE')
        self.assertIn('2001:db8::/32', reason)

        # Uncompressed match
        verdict, _ = check_scope('2001:0db8:0000:0000:0000:0000:0000:0002', scope_v6)
        self.assertEqual(verdict, 'IN_SCOPE')

        # Precedencia de exclusión en IPv6
        verdict, _ = check_scope('2001:db8::99', scope_v6)
        self.assertEqual(verdict, 'OUT_OF_SCOPE')

        # IP exacta fuera de CIDR
        verdict, _ = check_scope('fe80::1', scope_v6)
        self.assertEqual(verdict, 'IN_SCOPE')

        # Fuera de alcance
        verdict, _ = check_scope('2001:cafe::1', scope_v6)
        self.assertEqual(verdict, 'UNKNOWN')

    def test_endpoint_matching_and_traversal_neutralization(self):
        # Puertos por defecto implícitos
        self.assertTrue(endpoint_matches('http://example.com:80/api', 'http://example.com/api'))
        self.assertTrue(endpoint_matches('http://example.com/api', 'http://example.com:80/api'))
        self.assertTrue(endpoint_matches('https://example.com:443/api', 'https://example.com/api'))

        # Esquema o puerto distinto no coincide
        self.assertFalse(endpoint_matches('https://example.com/api', 'http://example.com/api'))
        self.assertFalse(endpoint_matches('http://example.com:8080/api', 'http://example.com/api'))

        # Prefijo de rutas y subrutas
        self.assertTrue(endpoint_matches('http://example.com/api', 'http://example.com/api'))
        self.assertTrue(endpoint_matches('http://example.com/api/', 'http://example.com/api'))
        self.assertTrue(endpoint_matches('http://example.com/api/v1/users', 'http://example.com/api'))
        self.assertTrue(endpoint_matches('http://example.com/api?debug=1#test', 'http://example.com/api'))

        # Bloqueo de colisión por sufijo (/api-admin no es subruta de /api)
        self.assertFalse(endpoint_matches('http://example.com/api-admin', 'http://example.com/api'))
        self.assertFalse(endpoint_matches('http://example.com/api_v2', 'http://example.com/api'))

        # Neutralización crítica de path traversal escape
        self.assertFalse(endpoint_matches('http://example.com/api/../admin', 'http://example.com/api'))
        self.assertFalse(endpoint_matches('http://example.com/api/v1/../../secret', 'http://example.com/api'))

        # Coincidencia en raíz abarca rutas completas
        self.assertTrue(endpoint_matches('https://example.com/login', 'https://example.com'))
        self.assertTrue(endpoint_matches('https://example.com/admin/settings', 'https://example.com/'))

    def test_text_candidate_extraction_extended(self):
        sample_text = (
            "Se detectó tráfico hacia https://api.target.local:8443/v1/health y "
            "también a la IP 192.168.1.50 y al host bücher.de. "
            "Además el servidor IPv6 2001:db8::5 responde en [2001:db8::10]:80 y fe80::1."
        )
        candidates = extract_candidate_targets(sample_text)
        self.assertIn('https://api.target.local:8443/v1/health', candidates)
        self.assertIn('192.168.1.50', candidates)
        self.assertIn('bücher.de', candidates)
        self.assertIn('2001:db8::5', candidates)
        self.assertIn('2001:db8::10', candidates)
        self.assertIn('fe80::1', candidates)

        # Validación de texto contra scope
        scope = {
            'scope': {
                'in_scope': {
                    'domains': ['target.local', '*.target.local', 'bücher.de'],
                    'ips': ['192.168.1.50'],
                    'cidrs': ['2001:db8::/32']
                },
                'out_of_scope': {
                    'ips': ['fe80::1']
                }
            }
        }
        findings = validate_text_against_scope(sample_text, scope)
        out_targets = [f['target'] for f in findings if f['verdict'] == 'OUT_OF_SCOPE']
        self.assertIn('fe80::1', out_targets)
