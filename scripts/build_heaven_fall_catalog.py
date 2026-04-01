import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 1
SOURCE_IMAGE_DIR = Path("assets") / "source-cards"
CORE_RULE_TITLES = {"Ammo", "Cover", "Cells"}
UNIVERSAL_STRAIN_TITLES = {"Strains", "Reroll", "Cover fire", "Chill", "Burn"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_list(value: object, field_name: str, path: Path) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{path}: expected '{field_name}' to be a list")
    return value


def validate_rules_payload(payload: dict, path: Path) -> dict:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError(f"{path}: unsupported schemaVersion {payload.get('schemaVersion')}")
    sections = ensure_list(payload.get("sections"), "sections", path)
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            raise ValueError(f"{path}: section {index} must be an object")
        if not str(section.get("id") or "").strip():
            raise ValueError(f"{path}: section {index} is missing id")
        if not str(section.get("title") or "").strip():
            raise ValueError(f"{path}: section {index} is missing title")
        ensure_list(section.get("body"), "body", path)
    return payload


def validate_card_payload(payload: dict, path: Path, source_root: Path) -> dict:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError(f"{path}: unsupported schemaVersion {payload.get('schemaVersion')}")

    required_strings = ("unitId", "name", "sourceImage")
    for field_name in required_strings:
        if not str(payload.get(field_name) or "").strip():
            raise ValueError(f"{path}: missing required field '{field_name}'")

    for field_name in ("stats", "defense", "attacks", "tags", "rulesText"):
        ensure_list(payload.get(field_name), field_name, path)

    verification = payload.get("verification")
    if not isinstance(verification, dict):
        raise ValueError(f"{path}: missing verification block")
    ensure_list(verification.get("unresolvedFields"), "verification.unresolvedFields", path)
    ensure_list(verification.get("notes"), "verification.notes", path)
    if not str(verification.get("status") or "").strip():
        raise ValueError(f"{path}: verification.status is required")

    source_image_path = source_root / str(payload["sourceImage"])
    if not source_image_path.exists():
        raise ValueError(f"{path}: source image not found: {source_image_path}")

    return payload


def load_rules(data_root: Path) -> dict:
    rules_path = data_root / "rules.json"
    return validate_rules_payload(load_json(rules_path), rules_path)


def load_cards(data_root: Path, source_root: Path) -> list[dict]:
    cards_dir = data_root / "cards"
    records = []
    seen_ids: set[str] = set()
    for path in sorted(cards_dir.glob("*.json")):
        payload = validate_card_payload(load_json(path), path, source_root)
        unit_id = payload["unitId"]
        if unit_id in seen_ids:
            raise ValueError(f"Duplicate unitId detected: {unit_id}")
        seen_ids.add(unit_id)
        records.append(payload)
    if not records:
        raise ValueError(f"No card files found in {cards_dir}")
    return records


def build_rule_groups(rules_payload: dict) -> list[dict]:
    sections = rules_payload["sections"]
    grouped = [
        {
            "id": "core-rules",
            "title": "Core Rules",
            "sections": [section for section in sections if section["title"] in CORE_RULE_TITLES],
        },
        {
            "id": "universal-strains",
            "title": "Universal Strains",
            "sections": [section for section in sections if section["title"] in UNIVERSAL_STRAIN_TITLES],
        },
    ]
    return [group for group in grouped if group["sections"]]


def normalize_card(card: dict) -> dict:
    unresolved = list(card["verification"]["unresolvedFields"])
    return {
        "schemaVersion": SCHEMA_VERSION,
        "unitId": card["unitId"],
        "name": card["name"],
        "maxPerSquad": card.get("maxPerSquad"),
        "stats": list(card["stats"]),
        "defense": list(card["defense"]),
        "attacks": list(card["attacks"]),
        "tags": list(card["tags"]),
        "rulesText": list(card["rulesText"]),
        "sourceImage": card["sourceImage"],
        "sourceImageUrl": f"./{SOURCE_IMAGE_DIR.as_posix()}/{card['sourceImage']}",
        "verification": {
            "status": card["verification"]["status"],
            "unresolvedFields": unresolved,
            "notes": list(card["verification"]["notes"]),
            "hasUnresolvedFields": bool(unresolved),
        },
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def copy_source_images(cards: list[dict], source_root: Path, docs_root: Path) -> dict[str, str]:
    target_root = docs_root / SOURCE_IMAGE_DIR
    target_root.mkdir(parents=True, exist_ok=True)
    asset_index: dict[str, str] = {}
    for card in cards:
        file_name = card["sourceImage"]
        shutil.copy2(source_root / file_name, target_root / file_name)
        asset_index[card["unitId"]] = f"./{SOURCE_IMAGE_DIR.as_posix()}/{file_name}"
    return asset_index


def build_catalog(data_root: Path, docs_root: Path, source_root: Path) -> tuple[dict, dict]:
    rules_payload = load_rules(data_root)
    cards = load_cards(data_root, source_root)
    rule_groups = build_rule_groups(rules_payload)
    normalized_units = [normalize_card(card) for card in cards]
    asset_index = copy_source_images(cards, source_root, docs_root)
    generated_at = utc_now()

    catalog = {
        "schemaVersion": SCHEMA_VERSION,
        "title": "Heaven Fall Card Library",
        "generatedAt": generated_at,
        "rules": rule_groups,
        "units": normalized_units,
        "assetIndex": asset_index,
    }
    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "title": "Heaven Fall Card Library",
        "generatedAt": generated_at,
        "unitCount": len(normalized_units),
        "ruleGroupCount": len(rule_groups),
        "rulesSectionCount": sum(len(group["sections"]) for group in rule_groups),
        "catalogFile": "catalog.json",
        "assetsRoot": SOURCE_IMAGE_DIR.as_posix(),
    }
    return manifest, catalog


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Heaven Fall static card catalog.")
    parser.add_argument("--data-root", default="data", help="Path to raw data files.")
    parser.add_argument("--docs-root", default="docs", help="Path to the static site output directory.")
    parser.add_argument(
        "--source-root",
        default=".",
        help="Path to the original source images referenced by the raw card JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root()
    data_root = (root / args.data_root).resolve()
    docs_root = (root / args.docs_root).resolve()
    source_root = (root / args.source_root).resolve()

    manifest, catalog = build_catalog(data_root, docs_root, source_root)
    write_json(docs_root / "data" / "manifest.json", manifest)
    write_json(docs_root / "data" / "catalog.json", catalog)


if __name__ == "__main__":
    main()
