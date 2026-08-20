import csv
import argparse
from .fetch_data import CodeforcesFetcher
from .paths import ANALYSIS_DIR, ensure_directory
from .plot_results import plot_from_csv

def get_problem_root(index):
    root = index.rstrip('0123456789')
    if not root:
        return index
    return root

def calculate_problem_times(submissions, contest_start_time=0):
    """
    计算用户通过的所有题目的耗费时间
    submissions: 该用户在该场比赛的所有有效提交 (已按ID降序排列，即时间倒序)
    """
    # 1. 筛选出 AC 的提交，并按时间正序排列
    # 同时我们需要所有提交来确定"本题最早一次提交时间"
    
    # 按题目分组提交
    submissions_by_problem = {}
    ac_submissions = []
    
    # Codeforces API returns submissions in reverse chronological order (newest first)
    # We reverse it to be chronological
    sorted_submissions = sorted(submissions, key=lambda x: x["creationTimeSeconds"])
    
    for sub in sorted_submissions:
        prob_index = sub["problem"]["index"]
        if prob_index not in submissions_by_problem:
            submissions_by_problem[prob_index] = []
        submissions_by_problem[prob_index].append(sub)
        
        if sub.get("verdict") == "OK":
            # Check if this problem is already AC'd by this user?
            # The problem statement implies we just want "the" AC time. 
            # Usually only the first AC matters.
            already_ac = False
            for ac in ac_submissions:
                if ac["problem"]["index"] == prob_index:
                    already_ac = True
                    break
            if not already_ac:
                ac_submissions.append(sub)
    
    # ac_submissions is now sorted by time (because sorted_submissions was)
    
    results = {}
    
    for i, ac_sub in enumerate(ac_submissions):
        prob_index = ac_sub["problem"]["index"]
        ac_time = ac_sub["relativeTimeSeconds"]
        
        # 本题最早一次提交时间
        first_sub_time = submissions_by_problem[prob_index][0]["relativeTimeSeconds"]
        
        # Find previous valid AC time (skipping sibling problems like F1/F2)
        prev_ac_time = 0
        current_root = get_problem_root(prob_index)
        
        # Look backwards from i-1
        for j in range(i - 1, -1, -1):
            prev_sub = ac_submissions[j]
            prev_index = prev_sub["problem"]["index"]
            prev_root = get_problem_root(prev_index)
            
            if prev_root != current_root:
                prev_ac_time = prev_sub["relativeTimeSeconds"]
                break
        
        start_time = min(prev_ac_time, first_sub_time)
            
        duration = ac_time - start_time
        results[prob_index] = duration
        
    return results

def main():
    parser = argparse.ArgumentParser(description='Analyze Codeforces contest data.')
    parser.add_argument('contest_id', type=int, nargs='?', help='The ID of the contest to analyze')
    args = parser.parse_args()

    if args.contest_id:
        contest_id = args.contest_id
    else:
        try:
            contest_id = int(input("请输入比赛ID: "))
        except ValueError:
            print("无效的比赛ID")
            return

    fetcher = CodeforcesFetcher()
    
    print(f"Fetching data for contest {contest_id}...")
    
    # 1. Get all participants
    participants = fetcher.get_valid_participants(contest_id)
    print(f"Found {len(participants)} participants.")
    
    # Get contest start time for filtering
    contest_start_time = fetcher.get_contest_start_time(contest_id)

    # 2. Get all submissions for the contest (bulk fetch is better if possible, 
    # but our fetcher currently does per-user or per-contest. 
    # Let's use per-contest fetching if we implemented it, or loop users.
    # Since we added get_all_contest_submissions, let's use it.)
    
    print("Fetching all submissions...")
    all_submissions = fetcher.get_all_contest_submissions(contest_id)
    print(f"Found {len(all_submissions)} submissions.")
    
    # Group submissions by handle
    subs_by_handle = {}
    for sub in all_submissions:
        # Filter for valid participants only? 
        # The prompt says "对于指定比赛的指定有效参赛者...获取他们所有的提交"
        # We should filter by the participant types we care about.
        
        # Note: sub['author']['members'] is a list.
        # For individual contests, it has 1 member.
        # We need to match this with our participants list.
        
        # Let's just use the handle from the submission author
        # And check if the participant type is valid
        p_type = sub["author"]["participantType"]
        if p_type == "CONTESTANT":
            for member in sub["author"]["members"]:
                h = member["handle"]
                if h not in subs_by_handle:
                    subs_by_handle[h] = []
                subs_by_handle[h].append(sub)

    # 3. Process each participant
    output_data = []
    
    # Get problem list to ensure CSV columns are consistent
    problems = fetcher.get_contest_problems(contest_id)
    problem_indices = sorted([p["index"] for p in problems])
    
    header = ["handle", "rating"] + problem_indices
    
    count = 0
    for p in participants:
        handle = p["handle"]
        p_type = p["participantType"]
        
        if handle not in subs_by_handle:
            continue
            
        user_subs = subs_by_handle[handle]
        
        # Calculate times
        times = calculate_problem_times(user_subs)
        
        if not times:
            continue

        # Get rating
        rating = fetcher.get_user_rating(contest_id, handle, p_type)
        
        row = {
            "handle": handle,
            "rating": rating
        }
        
        for idx in problem_indices:
            row[idx] = times.get(idx, "")
            
        output_data.append(row)
        
        count += 1
        if count % 100 == 0:
            print(f"Processed {count} users...")

    print(f"Total processed: {count}")

    # 4. Write to CSV
    csv_file = ensure_directory(ANALYSIS_DIR) / f"contest_{contest_id}_analysis.csv"
    print(f"Writing results to {csv_file}...")
    
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(output_data)
        
    print("Done!")
    
    # 5. Plot results
    print("Generating plots...")
    plot_from_csv(csv_file)

if __name__ == "__main__":
    main()
