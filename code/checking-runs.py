import argparse
import ast
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

try:
    import pymongo
    from bson import json_util
except ImportError:
    pymongo = None
    json_util = None


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
PULL_ENGAGEMENT_PATH = Path(__file__).resolve().parent / "pull_engagement.py"
POST_ID_FIELDS = ("id", "shortCode", "url")


def load_insta_teams_dict():
    """Read INSTA_TEAMS_DICT from pull_engagement.py without importing the file."""
    tree = ast.parse(PULL_ENGAGEMENT_PATH.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue

        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "INSTA_TEAMS_DICT":
                return ast.literal_eval(node.value)

    raise RuntimeError(f"INSTA_TEAMS_DICT was not found in {PULL_ENGAGEMENT_PATH}")


def load_json_file(path):
    raw = path.read_text(encoding="utf-8")
    if json_util is not None:
        return json_util.loads(raw)
    return json.loads(raw)


def normalize_post_key_value(field, value):
    if value is None:
        return None

    value = str(value).strip()
    if not value:
        return None

    if field == "url":
        parts = urlsplit(value)
        normalized_path = parts.path.rstrip("/")
        return urlunsplit(
            (
                parts.scheme.lower(),
                parts.netloc.lower(),
                normalized_path,
                "",
                "",
            )
        )

    return value


def post_identity_key(record, key_fields=POST_ID_FIELDS):
    """Return the first stable key that identifies an Instagram post."""
    if not isinstance(record, dict):
        return None

    for field in key_fields:
        value = normalize_post_key_value(field, record.get(field))
        if value:
            return field, value

    return None


def find_duplicate_documents(records, key_fields=POST_ID_FIELDS):
    """Find repeated posts in one JSON record list.

    The return value is a list of groups. Each group contains the identity key
    and every matching document position in the file.
    """
    grouped_records = defaultdict(list)

    for index, record in enumerate(records):
        key = post_identity_key(record, key_fields)
        if key is None:
            continue
        grouped_records[key].append((index, record))

    duplicates = []
    for (key_field, key_value), matches in grouped_records.items():
        if len(matches) < 2:
            continue

        duplicates.append(
            {
                "key_field": key_field,
                "key_value": key_value,
                "count": len(matches),
                "indexes": [index for index, _record in matches],
                "records": [record for _index, record in matches],
            }
        )

    return sorted(
        duplicates,
        key=lambda group: (-group["count"], group["key_field"], group["key_value"]),
    )


def parse_timestamp(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)

    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

    return None


def isoformat_or_blank(value):
    if value is None:
        return ""
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def infer_league(path, records, insta_teams_dict):
    stem = path.stem
    for league in insta_teams_dict:
        if stem == league or stem.startswith(f"{league}_"):
            return league

    leagues_in_file = Counter(
        record.get("_league")
        for record in records
        if isinstance(record, dict) and record.get("_league") in insta_teams_dict
    )
    if len(leagues_in_file) == 1:
        return next(iter(leagues_in_file))

    return None


def expected_teams_for_file(path, records, insta_teams_dict):
    league = infer_league(path, records, insta_teams_dict)
    if league:
        return league, insta_teams_dict[league]

    all_teams = sorted({team for teams in insta_teams_dict.values() for team in teams})
    return "ALL", all_teams


def summarize_file(path, insta_teams_dict):
    records = load_json_file(path)
    if not isinstance(records, list):
        raise ValueError(f"{path} does not contain a JSON list")

    league, expected_teams = expected_teams_for_file(path, records, insta_teams_dict)
    stats = defaultdict(lambda: {"count": 0, "earliest": None, "latest": None})

    for record in records:
        if not isinstance(record, dict):
            continue

        username = record.get("ownerUsername")
        if not username:
            continue

        username = username.lower()
        timestamp = parse_timestamp(record.get("timestamp"))
        team_stats = stats[username]
        team_stats["count"] += 1

        if timestamp is not None:
            if team_stats["earliest"] is None or timestamp < team_stats["earliest"]:
                team_stats["earliest"] = timestamp
            if team_stats["latest"] is None or timestamp > team_stats["latest"]:
                team_stats["latest"] = timestamp

    rows = []
    for team in expected_teams:
        team_key = team.lower()
        team_stats = stats.get(team_key, {"count": 0, "earliest": None, "latest": None})
        rows.append(
            {
                "file": path.name,
                "league_checked": league,
                "team": team,
                "posts_pulled": team_stats["count"],
                "has_non_zero_results": team_stats["count"] > 0,
                "earliest_post_timestamp": isoformat_or_blank(team_stats["earliest"]),
                "latest_post_timestamp": isoformat_or_blank(team_stats["latest"]),
            }
        )

    return rows


def summarize_duplicate_posts(path):
    records = load_json_file(path)
    if not isinstance(records, list):
        raise ValueError(f"{path} does not contain a JSON list")

    rows = []
    for group in find_duplicate_documents(records):
        first_record = group["records"][0]
        rows.append(
            {
                "file": path.name,
                "key_field": group["key_field"],
                "key_value": group["key_value"],
                "duplicate_count": group["count"],
                "indexes": ",".join(str(index) for index in group["indexes"]),
                "ownerUsername": first_record.get("ownerUsername", ""),
                "timestamp": first_record.get("timestamp", ""),
                "url": first_record.get("url", ""),
            }
        )

    return rows


def print_table(rows):
    headers = [
        "file",
        "league_checked",
        "team",
        "posts_pulled",
        "has_non_zero_results",
        "earliest_post_timestamp",
        "latest_post_timestamp",
    ]
    widths = {
        header: max(len(header), *(len(str(row[header])) for row in rows))
        for header in headers
    }

    print(" | ".join(header.ljust(widths[header]) for header in headers))
    print("-+-".join("-" * widths[header] for header in headers))
    for row in rows:
        print(" | ".join(str(row[header]).ljust(widths[header]) for header in headers))


def print_duplicate_table(rows):
    headers = [
        "file",
        "key_field",
        "key_value",
        "duplicate_count",
        "indexes",
        "ownerUsername",
        "timestamp",
        "url",
    ]
    widths = {
        header: max(len(header), *(len(str(row[header])) for row in rows))
        for header in headers
    }

    print(" | ".join(header.ljust(widths[header]) for header in headers))
    print("-+-".join("-" * widths[header] for header in headers))
    for row in rows:
        print(" | ".join(str(row[header]).ljust(widths[header]) for header in headers))


def write_csv(rows, output_path):
    headers = [
        "file",
        "league_checked",
        "team",
        "posts_pulled",
        "has_non_zero_results",
        "earliest_post_timestamp",
        "latest_post_timestamp",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def write_duplicate_csv(rows, output_path):
    headers = [
        "file",
        "key_field",
        "key_value",
        "duplicate_count",
        "indexes",
        "ownerUsername",
        "timestamp",
        "url",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Check Instagram pull JSON files for missing teams, post counts, "
            "and latest post coverage."
        )
    )
    parser.add_argument(
        "--data-dir",
        default=DATA_DIR,
        type=Path,
        help="Directory containing JSON files. Defaults to ../data.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        help="Optional CSV path where the check results will be written.",
    )
    parser.add_argument(
        "--duplicates-csv",
        type=Path,
        help="Optional CSV path where duplicate post groups will be written.",
    )
    parser.add_argument(
        "--include-test-data",
        action="store_true",
        help="Include files whose names contain 'test'.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    insta_teams_dict = load_insta_teams_dict()

    json_files = sorted(args.data_dir.glob("*.json"))
    if not args.include_test_data:
        json_files = [path for path in json_files if "test" not in path.name.lower()]

    all_rows = []
    duplicate_rows = []
    for path in json_files:
        all_rows.extend(summarize_file(path, insta_teams_dict))
        duplicate_rows.extend(summarize_duplicate_posts(path))

    if not all_rows:
        print(f"No JSON files found in {args.data_dir}")
        return

    if pymongo is None or json_util is None:
        print("WARNING: pymongo/bson is not installed; using Python's json module fallback.")
        print("Install pymongo to parse Mongo Extended JSON: python3 -m pip install pymongo")
        print()

    print_table(all_rows)

    missing_rows = [row for row in all_rows if not row["has_non_zero_results"]]
    print()
    print(f"Checked {len(json_files)} JSON file(s) and {len(all_rows)} team/file combinations.")
    print(f"Teams with zero pulled posts: {len(missing_rows)}")
    print(f"Duplicate post groups: {len(duplicate_rows)}")

    if missing_rows:
        print("Zero-result teams:")
        for row in missing_rows:
            print(f"- {row['file']}: {row['team']} ({row['league_checked']})")

    if duplicate_rows:
        print()
        print("Duplicate posts:")
        print_duplicate_table(duplicate_rows)

    if args.output_csv:
        write_csv(all_rows, args.output_csv)
        print(f"CSV written to {args.output_csv}")

    if args.duplicates_csv:
        write_duplicate_csv(duplicate_rows, args.duplicates_csv)
        print(f"Duplicate CSV written to {args.duplicates_csv}")


if __name__ == "__main__":
    main()
