import pathlib
import tempfile
import unittest


class TestScopeValidation(unittest.TestCase):
    """Cubre la fase 105: el editor de alcance del dashboard no debe poder
    dejar target.yaml en un estado invalido (A1 del backlog de mejoras)."""

    def setUp(self):
        from app.services.workspace_sync import WorkspaceSyncService
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.workspace = WorkspaceSyncService(self.root / "workspace")
        self.workspace.create_engagement("sample")

    def test_initial_scope_is_empty_without_a_target(self):
        data = self.workspace.get_target_yaml("sample")
        self.assertFalse(any(data["scope"]["in_scope"].values()))
        self.assertFalse(any(data["scope"]["out_of_scope"].values()))
        self.assertEqual(data["engagement"]["tos_reference"], "")

    def test_initial_domain_does_not_authorize_subdomains_or_add_examples(self):
        from seclab_scope import check_scope
        self.workspace.create_engagement("exact", domain="example.test")
        data = self.workspace.get_target_yaml("exact")
        self.assertEqual(data["scope"]["in_scope"]["domains"], ["example.test"])
        self.assertEqual(data["scope"]["in_scope"]["endpoints"], [])
        self.assertEqual(check_scope("example.test", data)[0], "IN_SCOPE")
        self.assertEqual(check_scope("sub.example.test", data)[0], "UNKNOWN")
        self.assertFalse(any(data["scope"]["out_of_scope"].values()))

    def test_explicit_wildcard_and_ip_are_preserved(self):
        from seclab_scope import check_scope
        for name, target in (("wild", "*.example.test"), ("v4", "192.0.2.1"), ("v6", "2001:db8::1")):
            self.workspace.create_engagement(name, domain=target)
            data = self.workspace.get_target_yaml(name)
            expected = "sub.example.test" if name == "wild" else target
            self.assertEqual(check_scope(expected, data)[0], "IN_SCOPE")
            self.assertEqual(sum(len(values) for values in data["scope"]["in_scope"].values()), 1)

    def test_invalid_initial_target_fails_before_creating_project(self):
        from app.services.workspace_sync import ScopeValidationError
        with self.assertRaises(ScopeValidationError):
            self.workspace.create_engagement("invalid", domain="https://example.test/api")
        self.assertFalse((self.root / "workspace" / "engagements" / "invalid").exists())

    def _scope_payload(self, **overrides):
        payload = self.workspace.get_target_yaml("sample")
        payload["scope"] = {
            "in_scope": {
                "domains": ["sample.local"],
                "ips": ["10.0.0.5"],
                "cidrs": ["10.0.1.0/24"],
                "endpoints": ["https://sample.local/api"],
            },
            "out_of_scope": {
                "domains": [],
                "ips": [],
                "cidrs": [],
                "notes": [],
            },
        }
        payload["scope"].update(overrides)
        return payload

    def test_valid_scope_with_separate_ips_and_cidrs_is_written(self):
        payload = self._scope_payload()
        self.assertTrue(self.workspace.save_target_yaml("sample", payload))
        saved = self.workspace.get_target_yaml("sample")
        self.assertEqual(saved["scope"]["in_scope"]["ips"], ["10.0.0.5"])
        self.assertEqual(saved["scope"]["in_scope"]["cidrs"], ["10.0.1.0/24"])
        self.assertEqual(saved["scope"]["in_scope"]["endpoints"], ["https://sample.local/api"])

    def test_cidr_misclassified_as_ip_is_rejected_and_disk_is_untouched(self):
        # Reproduce el bug original: un CIDR escrito en el campo combinado
        # "IPs y CIDRs" terminaba guardado dentro de `ips`.
        from app.services.workspace_sync import ScopeValidationError
        before = self.workspace.get_target_yaml("sample")
        payload = self._scope_payload(in_scope={
            "domains": ["sample.local"],
            "ips": ["10.0.1.0/24"],
            "cidrs": [],
            "endpoints": [],
        })
        with self.assertRaises(ScopeValidationError):
            self.workspace.save_target_yaml("sample", payload)
        # El target.yaml previo no debe alterarse: fallo cerrado, sin escritura parcial.
        self.assertEqual(self.workspace.get_target_yaml("sample"), before)

    def test_malformed_domain_is_rejected(self):
        from app.services.workspace_sync import ScopeValidationError
        payload = self._scope_payload(in_scope={
            "domains": ["not a domain!"],
            "ips": [],
            "cidrs": [],
            "endpoints": [],
        })
        with self.assertRaises(ScopeValidationError):
            self.workspace.save_target_yaml("sample", payload)

    def test_invalid_operational_limits_type_is_rejected(self):
        from app.services.workspace_sync import ScopeValidationError
        payload = self._scope_payload()
        payload["operational_limits"] = "no-deberia-ser-texto"
        with self.assertRaises(ScopeValidationError):
            self.workspace.save_target_yaml("sample", payload)

    def test_payload_without_scope_key_skips_scope_validation(self):
        # save_target_yaml tambien puede usarse para otros datos de
        # target.yaml; sin clave "scope" no debe exigir nada de seclab_scope.
        payload = {"version": "1.0", "engagement": {"name": "sample"}}
        self.assertTrue(self.workspace.save_target_yaml("sample", payload))
        self.assertEqual(self.workspace.get_target_yaml("sample"), payload)


if __name__ == "__main__":
    unittest.main()
