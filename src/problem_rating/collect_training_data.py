import csv
from .analyze_contest import calculate_problem_times
from .fetch_data import CodeforcesFetcher
from .paths import PROCESSED_DATA_DIR, ensure_directory

def get_recent_contests(fetcher, limit=10):
    print("Fetching contest list...")
    contests = fetcher._make_request("contest.list", {"gym": "false"})
    
    target_contests = []
    for c in contests:
        if c["phase"] == "FINISHED":
            target_contests.append(c)
            if len(target_contests) >= limit:
                break
    
    return target_contests

def process_contest(fetcher, contest, writer):
    contest_id = contest["id"]
    contest_name = contest["name"]
    print(f"\nProcessing Contest {contest_id}: {contest_name}")
    
    # 1. Get Problems and Official Ratings
    problems_data = fetcher.get_contest_problems(contest_id)
    problem_ratings = {}
    for p in problems_data:
        if "rating" in p:
            problem_ratings[p["index"]] = p["rating"]
            
    if not problem_ratings:
        print("No rated problems found. Skipping.")
        return

    print(f"Rated Problems: {len(problem_ratings)}")

    # 2. Get User Ratings (Old Rating)
    # We use ratingChanges to get the rating BEFORE the contest
    try:
        rating_changes = fetcher._make_request("contest.ratingChanges", {"contestId": contest_id})
    except Exception as e:
        print(f"Failed to fetch rating changes: {e}")
        return

    user_ratings = {}
    if rating_changes:
        for rc in rating_changes:
            user_ratings[rc["handle"]] = rc["oldRating"]
    else:
        print("No rating changes found. Skipping.")
        return
        
    print(f"Rated Participants: {len(user_ratings)}")

    # 3. Get Submissions
    try:
        all_submissions = fetcher.get_all_contest_submissions(contest_id)
    except Exception as e:
        print(f"Failed to fetch submissions: {e}")
        return

    # 4. Group by User
    submissions_by_user = {}
    for sub in all_submissions:
        if "author" in sub and "members" in sub["author"]:
            # Filter by participantType as requested
            p_type = sub["author"].get("participantType")
            if p_type != "CONTESTANT":
                continue

            handle = sub["author"]["members"][0]["handle"]
            # Only process if we have a rating for this user
            if handle in user_ratings:
                if handle not in submissions_by_user:
                    submissions_by_user[handle] = []
                submissions_by_user[handle].append(sub)

    # 5. Calculate Times and Write to CSV
    row_count = 0
    for handle, subs in submissions_by_user.items():
        # No need for hardcoded time filter if we trust participantType
        rating = user_ratings[handle]
        times = calculate_problem_times(subs)
        
        for p_idx, time_sec in times.items():
            # Only if problem has an official rating
            if p_idx in problem_ratings:
                # Use seconds, clamp to 1 second to avoid zero
                if time_sec < 1.0: time_sec = 1.0
                
                writer.writerow({
                    "contestId": contest_id,
                    "problemIndex": p_idx,
                    "problemRating": problem_ratings[p_idx],
                    "userRating": rating,
                    "timeConsumed": time_sec
                })
                row_count += 1
                
    print(f"Saved {row_count} rows for contest {contest_id}.")

def main():
    fetcher = CodeforcesFetcher()
    
    # Find contests
    contests = get_recent_contests(fetcher, limit=100)
    print(f"Found {len(contests)} contests:")
    for c in contests:
        print(f"- {c['id']}: {c['name']}")
        
    output_file = ensure_directory(PROCESSED_DATA_DIR) / "training_data.csv"
    
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["contestId", "problemIndex", "problemRating", "userRating", "timeConsumed"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for contest in contests:
            process_contest(fetcher, contest, writer)
            
    print(f"\nData collection complete. Saved to {output_file}")

if __name__ == "__main__":
    main()
