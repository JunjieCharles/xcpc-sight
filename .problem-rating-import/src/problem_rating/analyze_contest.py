"""Create a per-user solve-time analysis for one Codeforces contest."""

import argparse
import csv
from collections import defaultdict

from .fetch_data import CodeforcesFetcher
from .paths import ANALYSIS_DIR, ensure_directory
from .plot_results import plot_from_csv
from .solve_features import calculate_problem_times, get_problem_root as get_problem_root


def main():
    parser = argparse.ArgumentParser(description="Analyze Codeforces contest data.")
    parser.add_argument(
        "contest_id", type=int, nargs="?", help="The Codeforces contest ID"
    )
    args = parser.parse_args()

    if args.contest_id:
        contest_id = args.contest_id
    else:
        try:
            contest_id = int(input("Contest ID: "))
        except ValueError:
            print("Invalid contest ID")
            return

    fetcher = CodeforcesFetcher()
    print(f"Fetching data for contest {contest_id}...")

    participants = fetcher.get_valid_participants(contest_id)
    print(f"Found {len(participants)} participants.")

    print("Fetching all submissions...")
    all_submissions = fetcher.get_all_contest_submissions(contest_id)
    print(f"Found {len(all_submissions)} submissions.")

    submissions_by_handle = defaultdict(list)
    for submission in all_submissions:
        author = submission.get("author") or {}
        if author.get("participantType") != "CONTESTANT":
            continue
        for member in author.get("members") or []:
            submissions_by_handle[member["handle"]].append(submission)

    problems = fetcher.get_contest_problems(contest_id)
    problem_indices = sorted(problem["index"] for problem in problems)
    rating_changes = fetcher._make_request(
        "contest.ratingChanges", {"contestId": contest_id}
    )
    ratings = {
        change["handle"]: change["newRating"]
        for change in rating_changes
        if "newRating" in change
    }

    output_data = []
    for participant in participants:
        handle = participant["handle"]
        user_submissions = submissions_by_handle.get(handle)
        if not user_submissions:
            continue

        # The compatibility function now uses prev1 and no first attempt.
        times = calculate_problem_times(user_submissions)
        if not times:
            continue

        row = {"handle": handle, "rating": ratings.get(handle)}
        row.update({index: times.get(index, "") for index in problem_indices})
        output_data.append(row)
        if len(output_data) % 100 == 0:
            print(f"Processed {len(output_data)} users...")

    print(f"Total processed: {len(output_data)}")
    csv_file = ensure_directory(ANALYSIS_DIR) / f"contest_{contest_id}_analysis.csv"
    print(f"Writing results to {csv_file}...")
    with csv_file.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(
            output_file, fieldnames=["handle", "rating", *problem_indices]
        )
        writer.writeheader()
        writer.writerows(output_data)

    print("Generating plots...")
    plot_from_csv(csv_file)


if __name__ == "__main__":
    main()
