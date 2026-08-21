import argparse
import json
import math

import numpy as np

from .analyze_contest import calculate_problem_times
from .fetch_data import CodeforcesFetcher
from .paths import MODEL_FILE


def load_model_coefficients():
    with open(MODEL_FILE, encoding="utf-8") as model_file:
        return json.load(model_file)


def estimate_difficulty(time_seconds, user_rating, coefficients):
    """
    Inverse formula from the trained Model 1:
    ln(T) = b0 + b1 * R + b2 * D
    => D = (ln(T) - b0 - b1 * R) / b2
    """
    if time_seconds <= 0:
        return None  # Should not happen for valid AC times

    intercept = coefficients["intercept"]
    rating_coefficient = coefficients["rating_coefficient"]
    difficulty_coefficient = coefficients["difficulty_coefficient"]
    ln_t = math.log(time_seconds)
    return (ln_t - intercept - rating_coefficient * user_rating) / difficulty_coefficient


def main():
    parser = argparse.ArgumentParser(
        description="Estimate problem difficulty based on user solving times."
    )
    parser.add_argument("contest_id", type=int, help="Codeforces Contest ID")
    parser.add_argument(
        "--min-rating",
        type=int,
        default=1600,
        help="Minimum user rating to consider (default: 1600)",
    )
    args = parser.parse_args()

    contest_id = args.contest_id
    fetcher = CodeforcesFetcher()

    try:
        coefficients = load_model_coefficients()
    except FileNotFoundError:
        print(f"Model file not found: {MODEL_FILE}")
        print("Run problem_rating.unified_model after collecting training data.")
        return

    print(f"Fetching data for contest {contest_id}...")

    # 1. Fetch Problems (to get official ratings if available)
    problems_data = fetcher.get_contest_problems(contest_id)
    official_ratings = {}
    problem_indices = []
    for p in problems_data:
        idx = p["index"]
        problem_indices.append(idx)
        if "rating" in p:
            official_ratings[idx] = p["rating"]

    print(f"Problems: {problem_indices}")

    # 2. Fetch User Ratings (Post-contest)
    print("Fetching rating changes...")
    rating_changes = fetcher._make_request("contest.ratingChanges", {"contestId": contest_id})
    user_ratings = {}
    if rating_changes:
        for rc in rating_changes:
            user_ratings[rc["handle"]] = rc["newRating"]
        print(f"Found {len(user_ratings)} rated participants.")
    else:
        print("No rating changes found. This might be an unrated contest or too recent.")
        # Fallback: Fetch standings to get participants, then fetch user info?
        # For now, we'll proceed. If user_ratings is empty, we can't estimate much.
        return

    # 3. Fetch All Submissions
    print("Fetching all submissions...")
    all_submissions = fetcher.get_all_contest_submissions(contest_id)
    print(f"Fetched {len(all_submissions)} submissions.")

    # 4. Group by User
    submissions_by_user = {}
    for sub in all_submissions:
        # Only consider submissions by CONTESTANT
        if "author" in sub and "members" in sub["author"]:
            p_type = sub["author"].get("participantType")
            if p_type != "CONTESTANT":
                continue

            handle = sub["author"]["members"][0]["handle"]
            if handle in user_ratings:
                if handle not in submissions_by_user:
                    submissions_by_user[handle] = []
                submissions_by_user[handle].append(sub)

    print(f"Processing submissions for {len(submissions_by_user)} rated users...")

    # 5. Calculate Times and Estimate Difficulty
    problem_estimates = {idx: [] for idx in problem_indices}

    skipped_users = 0
    for handle, subs in submissions_by_user.items():
        rating = user_ratings[handle]

        if rating < args.min_rating:
            skipped_users += 1
            continue

        # Calculate AC times
        # calculate_problem_times returns {problem_index: relativeTimeSeconds}
        times = calculate_problem_times(subs)

        for p_idx, time_sec in times.items():
            if time_sec < 60.0:
                # Avoid invalid logs and unstable estimates for extremely fast solves.
                time_sec = 60.0

            est_d = estimate_difficulty(time_sec, rating, coefficients)

            if p_idx in problem_estimates:
                problem_estimates[p_idx].append(est_d)

    # 6. Aggregate and Output
    used_users = len(submissions_by_user) - skipped_users
    print(f"Used {used_users} users (skipped {skipped_users} < {args.min_rating}).")
    print("\n" + "=" * 60)
    print(f"{'Problem':<10} | {'Official':<10} | {'Estimated':<10} | {'Samples':<10}")
    print("-" * 60)

    for idx in problem_indices:
        estimates = problem_estimates.get(idx, [])
        official = official_ratings.get(idx, "N/A")

        if estimates:
            median_est = np.median(estimates)
            count = len(estimates)
            print(f"{idx:<10} | {str(official):<10} | {median_est:.0f}{'':<6} | {count:<10}")
        else:
            print(f"{idx:<10} | {str(official):<10} | {'N/A':<10} | {0:<10}")

    print("=" * 60)


if __name__ == "__main__":
    main()
