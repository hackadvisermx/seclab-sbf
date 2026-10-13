#!/usr/bin/env python3
"""Pruebas unitarias para la detección de deriva DNS y re-validación en Scope Guard (seclab_scope)."""

import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from seclab_scope import (
    check_dns_drift,
    evaluate_engagement_dns_drift,
)


class TestSeclabDnsDrift(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = pathlib.Path(self.tmp.name)

        self.scope_data = {
            "scope": {
                "in_scope": {
                    "domains": ["api.target.local", "portal.target.local"],
                    "ips": ["192.168.1.10", "192.168.1.11"],
                    "cidrs": ["10.0.0.0/24"],
                },
                "out_of_scope": {
                    "domains": ["admin.target.local"],
                    "ips": ["10.0.0.99"],
                    "cidrs": ["172.16.0.0/16"],
                },
            }
        }

    def test_in_scope_stable_resolution(self):
        # Resolución inicial sin historial previo
        mock_res = lambda domain: ["192.168.1.10"]
        res = check_dns_drift(
            domain="api.target.local",
            scope_data=self.scope_data,
            known_ips=["192.168.1.10"],
            mock_resolver=mock_res,
        )
        self.assertEqual(res["status"], "IN_SCOPE_STABLE")
        self.assertTrue(res["is_in_scope"])
        self.assertFalse(res["has_drift"])
        self.assertEqual(res["resolved_ips"], ["192.168.1.10"])
        self.assertEqual(res["out_of_scope_ips"], [])

    def test_drift_detected_within_scope(self):
        # El dominio cambia de 192.168.1.10 a 10.0.0.5 (ambas están en in_scope)
        mock_res = lambda domain: ["10.0.0.5"]
        res = check_dns_drift(
            domain="api.target.local",
            scope_data=self.scope_data,
            known_ips=["192.168.1.10"],
            mock_resolver=mock_res,
        )
        self.assertEqual(res["status"], "DRIFT_WITHIN_SCOPE")
        self.assertTrue(res["is_in_scope"])
        self.assertTrue(res["has_drift"])
        self.assertEqual(res["added_ips"], ["10.0.0.5"])
        self.assertEqual(res["removed_ips"], ["192.168.1.10"])

    def test_out_of_scope_violation_via_cidr_or_unlisted(self):
        # El dominio resuelve a una IP fuera de alcance (e.g. 8.8.8.8 desconocida o 10.0.0.99 excluida)
        mock_res = lambda domain: ["10.0.0.99"]
        res = check_dns_drift(
            domain="api.target.local",
            scope_data=self.scope_data,
            known_ips=["192.168.1.10"],
            mock_resolver=mock_res,
        )
        self.assertEqual(res["status"], "OUT_OF_SCOPE_VIOLATION")
        self.assertFalse(res["is_in_scope"])
        self.assertIn("10.0.0.99", res["out_of_scope_ips"])

    def test_unresolved_domain_handling(self):
        def failing_resolver(d):
            raise RuntimeError("NXDOMAIN simulado")

        res = check_dns_drift(
            domain="inexistente.local",
            scope_data=self.scope_data,
            mock_resolver=failing_resolver,
        )
        self.assertEqual(res["status"], "UNRESOLVED")
        self.assertFalse(res["is_in_scope"])
        self.assertIn("NXDOMAIN simulado", res["error"])

    def test_evaluate_engagement_dns_drift_full_cycle(self):
        target_yaml = self.tmp_path / "target.yaml"
        target_yaml.write_text(
            "scope:\n"
            "  in_scope:\n"
            "    domains:\n"
            "      - api.target.local\n"
            "    ips:\n"
            "      - 192.168.1.10\n"
            "authorization:\n"
            "  reference: \"AUTH-2026\"\n"
            "  valid_from: \"2026-10-01T00:00:00Z\"\n"
            "  valid_until: \"2026-10-31T23:59:59Z\"\n"
            "  allow_passive: true\n"
            "  allow_active: true\n"
        )

        mock_map = {"api.target.local": ["192.168.1.10"]}
        resolver = lambda d: mock_map.get(d, [])

        eval_res = evaluate_engagement_dns_drift(self.tmp_path, mock_resolver=resolver)
        self.assertEqual(eval_res["status"], "OK")
        self.assertEqual(eval_res["domains_count"], 1)
        self.assertEqual(eval_res["violations_count"], 0)
        self.assertEqual(eval_res["drift_count"], 0)

        # Verificar que se creó evidence/.dns_records.json
        cache_path = self.tmp_path / "evidence" / ".dns_records.json"
        self.assertTrue(cache_path.is_file())


if __name__ == "__main__":
    unittest.main()
