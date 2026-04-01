import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "build_heaven_fall_catalog.py"
SPEC = importlib.util.spec_from_file_location("build_heaven_fall_catalog", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class BuildCatalogTests(unittest.TestCase):
    def make_fixture(self) -> tuple[Path, Path, Path]:
        temp_dir = Path(tempfile.mkdtemp())
        data_root = temp_dir / "data"
        docs_root = temp_dir / "docs"
        source_root = temp_dir / "source"
        source_root.mkdir(parents=True, exist_ok=True)
        (source_root / "card-a.jpg").write_bytes(b"fake-image")

        write_json(
            data_root / "rules.json",
            {
                "schemaVersion": 1,
                "title": "Heaven Fall",
                "sections": [
                    {"id": "ammo", "title": "Ammo", "body": ["Ammo text"]},
                    {"id": "reroll", "title": "Reroll", "body": ["Reroll text"]},
                ],
            },
        )
        write_json(
            data_root / "cards" / "card-a.json",
            {
                "schemaVersion": 1,
                "unitId": "card-a",
                "name": "Card A",
                "maxPerSquad": 2,
                "stats": [{"key": "w", "label": "W", "value": 4, "sourceText": "W 4"}],
                "defense": [{"key": "sv", "label": "SV", "value": "3", "sourceText": "SV 3"}],
                "attacks": [],
                "tags": [],
                "rulesText": [],
                "sourceImage": "card-a.jpg",
                "verification": {
                    "status": "in_review",
                    "updatedAt": "2026-04-01T20:00:00+00:00",
                    "sourceQuality": "fair",
                    "unresolvedFields": ["stats[0].value"],
                    "notes": ["Needs confirmation"],
                    "fieldNotes": {"stats[0].value": "Handwritten number is partially cut off."},
                    "reviewChecklist": {
                        "stats": False,
                        "defense": True,
                        "attacks": True,
                        "tags": True,
                        "rulesText": True
                    }
                },
            },
        )
        return data_root, docs_root, source_root

    def test_build_catalog_accepts_valid_input(self) -> None:
        data_root, docs_root, source_root = self.make_fixture()
        manifest, catalog, report = MODULE.build_catalog(data_root, docs_root, source_root)

        self.assertEqual(manifest["unitCount"], 1)
        self.assertEqual(catalog["units"][0]["unitId"], "card-a")
        self.assertTrue((docs_root / "assets" / "source-cards" / "card-a.jpg").exists())
        self.assertEqual(catalog["rules"][0]["sections"][0]["title"], "Ammo")
        self.assertEqual(report["summary"]["statusCounts"]["in_review"], 1)

    def test_build_catalog_rejects_duplicate_unit_id(self) -> None:
        data_root, docs_root, source_root = self.make_fixture()
        write_json(
            data_root / "cards" / "duplicate.json",
            {
                "schemaVersion": 1,
                "unitId": "card-a",
                "name": "Card Duplicate",
                "maxPerSquad": 1,
                "stats": [],
                "defense": [],
                "attacks": [],
                "tags": [],
                "rulesText": [],
                "sourceImage": "card-a.jpg",
                "verification": {
                    "status": "unverified",
                    "updatedAt": "2026-04-01T20:00:00+00:00",
                    "sourceQuality": "poor",
                    "unresolvedFields": [],
                    "notes": [],
                    "fieldNotes": {},
                    "reviewChecklist": {
                        "stats": False,
                        "defense": False,
                        "attacks": False,
                        "tags": True,
                        "rulesText": True
                    }
                },
            },
        )

        with self.assertRaisesRegex(ValueError, "Duplicate unitId detected"):
            MODULE.build_catalog(data_root, docs_root, source_root)

    def test_build_catalog_rejects_missing_name_or_source_image(self) -> None:
        data_root, docs_root, source_root = self.make_fixture()
        write_json(
            data_root / "cards" / "bad-card.json",
            {
                "schemaVersion": 1,
                "unitId": "bad-card",
                "name": "",
                "maxPerSquad": 1,
                "stats": [],
                "defense": [],
                "attacks": [],
                "tags": [],
                "rulesText": [],
                "sourceImage": "",
                "verification": {
                    "status": "unverified",
                    "updatedAt": "2026-04-01T20:00:00+00:00",
                    "sourceQuality": "poor",
                    "unresolvedFields": [],
                    "notes": [],
                    "fieldNotes": {},
                    "reviewChecklist": {
                        "stats": False,
                        "defense": False,
                        "attacks": False,
                        "tags": True,
                        "rulesText": True
                    }
                },
            },
        )

        with self.assertRaisesRegex(ValueError, "missing required field 'name'"):
            MODULE.build_catalog(data_root, docs_root, source_root)

    def test_build_catalog_preserves_unresolved_verification_metadata(self) -> None:
        data_root, docs_root, source_root = self.make_fixture()
        manifest, catalog, report = MODULE.build_catalog(data_root, docs_root, source_root)

        self.assertEqual(manifest["rulesSectionCount"], 2)
        verification = catalog["units"][0]["verification"]
        self.assertEqual(verification["unresolvedFields"], ["stats[0].value"])
        self.assertTrue(verification["hasUnresolvedFields"])
        self.assertEqual(verification["fieldNotes"]["stats[0].value"], "Handwritten number is partially cut off.")
        self.assertEqual(report["cards"][0]["unresolvedFieldCount"], 1)

    def test_build_catalog_rejects_verified_cards_with_unresolved_fields(self) -> None:
        data_root, docs_root, source_root = self.make_fixture()
        write_json(
            data_root / "cards" / "card-a.json",
            {
                "schemaVersion": 1,
                "unitId": "card-a",
                "name": "Card A",
                "maxPerSquad": 2,
                "stats": [{"key": "w", "label": "W", "value": 4}],
                "defense": [{"key": "sv", "label": "SV", "value": "3"}],
                "attacks": [],
                "tags": [],
                "rulesText": [],
                "sourceImage": "card-a.jpg",
                "verification": {
                    "status": "verified",
                    "updatedAt": "2026-04-01T20:00:00+00:00",
                    "sourceQuality": "good",
                    "unresolvedFields": ["stats[0].value"],
                    "notes": [],
                    "fieldNotes": {"stats[0].value": "Still unresolved"},
                    "reviewChecklist": {
                        "stats": True,
                        "defense": True,
                        "attacks": True,
                        "tags": True,
                        "rulesText": True
                    }
                },
            },
        )

        with self.assertRaisesRegex(ValueError, "verified cards cannot contain unresolved fields"):
            MODULE.build_catalog(data_root, docs_root, source_root)


if __name__ == "__main__":
    unittest.main()
