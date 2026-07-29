import argparse
import json
from pathlib import Path

import pandas as pd

try:
    from bson import json_util
except ImportError:
    json_util = None

from pull_engagement import INSTA_TEAMS_DICT


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "instagram_sov_engagement.xlsx"
COMMENT_WEIGHT = 0.65
LIKE_WEIGHT = 0.35
DEFAULT_SMOOTHING_POSTS = 10.0


def load_json_records(path):
    raw_json = path.read_text(encoding="utf-8")
    if json_util is not None:
        records = json_util.loads(raw_json)
    else:
        records = json.loads(raw_json)

    if not isinstance(records, list):
        raise ValueError(f"{path} must contain a JSON array")

    return records


def infer_league_from_path(path):
    for league in INSTA_TEAMS_DICT:
        if path.stem == league or path.stem.startswith(f"{league}_"):
            return league
    return None


def as_number(value):
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def comments_are_countable(record):
    is_disabled = record.get("isCommentsDisabled")
    if isinstance(is_disabled, bool):
        return not is_disabled
    if isinstance(is_disabled, str):
        return is_disabled.strip().lower() == "false"
    return is_disabled is None


def normalize_username(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def coauthor_usernames(record):
    coauthors = record.get("coauthorProducers")
    if not isinstance(coauthors, list):
        return set()

    usernames = set()
    for coauthor in coauthors:
        if not isinstance(coauthor, dict):
            continue

        username = normalize_username(coauthor.get("username"))
        if username:
            usernames.add(username)

    return usernames


def attribution_usernames(record):
    usernames = coauthor_usernames(record)
    owner_username = normalize_username(record.get("ownerUsername"))
    if owner_username:
        usernames.add(owner_username)
    return usernames


def adjusted_per_post_rate(total_count, post_count, league_average, smoothing_posts):
    denominator = post_count + smoothing_posts
    if denominator <= 0:
        return 0.0
    return (total_count + (smoothing_posts * league_average)) / denominator


def calculate_league_sov(league, records, smoothing_posts=DEFAULT_SMOOTHING_POSTS):
    teams = INSTA_TEAMS_DICT[league]
    league_like_count = 0.0
    league_comment_count = 0.0
    league_post_count = 0
    league_commentable_post_count = 0
    normalized_records = []

    for record in records:
        if not isinstance(record, dict):
            continue

        likes_count = as_number(record.get("likesCount"))
        comments_count = as_number(record.get("commentsCount"))
        should_count_comments = comments_are_countable(record)

        league_like_count += likes_count
        league_post_count += 1
        if should_count_comments:
            league_comment_count += comments_count
            league_commentable_post_count += 1

        normalized_records.append(
            {
                "record": record,
                "likes_count": likes_count,
                "comments_count": comments_count,
                "should_count_comments": should_count_comments,
                "attribution_usernames": attribution_usernames(record),
            }
        )

    league_avg_likes_per_post = (
        league_like_count / league_post_count
        if league_post_count
        else 0.0
    )
    league_avg_comments_per_post = (
        league_comment_count / league_commentable_post_count
        if league_commentable_post_count
        else 0.0
    )

    rows = []
    for team in teams:
        team_key = normalize_username(team)
        team_like_count = 0.0
        team_comment_count = 0.0
        team_post_count = 0
        team_commentable_post_count = 0

        for normalized_record in normalized_records:
            if team_key not in normalized_record["attribution_usernames"]:
                continue

            team_post_count += 1
            team_like_count += normalized_record["likes_count"]
            if normalized_record["should_count_comments"]:
                team_commentable_post_count += 1
                team_comment_count += normalized_record["comments_count"]

        adjusted_comment_per_post = adjusted_per_post_rate(
            team_comment_count,
            team_commentable_post_count,
            league_avg_comments_per_post,
            smoothing_posts,
        )
        adjusted_like_per_post = adjusted_per_post_rate(
            team_like_count,
            team_post_count,
            league_avg_likes_per_post,
            smoothing_posts,
        )

        rows.append(
            {
                "ownerUsername": team,
                "adjusted_comment_per_post": adjusted_comment_per_post,
                "adjusted_like_per_post": adjusted_like_per_post,
            }
        )

    adjusted_comment_rate_total = sum(
        row["adjusted_comment_per_post"] for row in rows
    )
    adjusted_like_rate_total = sum(row["adjusted_like_per_post"] for row in rows)

    for row in rows:
        team_comment_ratio = (
            row["adjusted_comment_per_post"] / adjusted_comment_rate_total
            if adjusted_comment_rate_total
            else 0.0
        )
        team_like_ratio = (
            row["adjusted_like_per_post"] / adjusted_like_rate_total
            if adjusted_like_rate_total
            else 0.0
        )
        team_sov = (COMMENT_WEIGHT * team_comment_ratio) + (LIKE_WEIGHT * team_like_ratio)

        row["team_comment_ratio"] = team_comment_ratio
        row["team_like_ratio"] = team_like_ratio
        row["team_sov"] = team_sov

        del row["adjusted_comment_per_post"]
        del row["adjusted_like_per_post"]

    return rows, {
        "league": league,
        "league_like_count": league_like_count,
        "league_comment_count": league_comment_count,
        "league_post_count": league_post_count,
        "league_commentable_post_count": league_commentable_post_count,
        "smoothing_posts": smoothing_posts,
        "team_sov_sum": sum(row["team_sov"] for row in rows),
    }


def iter_league_json_files(data_dir):
    for path in sorted(data_dir.glob("*.json")):
        league = infer_league_from_path(path)
        if league is not None:
            yield league, path


def write_sov_workbook(dataframes_by_league, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for league, dataframe in dataframes_by_league.items():
            dataframe.to_excel(writer, sheet_name=league[:31], index=False)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Estimate Instagram SOV by league from data/*_raw_data.json files."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DATA_DIR,
        help=f"Directory containing league JSON files. Default: {DATA_DIR}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Output Excel file path. Default: {DEFAULT_OUTPUT_PATH}",
    )
    parser.add_argument(
        "--smoothing-posts",
        type=float,
        default=DEFAULT_SMOOTHING_POSTS,
        help=(
            "Number of league-average posts blended into each team's per-post rate. "
            f"Default: {DEFAULT_SMOOTHING_POSTS:g}"
        ),
    )
    return parser.parse_args()


def main():
    args = parse_args()
    data_dir = args.data_dir.resolve()
    output_path = args.output.resolve()

    if not data_dir.is_dir():
        raise NotADirectoryError(f"{data_dir} does not exist or is not a directory")
    if args.smoothing_posts < 0:
        raise ValueError("--smoothing-posts must be greater than or equal to 0")

    dataframes_by_league = {}
    validation_rows = []

    for league, path in iter_league_json_files(data_dir):
        records = load_json_records(path)
        rows, validation = calculate_league_sov(
            league,
            records,
            smoothing_posts=args.smoothing_posts,
        )
        dataframes_by_league[league] = pd.DataFrame(
            rows,
            columns=[
                "ownerUsername",
                "team_comment_ratio",
                "team_like_ratio",
                "team_sov",
            ],
        )
        validation_rows.append(validation)

    if not dataframes_by_league:
        raise RuntimeError(f"No league JSON files were found in {data_dir}")

    write_sov_workbook(dataframes_by_league, output_path)

    print(f"Excel file written to {output_path}")
    print()
    print("SOV validation by league:")
    needs_review = False
    for validation in validation_rows:
        team_sov_sum = validation["team_sov_sum"]
        difference = team_sov_sum - 1.0
        status = "OK" if abs(difference) <= 1e-9 else "CHECK"
        needs_review = needs_review or status == "CHECK"
        print(
            f"{validation['league']}: team_sov_sum={team_sov_sum:.12f} "
            f"difference_from_1={difference:.12f} status={status}"
        )

    if needs_review:
        print()
        print(
            "CHECK means the team SOV values do not add exactly to 1. This can happen "
            "when a coauthored post is credited to more than one team while the league "
            "denominator counts that post once."
        )


if __name__ == "__main__":
    main()
