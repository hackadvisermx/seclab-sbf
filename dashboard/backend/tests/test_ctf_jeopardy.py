import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.workspace_sync import WorkspaceSyncService
from app.models.schemas import EngagementCreate


class TestCtfJeopardySupport(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.ws_path = pathlib.Path(self.temp_dir.name)
        self.service = WorkspaceSyncService(workspace_path=self.ws_path)

    def test_create_jeopardy_challenge_and_list_metadata(self):
        item = self.service.create_engagement(
            name="crypto-rsa-oracle",
            eng_type="reto",
            client="DiceCTF 2026",
            subtype="jeopardy",
            category="crypto",
            points=250,
            difficulty="medium",
        )

        self.assertEqual(item.id, "crypto-rsa-oracle")
        self.assertEqual(item.type, "reto")
        self.assertEqual(item.subtype, "jeopardy")
        self.assertEqual(item.category, "crypto")
        self.assertEqual(item.points, 250)
        self.assertEqual(item.difficulty, "medium")
        self.assertFalse(item.is_solved)

        # Verificar target.yaml
        target_yaml = self.ws_path / "retos/crypto-rsa-oracle/target.yaml"
        self.assertTrue(target_yaml.exists())
        with open(target_yaml, "r", encoding="utf-8") as f:
            ydata = yaml.safe_load(f)
        meta = ydata.get("engagement", {})
        self.assertEqual(meta.get("subtype"), "jeopardy")
        self.assertEqual(meta.get("category"), "crypto")
        self.assertEqual(meta.get("points"), 250)
        self.assertEqual(meta.get("difficulty"), "medium")

        # Verificar list_engagements
        items = self.service.list_engagements()
        jeopardy_item = next((i for i in items if i.id == "crypto-rsa-oracle"), None)
        self.assertIsNotNone(jeopardy_item)
        self.assertEqual(jeopardy_item.subtype, "jeopardy")
        self.assertEqual(jeopardy_item.category, "crypto")
        self.assertEqual(jeopardy_item.points, 250)
        self.assertFalse(jeopardy_item.is_solved)

    def test_save_and_retrieve_jeopardy_flag_updates_solved_status(self):
        self.service.create_engagement(
            name="web-jwt-bypass",
            eng_type="reto",
            client="PicoCTF",
            subtype="jeopardy",
            category="web",
            points=100,
        )

        initial_flags = self.service.get_flags("web-jwt-bypass", "reto")
        self.assertEqual(initial_flags.get("subtype"), "jeopardy")
        self.assertEqual(initial_flags.get("category"), "web")
        self.assertEqual(initial_flags.get("points"), 100)
        self.assertFalse(initial_flags.get("solved"))

        # Marcar bandera como capturada
        initial_flags["flag"]["value"] = "picoCTF{jw7_n0n3_4lg0r17hm}"
        initial_flags["flag"]["status"] = "captured"
        initial_flags["flag"]["notes"] = "Clave firmada con alg=none en header JWT"

        saved = self.service.save_flags("web-jwt-bypass", initial_flags, "reto")
        self.assertTrue(saved.get("solved"))
        self.assertTrue(saved["flag"].get("captured_at"))

        # Recuperar y verificar persistencia
        retrieved = self.service.get_flags("web-jwt-bypass", "reto")
        self.assertTrue(retrieved.get("solved"))
        self.assertEqual(retrieved["flag"]["value"], "picoCTF{jw7_n0n3_4lg0r17hm}")
        self.assertEqual(retrieved["flag"]["status"], "captured")
        self.assertEqual(retrieved["flag"]["notes"], "Clave firmada con alg=none en header JWT")

        # Verificar list_engagements
        items = self.service.list_engagements()
        reto_item = next((i for i in items if i.id == "web-jwt-bypass"), None)
        self.assertIsNotNone(reto_item)
        self.assertTrue(reto_item.is_solved)

    def test_backward_compatibility_with_machine_reto(self):
        # Crear reto tradicional tipo máquina
        item = self.service.create_engagement(
            name="legacy-box",
            eng_type="reto",
            client="HackTheBox",
            subtype="machine",
        )
        self.assertEqual(item.subtype, "machine")
        self.assertIsNone(item.category)
        self.assertFalse(item.is_solved)

        # Capturar user_flag no resuelve la máquina completa
        flags = self.service.get_flags("legacy-box", "reto")
        flags["user_flag"]["value"] = "user_flag_hash_here"
        flags["user_flag"]["status"] = "captured"
        self.service.save_flags("legacy-box", flags, "reto")

        items = self.service.list_engagements()
        box_item = next((i for i in items if i.id == "legacy-box"), None)
        self.assertFalse(box_item.is_solved)

        # Capturar root_flag resuelve la máquina
        flags["root_flag"]["value"] = "root_flag_hash_here"
        flags["root_flag"]["status"] = "captured"
        self.service.save_flags("legacy-box", flags, "reto")

        items = self.service.list_engagements()
        box_item = next((i for i in items if i.id == "legacy-box"), None)
        self.assertTrue(box_item.is_solved)

    def test_sync_category_and_points_from_flags_to_target_yaml(self):
        self.service.create_engagement(
            name="rev-crackme",
            eng_type="reto",
            subtype="jeopardy",
            category="reverse",
            points=150,
        )

        flags = self.service.get_flags("rev-crackme", "reto")
        flags["points"] = 300
        flags["difficulty"] = "hard"
        self.service.save_flags("rev-crackme", flags, "reto")

        target_yaml = self.ws_path / "retos/rev-crackme/target.yaml"
        with open(target_yaml, "r", encoding="utf-8") as f:
            ydata = yaml.safe_load(f)
        meta = ydata.get("engagement", {})
        self.assertEqual(meta.get("points"), 300)
        self.assertEqual(meta.get("difficulty"), "hard")

    def test_api_endpoints_create_and_detail_jeopardy(self):
        from app.api.endpoints import engagements, loot
        app = FastAPI()
        app.include_router(engagements.router)
        app.include_router(loot.router)

        with patch.object(engagements, "workspace_service", self.service), \
             patch.object(loot, "workspace_service", self.service), \
             TestClient(app) as client:
            
            payload = {
                "name": "pwn-rop-baby",
                "type": "reto",
                "client": "Defcon CTF",
                "subtype": "jeopardy",
                "category": "pwn",
                "points": 400,
                "difficulty": "hard",
            }
            res = client.post("/engagements", json=payload)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["id"], "pwn-rop-baby")
            self.assertEqual(data["subtype"], "jeopardy")
            self.assertEqual(data["category"], "pwn")
            self.assertEqual(data["points"], 400)

            # Detalle
            res_detail = client.get("/engagements/pwn-rop-baby?type=reto")
            self.assertEqual(res_detail.status_code, 200)
            detail = res_detail.json()
            self.assertEqual(detail["subtype"], "jeopardy")
            self.assertEqual(detail["category"], "pwn")
            self.assertEqual(detail["points"], 400)
            self.assertFalse(detail["is_solved"])

            # Guardar bandera por API
            flag_payload = {
                "subtype": "jeopardy",
                "category": "pwn",
                "points": 400,
                "flag": {
                    "value": "flag{r0p_ch41n_0v3rfl0w}",
                    "status": "captured",
                    "notes": "mprotect + shellcode payload",
                }
            }
            res_flags = client.post("/loot/pwn-rop-baby/flags?type=reto", json=flag_payload)
            self.assertEqual(res_flags.status_code, 200)
            self.assertTrue(res_flags.json()["solved"])

            # Re-verificar detalle
            res_detail2 = client.get("/engagements/pwn-rop-baby?type=reto")
            self.assertTrue(res_detail2.json()["is_solved"])
