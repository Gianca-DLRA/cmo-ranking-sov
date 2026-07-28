import argparse
import json
import os
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"


def id_key(record):
    """Return the duplicate key for a JSON object, or None when it has no id."""
    if not isinstance(record, dict) or "id" not in record:
        return None

    value = record["id"]
    if value is None or value == "":
        return None

    try:
        hash(value)
    except TypeError:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    return value


def load_records(path):
    with path.open("r", encoding="utf-8") as file:
        records = json.load(file)

    if not isinstance(records, list):
        raise ValueError(f"{path} must contain a JSON array")

    return records


def write_records_atomic(path, records, indent):
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(records, temp_file, ensure_ascii=False, indent=indent)
            temp_file.write("\n")

        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def dedupe_records(records):
    seen_ids = set()
    deduped = []
    duplicates_removed = 0

    for record in records:
        key = id_key(record)
        if key is None:
            deduped.append(record)
            continue

        if key in seen_ids:
            duplicates_removed += 1
            continue

        seen_ids.add(key)
        deduped.append(record)

    return deduped, duplicates_removed


def dedupe_file(path, dry_run=False, indent=2):
    records = load_records(path)
    deduped, duplicates_removed = dedupe_records(records)

    if duplicates_removed and not dry_run:
        write_records_atomic(path, deduped, indent)

    return {
        "file": path.name,
        "original_count": len(records),
        "final_count": len(deduped),
        "duplicates_removed": duplicates_removed,
    }


def iter_json_files(data_dir):
    return sorted(path for path in data_dir.glob("*.json") if path.is_file())


def parse_args():
    parser = argparse.ArgumentParser(
        description="Remove duplicate records from data/*.json using the id field."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DATA_DIR,
        help=f"Directory with JSON files. Default: {DATA_DIR}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report duplicates without changing files.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Write compact JSON instead of pretty-printed JSON.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    data_dir = args.data_dir.resolve()
    if not data_dir.is_dir():
        raise NotADirectoryError(f"{data_dir} does not exist or is not a directory")

    files = iter_json_files(data_dir)
    if not files:
        print(f"No JSON files found in {data_dir}")
        return

    indent = None if args.compact else 2
    total_removed = 0
    for path in files:
        stats = dedupe_file(path, dry_run=args.dry_run, indent=indent)
        total_removed += stats["duplicates_removed"]
        print(
            f"{stats['file']}: "
            f"{stats['original_count']} -> {stats['final_count']} "
            f"({stats['duplicates_removed']} duplicates removed)"
        )

    action = "would be removed" if args.dry_run else "removed"
    print(f"Total duplicates {action}: {total_removed}")


if __name__ == "__main__":
    main()
