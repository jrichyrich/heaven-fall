import argparse
import json
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 1
RAW_CAPTURE_DIR = Path("assets") / "raw-captures"
SOURCE_IMAGE_DIR = Path("assets") / "source-cards"
REPORT_FILE = "verification-report.json"
CORE_RULE_TITLES = {"Ammo", "Cover", "Cells"}
UNIVERSAL_STRAIN_TITLES = {"Strains", "Reroll", "Cover fire", "Chill", "Burn", "Shuffle", "Reinforcements"}
ACTION_RULE_TITLES = {"Actions"}
WEAPON_REFERENCE_TITLES = {"Weapons"}
VERIFICATION_STATUSES = {"unverified", "in_review", "verified"}
SOURCE_QUALITY_VALUES = {"poor", "fair", "good"}
REVIEW_CHECKLIST_FIELDS = ("stats", "defense", "attacks", "tags", "rulesText")
REQUIRED_STAT_KEYS = ("m", "w", "sv", "t", "sd", "stm")
SOURCE_TYPES = {"image", "pdf_page"}
CANONICAL_UNIT_NAMES = {
    "lwbt-quad-gun": "LWBT Quad gun",
    "lwbt-transport": "LWBT Transport mode",
    "lwbt-heavy-weapon": "LWBT Heavy weapon",
    "ammo-cache": "Ammo cache",
    "dreg": "Dreg",
    "breaker": "Breaker",
    "mercenary": "Mercenary",
    "dreg-captain": "Dreg captain",
    "skrap": "Skrap",
    "glaive": "Glaive",
    "champion": "Champion",
    "pistolier": "Pistolier",
    "rampager": "Rampager",
    "shawka": "Shawka",
    "hunter": "Hunter",
    "scout": "Scout",
    "keeper-of-secrets": "Keeper of secrets",
    "light-buggy": "Light buggy",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def ensure_list(value: object, field_name: str, path: Path) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{path}: expected '{field_name}' to be a list")
    return value


def ensure_dict(value: object, field_name: str, path: Path) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected '{field_name}' to be an object")
    return value


def ensure_string_list(values: object, field_name: str, path: Path) -> list[str]:
    items = ensure_list(values, field_name, path)
    for index, item in enumerate(items):
        if not isinstance(item, str):
            raise ValueError(f"{path}: {field_name}[{index}] must be a string")
    return items


def resolve_relative_path(value: str, base_root: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (base_root / path).resolve()


def validate_sections(sections: object, field_name: str, path: Path) -> list[dict]:
    items = ensure_list(sections, field_name, path)
    for index, section in enumerate(items):
        if not isinstance(section, dict):
            raise ValueError(f"{path}: {field_name}[{index}] must be an object")
        if not str(section.get("id") or "").strip():
            raise ValueError(f"{path}: {field_name}[{index}] is missing id")
        if not str(section.get("title") or "").strip():
            raise ValueError(f"{path}: {field_name}[{index}] is missing title")
        ensure_list(section.get("body"), f"{field_name}[{index}].body", path)
    return items


def validate_rules_payload(payload: dict, path: Path) -> dict:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError(f"{path}: unsupported schemaVersion {payload.get('schemaVersion')}")
    validate_sections(payload.get("sections"), "sections", path)
    return payload


def validate_factions_payload(payload: dict, path: Path) -> dict:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError(f"{path}: unsupported schemaVersion {payload.get('schemaVersion')}")
    groups = ensure_list(payload.get("groups"), "groups", path)
    for index, group in enumerate(groups):
        if not isinstance(group, dict):
            raise ValueError(f"{path}: groups[{index}] must be an object")
        if not str(group.get("id") or "").strip():
            raise ValueError(f"{path}: groups[{index}] is missing id")
        if not str(group.get("title") or "").strip():
            raise ValueError(f"{path}: groups[{index}] is missing title")
        validate_sections(group.get("sections"), f"groups[{index}].sections", path)
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


def validate_stat_block(stats: list[dict], path: Path) -> None:
    validate_source_text_entries(stats, "stats", path)
    stat_keys = []
    for index, stat in enumerate(stats):
        key = str(stat.get("key") or "").strip().lower()
        label = str(stat.get("label") or "").strip()
        if not key:
            raise ValueError(f"{path}: stats[{index}].key is required")
        if not label:
            raise ValueError(f"{path}: stats[{index}].label is required")
        if stat.get("value") in (None, ""):
            raise ValueError(f"{path}: stats[{index}].value is required")
        stat_keys.append(key)
    if tuple(stat_keys) != REQUIRED_STAT_KEYS:
        raise ValueError(f"{path}: stats must contain keys in order {list(REQUIRED_STAT_KEYS)}")


def validate_defense_block(defense: list[dict], path: Path) -> None:
    validate_source_text_entries(defense, "defense", path)
    for index, entry in enumerate(defense):
        if not str(entry.get("key") or "").strip():
            raise ValueError(f"{path}: defense[{index}].key is required")
        if not str(entry.get("label") or "").strip():
            raise ValueError(f"{path}: defense[{index}].label is required")
        if entry.get("value") in (None, ""):
            raise ValueError(f"{path}: defense[{index}].value is required")


def validate_attack_block(attacks: list[dict], path: Path) -> None:
    validate_source_text_entries(attacks, "attacks", path)
    for index, attack in enumerate(attacks):
        if not str(attack.get("name") or "").strip():
            raise ValueError(f"{path}: attacks[{index}].name is required")
        for field_name in ("kind", "range", "atk", "hit", "str", "aoe", "dmg"):
            if attack.get(field_name) in (None, ""):
                raise ValueError(f"{path}: attacks[{index}].{field_name} is required")
        if "notes" in attack:
            ensure_string_list(attack.get("notes"), f"attacks[{index}].notes", path)


def validate_source_block(payload: dict, unit_id: str, path: Path, source_root: Path, base_root: Path) -> dict:
    source = ensure_dict(payload.get("source"), "source", path)
    source_type = str(source.get("type") or "").strip()
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"{path}: source.type must be one of {sorted(SOURCE_TYPES)}")

    output_name = str(source.get("outputName") or "").strip()
    if output_name and Path(output_name).name != output_name:
        raise ValueError(f"{path}: source.outputName must be a filename, not a path")

    if source_type == "image":
        file_name = str(source.get("file") or "").strip()
        if not file_name:
            raise ValueError(f"{path}: source.file is required for image sources")
        input_path = resolve_relative_path(file_name, source_root)
        if not input_path.exists():
            raise ValueError(f"{path}: source image not found: {input_path}")
        return {
            "type": "image",
            "file": file_name,
            "inputPath": input_path,
            "outputName": output_name or Path(file_name).name,
            "sortOrder": int(source.get("sortOrder") or 9999),
        }

    file_name = str(source.get("file") or "").strip()
    if not file_name:
        raise ValueError(f"{path}: source.file is required for pdf_page sources")
    page = source.get("page")
    if not isinstance(page, int) or page < 1:
        raise ValueError(f"{path}: source.page must be a positive integer")
    input_path = resolve_relative_path(file_name, base_root)
    if not input_path.exists():
        raise ValueError(f"{path}: source pdf not found: {input_path}")
    return {
        "type": "pdf_page",
        "file": file_name,
        "inputPath": input_path,
        "page": page,
        "outputName": output_name or f"{unit_id}.png",
        "sortOrder": int(source.get("sortOrder") or page),
    }


def validate_card_payload(payload: dict, path: Path, source_root: Path, base_root: Path) -> dict:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError(f"{path}: unsupported schemaVersion {payload.get('schemaVersion')}")

    required_strings = ("unitId", "name")
    for field_name in required_strings:
        if not str(payload.get(field_name) or "").strip():
            raise ValueError(f"{path}: missing required field '{field_name}'")

    unit_id = str(payload["unitId"]).strip()
    name = str(payload["name"]).strip()
    if unit_id == "pistollier" or name == "Pistollier":
        raise ValueError(f"{path}: canonical naming mismatch detected for pistolier")
    if unit_id in CANONICAL_UNIT_NAMES and name != CANONICAL_UNIT_NAMES[unit_id]:
        raise ValueError(f"{path}: canonical name for '{unit_id}' must be '{CANONICAL_UNIT_NAMES[unit_id]}'")

    points = payload.get("points")
    if not isinstance(points, int):
        raise ValueError(f"{path}: missing required field 'points'")

    max_per_squad = payload.get("maxPerSquad")
    if max_per_squad is not None and not isinstance(max_per_squad, int):
        raise ValueError(f"{path}: maxPerSquad must be an integer when present")

    stats = ensure_list(payload.get("stats"), "stats", path)
    defense = ensure_list(payload.get("defense"), "defense", path)
    attacks = ensure_list(payload.get("attacks"), "attacks", path)
    tags = ensure_string_list(payload.get("tags"), "tags", path)
    rules_text = ensure_string_list(payload.get("rulesText"), "rulesText", path)
    special_rules = ensure_string_list(payload.get("specialRules"), "specialRules", path)

    validate_stat_block(stats, path)
    validate_defense_block(defense, path)
    validate_attack_block(attacks, path)
    verification = validate_verification_block(payload, path)
    source = validate_source_block(payload, unit_id, path, source_root, base_root)

    return {
        **payload,
        "unitId": unit_id,
        "name": name,
        "points": points,
        "tags": tags,
        "rulesText": rules_text,
        "specialRules": special_rules,
        "verification": verification,
        "source": source,
    }


def load_rules(data_root: Path) -> dict:
    rules_path = data_root / "rules.json"
    return validate_rules_payload(load_json(rules_path), rules_path)


def load_factions(data_root: Path) -> dict:
    factions_path = data_root / "factions.json"
    return validate_factions_payload(load_json(factions_path), factions_path)


def load_cards(data_root: Path, source_root: Path) -> list[dict]:
    cards_dir = data_root / "cards"
    records = []
    seen_ids: set[str] = set()
    base_root = data_root.parent.resolve()
    for path in sorted(cards_dir.glob("*.json")):
        payload = validate_card_payload(load_json(path), path, source_root, base_root)
        unit_id = payload["unitId"]
        if unit_id in seen_ids:
            raise ValueError(f"Duplicate unitId detected: {unit_id}")
        seen_ids.add(unit_id)
        records.append(payload)
    if not records:
        raise ValueError(f"No card files found in {cards_dir}")
    return sorted(records, key=lambda card: (card["source"]["sortOrder"], card["name"]))


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
        {
            "id": "actions",
            "title": "Actions",
            "sections": [section for section in sections if section["title"] in ACTION_RULE_TITLES],
        },
        {
            "id": "weapons-reference",
            "title": "Weapons Reference",
            "sections": [section for section in sections if section["title"] in WEAPON_REFERENCE_TITLES],
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


def normalize_card(card: dict, asset_url: str) -> dict:
    verification = card["verification"]
    unresolved = list(verification["unresolvedFields"])
    status = verification["status"]
    source_quality = verification["sourceQuality"]
    source = card["source"]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "unitId": card["unitId"],
        "name": card["name"],
        "points": card["points"],
        "maxPerSquad": card.get("maxPerSquad"),
        "stats": list(card["stats"]),
        "defense": list(card["defense"]),
        "attacks": list(card["attacks"]),
        "tags": list(card["tags"]),
        "specialRules": list(card["specialRules"]),
        "rulesText": list(card["rulesText"]),
        "sourceImage": source["outputName"],
        "sourceImageUrl": asset_url,
        "source": {
            "type": source["type"],
            "file": source["file"],
            "page": source.get("page"),
        },
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
            "sourceImage": unit["sourceImage"],
            "sourcePage": unit["source"].get("page"),
        })
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": generated_at,
        "summary": summary,
        "cards": cards,
    }


def render_pdf_page_with_pymupdf(source_path: Path, page: int, target_path: Path) -> bool:
    try:
        import fitz  # type: ignore
    except ImportError:
        return False

    target_path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open(source_path)
    try:
        page_obj = document.load_page(page - 1)
        pixmap = page_obj.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        pixmap.save(target_path)
    finally:
        document.close()
    return True


def render_pdf_page_with_pdftoppm(source_path: Path, page: int, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    prefix = target_path.with_suffix("")
    try:
        subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-singlefile",
                "-f",
                str(page),
                "-l",
                str(page),
                str(source_path),
                str(prefix),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise RuntimeError("pdftoppm is required to render PDF source pages when PyMuPDF is unavailable") from error
    except subprocess.CalledProcessError as error:
        stderr = error.stderr.strip() if error.stderr else ""
        raise RuntimeError(f"Failed to render PDF page {page} from {source_path}: {stderr}") from error


def render_pdf_page(source_path: Path, page: int, target_path: Path) -> None:
    if render_pdf_page_with_pymupdf(source_path, page, target_path):
        return
    render_pdf_page_with_pdftoppm(source_path, page, target_path)


def render_source_assets(cards: list[dict], docs_root: Path) -> dict[str, str]:
    target_root = docs_root / SOURCE_IMAGE_DIR
    if target_root.exists():
        shutil.rmtree(target_root)
    target_root.mkdir(parents=True, exist_ok=True)

    asset_index: dict[str, str] = {}
    for card in cards:
        source = card["source"]
        target_path = target_root / source["outputName"]
        if source["type"] == "image":
            shutil.copy2(source["inputPath"], target_path)
        else:
            render_pdf_page(source["inputPath"], source["page"], target_path)
        if not target_path.exists():
            raise ValueError(f"Rendered source asset missing for {card['unitId']}: {target_path}")
        asset_index[card["unitId"]] = f"./{SOURCE_IMAGE_DIR.as_posix()}/{target_path.name}"
    return asset_index


def build_catalog(data_root: Path, docs_root: Path, source_root: Path) -> tuple[dict, dict, dict]:
    rules_payload = load_rules(data_root)
    factions_payload = load_factions(data_root)
    cards = load_cards(data_root, source_root)
    rule_groups = build_rule_groups(rules_payload)
    faction_groups = list(factions_payload["groups"])
    asset_index = render_source_assets(cards, docs_root)
    normalized_units = [normalize_card(card, asset_index[card["unitId"]]) for card in cards]
    generated_at = utc_now()
    verification_summary = build_verification_summary(normalized_units)
    verification_report = build_verification_report(normalized_units, generated_at)

    catalog = {
        "schemaVersion": SCHEMA_VERSION,
        "title": "Heaven Fall Card Library",
        "generatedAt": generated_at,
        "rules": rule_groups,
        "factions": faction_groups,
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
        "factionCount": len(faction_groups),
        "factionSectionCount": sum(len(group["sections"]) for group in faction_groups),
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
        help="Path used to resolve image-based source assets for fixtures and archived captures.",
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
