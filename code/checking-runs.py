import argparse
import ast
import csv
import pymongo
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    from bson import json_util
except ImportError:
    pymongo = None
    json_util = None


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
PULL_ENGAGEMENT_PATH = Path(__file__).resolve().parent / "pull_engagement.py"


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
    for path in json_files:
        all_rows.extend(summarize_file(path, insta_teams_dict))

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

    if missing_rows:
        print("Zero-result teams:")
        for row in missing_rows:
            print(f"- {row['file']}: {row['team']} ({row['league_checked']})")

    if args.output_csv:
        write_csv(all_rows, args.output_csv)
        print(f"CSV written to {args.output_csv}")


if __name__ == "__main__":
    main()
