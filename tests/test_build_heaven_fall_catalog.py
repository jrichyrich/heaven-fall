import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "build_heaven_fall_catalog.py"
PDF_FIXTURE = REPO_ROOT / "assets" / "pdf" / "datasheets-for-heavenfall.pdf"
SPEC = importlib.util.spec_from_file_location("build_heaven_fall_catalog", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build_stats(movement: str = '7"', sd: int = 3) -> list[dict]:
    return [
        {"key": "m", "label": "M", "value": movement, "sourceText": f"M {movement}"},
        {"key": "w", "label": "W", "value": 4, "sourceText": "W 4"},
        {"key": "sv", "label": "SV", "value": "4+", "sourceText": "SV 4+"},
        {"key": "t", "label": "T", "value": 4, "sourceText": "T 4"},
        {"key": "sd", "label": "SD", "value": sd, "sourceText": f"SD {sd}"},
        {"key": "stm", "label": "STM", "value": 2, "sourceText": "STM 2"},
    ]


def build_verification(status: str = "verified", unresolved_fields: list[str] | None = None) -> dict:
    unresolved = unresolved_fields or []
    return {
        "status": status,
        "updatedAt": "2026-04-01T00:00:00+00:00",
        "sourceQuality": "good" if status == "verified" else "fair",
        "unresolvedFields": unresolved,
        "notes": ["Needs confirmation"] if unresolved else [],
        "fieldNotes": {field: "Captured for review." for field in unresolved},
        "reviewChecklist": {
            "stats": not unresolved,
            "defense": True,
            "attacks": True,
            "tags": True,
            "rulesText": True,
        },
    }


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
            data_root / "factions.json",
            {
                "schemaVersion": 1,
                "title": "Faction Rules",
                "groups": [
                    {
                        "id": "houno",
                        "title": "Houno",
                        "sections": [
                            {"id": "voice-of-command", "title": "Voice of command", "body": ["Faction passive."]},
                        ],
                    }
                ],
            },
        )

        return data_root, docs_root, source_root

    def test_build_catalog_accepts_pdf_backed_input_and_renders_asset(self) -> None:
        data_root, docs_root, source_root = self.make_fixture()
        write_json(
            data_root / "cards" / "lwbt-heavy-weapon.json",
            {
                "schemaVersion": 1,
                "unitId": "lwbt-heavy-weapon",
                "name": "LWBT Heavy weapon",
                "points": 50,
                "maxPerSquad": None,
                "stats": build_stats('8"', 3),
                "defense": [{"key": "ward", "label": "Ward", "value": "5+", "sourceText": "5+"}],
                "attacks": [
                    {
                        "name": "Heavy gun",
                        "kind": "ranged",
                        "range": '20"',
                        "atk": 1,
                        "hit": "4+",
                        "str": 10,
                        "aoe": '2"',
                        "dmg": "D3+1",
                        "notes": [],
                        "sourceText": 'Heavy gun | 20" | 1 | 4+ | 10 | 2" | D3+1',
                    }
                ],
                "tags": [],
                "specialRules": [],
                "rulesText": [],
                "source": {
                    "type": "pdf_page",
                    "file": str(PDF_FIXTURE),
                    "page": 3,
                },
                "verification": build_verification(),
            },
        )

        with mock.patch.object(MODULE, "render_pdf_page") as render_pdf_page:
            render_pdf_page.side_effect = lambda _src, _page, target: Path(target).write_bytes(b"png")
            manifest, catalog, report = MODULE.build_catalog(data_root, docs_root, source_root)

        self.assertEqual(manifest["unitCount"], 1)
        self.assertEqual(manifest["factionCount"], 1)
        self.assertEqual(catalog["units"][0]["unitId"], "lwbt-heavy-weapon")
        self.assertEqual(catalog["units"][0]["points"], 50)
        self.assertTrue((docs_root / "assets" / "source-cards" / "lwbt-heavy-weapon.png").exists())
        self.assertEqual(catalog["units"][0]["source"]["page"], 3)
        self.assertEqual(report["summary"]["statusCounts"]["verified"], 1)
        self.assertEqual(catalog["factions"][0]["title"], "Houno")

    def test_build_catalog_rejects_duplicate_unit_id(self) -> None:
        data_root, docs_root, source_root = self.make_fixture()
        payload = {
            "schemaVersion": 1,
            "unitId": "card-a",
            "name": "Card A",
            "points": 10,
            "maxPerSquad": 2,
            "stats": build_stats(),
            "defense": [],
            "attacks": [],
            "tags": [],
            "specialRules": [],
            "rulesText": [],
            "source": {"type": "image", "file": "card-a.jpg"},
            "verification": build_verification(),
        }
        write_json(data_root / "cards" / "card-a.json", payload)
        write_json(data_root / "cards" / "duplicate.json", {**payload, "name": "Duplicate"})

        with self.assertRaisesRegex(ValueError, "Duplicate unitId detected"):
            MODULE.build_catalog(data_root, docs_root, source_root)

    def test_build_catalog_rejects_missing_points_or_sd(self) -> None:
        data_root, docs_root, source_root = self.make_fixture()
        write_json(
            data_root / "cards" / "bad-card.json",
            {
                "schemaVersion": 1,
                "unitId": "bad-card",
                "name": "Bad Card",
                "maxPerSquad": 1,
                "stats": build_stats()[:-2] + [{"key": "stm", "label": "STM", "value": 2, "sourceText": "STM 2"}],
                "defense": [],
                "attacks": [],
                "tags": [],
                "specialRules": [],
                "rulesText": [],
                "source": {"type": "image", "file": "card-a.jpg"},
                "verification": build_verification(),
            },
        )

        with self.assertRaisesRegex(ValueError, "missing required field 'points'|stats must contain keys in order"):
            MODULE.build_catalog(data_root, docs_root, source_root)

    def test_build_catalog_preserves_unresolved_verification_metadata(self) -> None:
        data_root, docs_root, source_root = self.make_fixture()
        write_json(
            data_root / "cards" / "pistolier.json",
            {
                "schemaVersion": 1,
                "unitId": "pistolier",
                "name": "Pistolier",
                "points": 10,
                "maxPerSquad": 3,
                "stats": build_stats(),
                "defense": [],
                "attacks": [],
                "tags": [],
                "specialRules": ["Dual wield"],
                "rulesText": [],
                "source": {"type": "image", "file": "card-a.jpg"},
                "verification": build_verification("in_review", ["attacks[0].range"]),
            },
        )

        manifest, catalog, report = MODULE.build_catalog(data_root, docs_root, source_root)

        self.assertEqual(manifest["rulesSectionCount"], 2)
        self.assertEqual(manifest["factionSectionCount"], 1)
        verification = catalog["units"][0]["verification"]
        self.assertEqual(verification["unresolvedFields"], ["attacks[0].range"])
        self.assertTrue(verification["hasUnresolvedFields"])
        self.assertEqual(verification["fieldNotes"]["attacks[0].range"], "Captured for review.")
        self.assertEqual(report["cards"][0]["unresolvedFieldCount"], 1)

    def test_build_catalog_rejects_verified_cards_with_unresolved_fields(self) -> None:
        data_root, docs_root, source_root = self.make_fixture()
        write_json(
            data_root / "cards" / "card-a.json",
            {
                "schemaVersion": 1,
                "unitId": "card-a",
                "name": "Card A",
                "points": 10,
                "maxPerSquad": 2,
                "stats": build_stats(),
                "defense": [],
                "attacks": [],
                "tags": [],
                "specialRules": [],
                "rulesText": [],
                "source": {"type": "image", "file": "card-a.jpg"},
                "verification": {
                    **build_verification(),
                    "unresolvedFields": ["stats[0].value"],
                    "fieldNotes": {"stats[0].value": "Still unresolved"},
                },
            },
        )

        with self.assertRaisesRegex(ValueError, "verified cards cannot contain unresolved fields"):
            MODULE.build_catalog(data_root, docs_root, source_root)

    def test_build_catalog_rejects_canonical_name_mismatch(self) -> None:
        data_root, docs_root, source_root = self.make_fixture()
        write_json(
            data_root / "cards" / "pistollier.json",
            {
                "schemaVersion": 1,
                "unitId": "pistollier",
                "name": "Pistollier",
                "points": 10,
                "maxPerSquad": 3,
                "stats": build_stats(),
                "defense": [],
                "attacks": [],
                "tags": [],
                "specialRules": [],
                "rulesText": [],
                "source": {"type": "image", "file": "card-a.jpg"},
                "verification": build_verification(),
            },
        )

        with self.assertRaisesRegex(ValueError, "canonical naming mismatch"):
            MODULE.build_catalog(data_root, docs_root, source_root)

    def test_build_catalog_rejects_missing_source_asset(self) -> None:
        data_root, docs_root, source_root = self.make_fixture()
        write_json(
            data_root / "cards" / "dreg.json",
            {
                "schemaVersion": 1,
                "unitId": "dreg",
                "name": "Dreg",
                "points": 4,
                "maxPerSquad": None,
                "stats": build_stats('6"', 2),
                "defense": [],
                "attacks": [],
                "tags": [],
                "specialRules": [],
                "rulesText": [],
                "source": {"type": "pdf_page", "file": "missing.pdf", "page": 1},
                "verification": build_verification(),
            },
        )

        with self.assertRaisesRegex(ValueError, "source pdf not found"):
            MODULE.build_catalog(data_root, docs_root, source_root)


if __name__ == "__main__":
    unittest.main()
