import csv
import re
from .analyze_contest import calculate_problem_times
from .fetch_data import CodeforcesAPIError, CodeforcesFetcher
from .paths import PROCESSED_DATA_DIR, ensure_directory


EXCLUDED_DIVISION_PATTERN = re.compile(r"\bDiv\.\s*[34]\b", re.IGNORECASE)


def get_rating_changes(fetcher, contest_id):
    try:
        rating_changes = fetcher._make_request(
            "contest.ratingChanges", {"contestId": contest_id}
        )
    except CodeforcesAPIError:
        return []

    return [change for change in rating_changes if "newRating" in change]


def get_recent_contests(fetcher, limit=10):
    print("Fetching contest list...")
    contests = fetcher._make_request("contest.list", {"gym": "false"})
    
    target_contests = []
    excluded_division_count = 0
    excluded_unrated_count = 0
    for c in contests:
        contest_name = c["name"]
        if EXCLUDED_DIVISION_PATTERN.search(contest_name):
            excluded_division_count += 1
            continue

        if c["phase"] != "FINISHED":
            continue

        if not get_rating_changes(fetcher, c["id"]):
            excluded_unrated_count += 1
            continue

        target_contests.append(c)
        if len(target_contests) >= limit:
            break

    print(f"Excluded {excluded_division_count} Div. 3/Div. 4 contests.")
    print(f"Excluded {excluded_unrated_count} unrated contests.")
    return target_contests

def process_contest(fetcher, contest, writer):
    contest_id = contest["id"]
    contest_name = contest["name"]
    contest_duration = contest.get("durationSeconds")
    print(f"\nProcessing Contest {contest_id}: {contest_name}")

    if not contest_duration:
        print("Contest duration is unavailable. Skipping.")
        return
    
    # 1. Get Problems and Official Ratings
    try:
        problems_data = fetcher.get_contest_problems(contest_id)
    except Exception as error:
        print(f"Failed to fetch contest standings: {error}")
        return

    problem_ratings = {}
    for p in problems_data:
        if "rating" in p:
            problem_ratings[p["index"]] = p["rating"]
            
    if not problem_ratings:
        print("No rated problems found. Skipping.")
        return

    print(f"Rated Problems: {len(problem_ratings)}")

    # 2. Get User Ratings (New Rating)
    # We use ratingChanges to get the rating AFTER the contest.
    user_ratings = {}
    rating_changes = get_rating_changes(fetcher, contest_id)
    if rating_changes:
        for rc in rating_changes:
            user_ratings[rc["handle"]] = rc["newRating"]
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
                    "timeConsumed": time_sec,
                    "contestDurationSeconds": contest_duration,
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
        fieldnames = [
            "contestId",
            "problemIndex",
            "problemRating",
            "userRating",
            "timeConsumed",
            "contestDurationSeconds",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for contest in contests:
            process_contest(fetcher, contest, writer)
            
    print(f"\nData collection complete. Saved to {output_file}")

if __name__ == "__main__":
    main()
