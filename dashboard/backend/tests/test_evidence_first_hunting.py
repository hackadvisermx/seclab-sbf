import datetime
import pathlib
import tempfile
import unittest
import yaml

from app.services.workspace_sync import WorkspaceSyncService
from app.models.schemas import FindingCreate


class TestEvidenceFirstHunting(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.ws_path = pathlib.Path(self.temp_dir.name)
        self.service = WorkspaceSyncService(workspace_path=self.ws_path)

        # Crear engagement base
        self.service.create_engagement(
            name="hunting-lab",
            eng_type="engagement",
            client="Target Security Lab",
        )

    def test_save_finding_with_proven_status(self):
        finding_data = FindingCreate(
            slug="idor-user-profile",
            title="Insecure Direct Object Reference en Perfil",
            severity="HIGH",
            cvss_score=8.1,
            status="PROVEN",
            asset="https://api.target.local/v1/users/42/profile",
            description="Lectura no autorizada de datos personales de otro usuario.",
            steps_to_reproduce="1. Iniciar sesión como Usuario B.\n2. Modificar id a 42 (Usuario A).\n3. Validar con control negativo.",
        )

        detail = self.service.save_finding("hunting-lab", finding_data, eng_type="engagement")
        self.assertEqual(detail.slug, "idor-user-profile")
        self.assertEqual(detail.frontmatter.status, "PROVEN")
        self.assertEqual(detail.frontmatter.severity, "HIGH")

        # Verificar contenido en disco
        file_path = self.ws_path / "engagements/hunting-lab/evidence/idor-user-profile.md"
        self.assertTrue(file_path.exists())
        content = file_path.read_text(encoding="utf-8")
        self.assertIn("status: PROVEN", content)

        # Verificar list_findings
        findings = self.service.list_findings("hunting-lab", eng_type="engagement")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].frontmatter.status, "PROVEN")

        # Verificar get_finding
        retrieved = self.service.get_finding("hunting-lab", "idor-user-profile", eng_type="engagement")
        self.assertEqual(retrieved.frontmatter.status, "PROVEN")

    def test_save_finding_candidate_and_disproved(self):
        # 1. Hallazgo en estado CANDIDATE
        cand = FindingCreate(
            slug="candidate-sqli",
            title="Posible SQL Injection en Parámetro id",
            severity="MEDIUM",
            cvss_score=5.5,
            status="CANDIDATE",
            asset="https://api.target.local/v1/search",
            description="Hipótesis bajo análisis sin confirmación determinista.",
        )
        self.service.save_finding("hunting-lab", cand)

        # 2. Hallazgo en estado DISPROVED
        disp = FindingCreate(
            slug="disproved-ssrf",
            title="Falso Positivo en Webhook Callback",
            severity="LOW",
            cvss_score=3.1,
            status="DISPROVED",
            asset="https://api.target.local/v1/webhook",
            description="Refutado por control negativo con respuesta 403 y resolución fija.",
        )
        self.service.save_finding("hunting-lab", disp)

        findings = {f.slug: f for f in self.service.list_findings("hunting-lab")}
        self.assertEqual(findings["candidate-sqli"].frontmatter.status, "CANDIDATE")
        self.assertEqual(findings["disproved-ssrf"].frontmatter.status, "DISPROVED")

    def test_legacy_finding_status_fallback(self):
        ev_dir = self.ws_path / "engagements/hunting-lab/evidence"
        ev_dir.mkdir(parents=True, exist_ok=True)

        # Ficha legada sin campo status
        legacy_no_status = ev_dir / "legacy-vuln.md"
        legacy_no_status.write_text(
            "---\n"
            "title: 'Vulnerabilidad Antigua'\n"
            "severity: 'HIGH'\n"
            "cvss_score: 7.5\n"
            "cwe: 'CWE-79'\n"
            "asset: 'https://legacy.target.local'\n"
            "---\n\n"
            "## Descripción\n"
            "Ficha antigua sin campo status explícito.\n",
            encoding="utf-8"
        )

        findings = self.service.list_findings("hunting-lab")
        legacy_item = next(f for f in findings if f.slug == "legacy-vuln")
        # El fallback por defecto debe ser PROVEN
        self.assertEqual(legacy_item.frontmatter.status, "PROVEN")

        # Ficha con estado en español o mixto
        legacy_confirmado = ev_dir / "legacy-confirmado.md"
        legacy_confirmado.write_text(
            "---\n"
            "title: 'Vulnerabilidad Confirmada'\n"
            "severity: 'CRITICAL'\n"
            "status: 'Confirmado'\n"
            "---\n\n"
            "## Descripción\n"
            "Estado confirmado legado.\n",
            encoding="utf-8"
        )
        conf_item = next(f for f in self.service.list_findings("hunting-lab") if f.slug == "legacy-confirmado")
        self.assertIn(conf_item.frontmatter.status, ["PROVEN", "CONFIRMADO"])

    def test_target_yaml_access_mode_and_identities(self):
        target_path = self.ws_path / "engagements/hunting-lab/target.yaml"
        target_data = {
            "version": "1.0",
            "engagement": {
                "name": "hunting-lab",
                "type": "engagement",
                "access_mode": "rich",
                "identities": [
                    {"id": "tester_a", "role": "victim_owner"},
                    {"id": "tester_b", "role": "attacker_user"}
                ]
            },
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": [], "cidrs": []},
                "out_of_scope": {"domains": [], "ips": [], "cidrs": []}
            }
        }
        with open(target_path, "w", encoding="utf-8") as f:
            yaml.dump(target_data, f)

        # Leer archivo y verificar persistencia
        with open(target_path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
        self.assertEqual(loaded["engagement"]["access_mode"], "rich")
        self.assertEqual(len(loaded["engagement"]["identities"]), 2)
        self.assertEqual(loaded["engagement"]["identities"][0]["id"], "tester_a")

    def test_help_cheatsheet_endpoint_loads_all_commands(self):
        from app.api.endpoints import help_center
        items = help_center.get_cheatsheet()
        self.assertGreaterEqual(len(items), 48)
        first = items[0]
        self.assertIn("category", first)
        self.assertIn("title", first)
        self.assertIn("command", first)
        self.assertIn("description", first)

    def test_help_skills_endpoint_loads_playbooks(self):
        from app.api.endpoints import help_center
        skills = help_center.list_skills()
        self.assertGreaterEqual(len(skills), 10)
        first = skills[0]
        self.assertIn("id", first)
        self.assertIn("title", first)
        self.assertIn("description", first)
        self.assertTrue(first["title"].startswith("Skill:"))

        # Validar detalle de una skill
        detail = help_center.get_skill_detail(first["id"])
        self.assertEqual(detail["id"], first["id"])
        self.assertIn("## 1. Propósito", detail["content"])
