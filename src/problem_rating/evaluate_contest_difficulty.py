import argparse
import numpy as np
import math
from .analyze_contest import calculate_problem_times
from .fetch_data import CodeforcesFetcher

def estimate_difficulty(time_seconds, user_rating):
    """
    Inverse formula from Model 1 (Updated with balanced samples, min_rating=1600, time in seconds):
    ln(T) = 6.7271 - 0.000847 * R + 0.001354 * D
    => D = (ln(T) - 6.7271 + 0.000847 * R) / 0.001354
    """
    if time_seconds <= 0:
        return None # Should not happen for valid AC times
    
    ln_t = math.log(time_seconds)
    d = (ln_t - 6.7271 + 0.000847 * user_rating) / 0.001354
    return d

def main():
    parser = argparse.ArgumentParser(description="Estimate problem difficulty based on user solving times.")
    parser.add_argument("contest_id", type=int, help="Codeforces Contest ID")
    parser.add_argument("--min-rating", type=int, default=1600, help="Minimum user rating to consider (default: 1600)")
    args = parser.parse_args()
    
    contest_id = args.contest_id
    fetcher = CodeforcesFetcher()
    
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
    
    # 2. Fetch User Ratings (Pre-contest)
    print("Fetching rating changes...")
    rating_changes = fetcher._make_request("contest.ratingChanges", {"contestId": contest_id})
    user_ratings = {}
    if rating_changes:
        for rc in rating_changes:
            user_ratings[rc["handle"]] = rc["oldRating"]
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
                time_sec = 60.0 # Avoid log(0) or negative log issues for extremely fast times, clamp to 60 sec
            
            est_d = estimate_difficulty(time_sec, rating)
            
            if p_idx in problem_estimates:
                problem_estimates[p_idx].append(est_d)
                
    # 6. Aggregate and Output
    print(f"Used {len(submissions_by_user) - skipped_users} users (skipped {skipped_users} < {args.min_rating}).")
    print("\n" + "="*60)
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
            
    print("="*60)

if __name__ == "__main__":
    main()
