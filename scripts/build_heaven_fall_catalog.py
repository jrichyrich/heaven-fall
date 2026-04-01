import argparse
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 1
RAW_CAPTURE_DIR = Path("assets") / "raw-captures"
SOURCE_IMAGE_DIR = Path("assets") / "source-cards"
REPORT_FILE = "verification-report.json"
CORE_RULE_TITLES = {"Ammo", "Cover", "Cells"}
UNIVERSAL_STRAIN_TITLES = {"Strains", "Reroll", "Cover fire", "Chill", "Burn"}
VERIFICATION_STATUSES = {"unverified", "in_review", "verified"}
SOURCE_QUALITY_VALUES = {"poor", "fair", "good"}
REVIEW_CHECKLIST_FIELDS = ("stats", "defense", "attacks", "tags", "rulesText")


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


def ensure_dict(value: object, field_name: str, path: Path) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected '{field_name}' to be an object")
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


def validate_source_text_entries(entries: list[dict], field_name: str, path: Path) -> None:
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: {field_name}[{index}] must be an object")
        if entry.get("sourceText") is not None and not isinstance(entry.get("sourceText"), str):
            raise ValueError(f"{path}: {field_name}[{index}].sourceText must be a string when present")


def validate_verification_block(payload: dict, path: Path) -> dict:
    verification = ensure_dict(payload.get("verification"), "verification", path)
    status = str(verification.get("status") or "").strip()
    updated_at = str(verification.get("updatedAt") or "").strip()
    source_quality = str(verification.get("sourceQuality") or "").strip()
    unresolved_fields = ensure_list(verification.get("unresolvedFields"), "verification.unresolvedFields", path)
    notes = ensure_list(verification.get("notes"), "verification.notes", path)
    field_notes = ensure_dict(verification.get("fieldNotes"), "verification.fieldNotes", path)
    review_checklist = ensure_dict(verification.get("reviewChecklist"), "verification.reviewChecklist", path)

    if status not in VERIFICATION_STATUSES:
        raise ValueError(f"{path}: verification.status must be one of {sorted(VERIFICATION_STATUSES)}")
    if not updated_at:
        raise ValueError(f"{path}: verification.updatedAt is required")
    if source_quality not in SOURCE_QUALITY_VALUES:
        raise ValueError(f"{path}: verification.sourceQuality must be one of {sorted(SOURCE_QUALITY_VALUES)}")

    for key in REVIEW_CHECKLIST_FIELDS:
        if key not in review_checklist or not isinstance(review_checklist[key], bool):
            raise ValueError(f"{path}: verification.reviewChecklist.{key} must be a boolean")

    for unresolved_field in unresolved_fields:
        if not isinstance(unresolved_field, str) or not unresolved_field.strip():
            raise ValueError(f"{path}: verification.unresolvedFields entries must be non-empty strings")

    for note in notes:
        if not isinstance(note, str):
            raise ValueError(f"{path}: verification.notes entries must be strings")

    for field_key, field_note in field_notes.items():
        if not isinstance(field_key, str) or not field_key.strip():
            raise ValueError(f"{path}: verification.fieldNotes keys must be non-empty strings")
        if not isinstance(field_note, str):
            raise ValueError(f"{path}: verification.fieldNotes values must be strings")

    if status == "verified":
        if unresolved_fields:
            raise ValueError(f"{path}: verified cards cannot contain unresolved fields")
        if source_quality == "poor":
            raise ValueError(f"{path}: verified cards cannot use poor-quality source captures")

    if status == "in_review":
        missing_notes = [field for field in unresolved_fields if field not in field_notes]
        if missing_notes:
            raise ValueError(
                f"{path}: in_review cards require fieldNotes entries for unresolved fields: {', '.join(missing_notes)}"
            )

    return verification


def validate_card_payload(payload: dict, path: Path, source_root: Path) -> dict:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError(f"{path}: unsupported schemaVersion {payload.get('schemaVersion')}")

    required_strings = ("unitId", "name", "sourceImage")
    for field_name in required_strings:
        if not str(payload.get(field_name) or "").strip():
            raise ValueError(f"{path}: missing required field '{field_name}'")

    stats = ensure_list(payload.get("stats"), "stats", path)
    defense = ensure_list(payload.get("defense"), "defense", path)
    attacks = ensure_list(payload.get("attacks"), "attacks", path)
    ensure_list(payload.get("tags"), "tags", path)
    ensure_list(payload.get("rulesText"), "rulesText", path)

    validate_source_text_entries(stats, "stats", path)
    validate_source_text_entries(defense, "defense", path)
    validate_source_text_entries(attacks, "attacks", path)
    validate_verification_block(payload, path)

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


def review_progress(review_checklist: dict) -> dict:
    completed = sum(1 for key in REVIEW_CHECKLIST_FIELDS if review_checklist.get(key))
    total = len(REVIEW_CHECKLIST_FIELDS)
    return {
        "completed": completed,
        "total": total,
        "percent": round((completed / total) * 100) if total else 0,
    }


def normalize_card(card: dict) -> dict:
    verification = card["verification"]
    unresolved = list(verification["unresolvedFields"])
    status = verification["status"]
    source_quality = verification["sourceQuality"]
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
            "status": status,
            "statusLabel": (
                "Verified" if status == "verified" else (
                    "Source unclear" if source_quality == "poor" else "Needs review"
                )
            ),
            "updatedAt": verification["updatedAt"],
            "sourceQuality": source_quality,
            "unresolvedFields": unresolved,
            "notes": list(verification["notes"]),
            "fieldNotes": dict(verification["fieldNotes"]),
            "reviewChecklist": dict(verification["reviewChecklist"]),
            "hasUnresolvedFields": bool(unresolved),
            "progress": review_progress(verification["reviewChecklist"]),
        },
    }


def build_verification_summary(normalized_units: list[dict]) -> dict:
    status_counts = Counter(unit["verification"]["status"] for unit in normalized_units)
    source_quality_counts = Counter(unit["verification"]["sourceQuality"] for unit in normalized_units)
    unresolved_total = sum(len(unit["verification"]["unresolvedFields"]) for unit in normalized_units)
    return {
        "statusCounts": {status: status_counts.get(status, 0) for status in sorted(VERIFICATION_STATUSES)},
        "sourceQualityCounts": {quality: source_quality_counts.get(quality, 0) for quality in sorted(SOURCE_QUALITY_VALUES)},
        "unresolvedFieldTotal": unresolved_total,
        "fullyVerifiedCount": status_counts.get("verified", 0),
        "inReviewCount": status_counts.get("in_review", 0),
        "unverifiedCount": status_counts.get("unverified", 0),
    }


def build_verification_report(normalized_units: list[dict], generated_at: str) -> dict:
    summary = build_verification_summary(normalized_units)
    cards = []
    for unit in normalized_units:
        verification = unit["verification"]
        cards.append({
            "unitId": unit["unitId"],
            "name": unit["name"],
            "status": verification["status"],
            "statusLabel": verification["statusLabel"],
            "sourceQuality": verification["sourceQuality"],
            "updatedAt": verification["updatedAt"],
            "unresolvedFieldCount": len(verification["unresolvedFields"]),
            "unresolvedFields": list(verification["unresolvedFields"]),
            "progress": dict(verification["progress"]),
        })
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": generated_at,
        "summary": summary,
        "cards": cards,
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


def build_catalog(data_root: Path, docs_root: Path, source_root: Path) -> tuple[dict, dict, dict]:
    rules_payload = load_rules(data_root)
    cards = load_cards(data_root, source_root)
    rule_groups = build_rule_groups(rules_payload)
    normalized_units = [normalize_card(card) for card in cards]
    asset_index = copy_source_images(cards, source_root, docs_root)
    generated_at = utc_now()
    verification_summary = build_verification_summary(normalized_units)
    verification_report = build_verification_report(normalized_units, generated_at)

    catalog = {
        "schemaVersion": SCHEMA_VERSION,
        "title": "Heaven Fall Card Library",
        "generatedAt": generated_at,
        "rules": rule_groups,
        "units": normalized_units,
        "assetIndex": asset_index,
        "verificationSummary": verification_summary,
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
        "verificationReportFile": REPORT_FILE,
        "verificationSummary": verification_summary,
    }
    return manifest, catalog, verification_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Heaven Fall static card catalog.")
    parser.add_argument("--data-root", default="data", help="Path to raw data files.")
    parser.add_argument("--docs-root", default="docs", help="Path to the static site output directory.")
    parser.add_argument(
        "--source-root",
        default=RAW_CAPTURE_DIR.as_posix(),
        help="Path to the raw source images referenced by the raw card JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root()
    data_root = (root / args.data_root).resolve()
    docs_root = (root / args.docs_root).resolve()
    source_root = (root / args.source_root).resolve()

    manifest, catalog, report = build_catalog(data_root, docs_root, source_root)
    write_json(docs_root / "data" / "manifest.json", manifest)
    write_json(docs_root / "data" / "catalog.json", catalog)
    write_json(docs_root / "data" / REPORT_FILE, report)


if __name__ == "__main__":
    main()
