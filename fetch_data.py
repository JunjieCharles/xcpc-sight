import requests
import json
import os
import time
import hashlib

class CodeforcesFetcher:
    def __init__(self, data_dir="data"):
        self.api_base = "https://codeforces.com/api"
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def _get_cache_filename(self, method, params):
        # Create a unique filename based on method and params
        param_str = json.dumps(params, sort_keys=True)
        hash_obj = hashlib.md5(f"{method}{param_str}".encode())
        return os.path.join(self.data_dir, f"{method}_{hash_obj.hexdigest()}.json")

    def _make_request(self, method, params=None, use_cache=True):
        if params is None:
            params = {}
        
        cache_file = self._get_cache_filename(method, params)
        
        if use_cache and os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

        url = f"{self.api_base}/{method}"
        max_retries = 5
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                print(f"Requesting {url} (Attempt {attempt + 1})...")
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if data["status"] == "OK":
                    # Save to cache
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(data["result"], f, ensure_ascii=False, indent=2)
                    return data["result"]
                else:
                    print(f"API Error: {data.get('comment')}")
                    # If it's a specific API error, maybe don't retry? 
                    # But for now we treat it as a failure.
            except requests.RequestException as e:
                print(f"Request failed: {e}")
            
            time.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff

        raise Exception(f"Failed to fetch {method} after {max_retries} attempts")

    def get_valid_participants(self, contest_id):
        """
        获取指定比赛的所有有效参赛者 (仅 CONTESTANT)
        """
        # showUnofficial=true is needed to get OUT_OF_COMPETITION, but we only want CONTESTANT now.
        # However, keeping showUnofficial=true doesn't hurt if we filter later.
        # But if we only want CONTESTANT, showUnofficial=false (default) might be enough?
        # Actually, let's keep showUnofficial=true to be safe and filter explicitly.
        data = self._make_request("contest.standings", {
            "contestId": contest_id,
            "showUnofficial": "true"
        })
        
        valid_participants = []
        for row in data["rows"]:
            party = row["party"]
            p_type = party["participantType"]
            
            if p_type == "CONTESTANT":
                # A party can have multiple members (team contest), but usually rating is individual or team handle
                # For simplicity, we'll take the members' handles.
                for member in party["members"]:
                    valid_participants.append({
                        "handle": member["handle"],
                        "participantType": p_type
                    })
                    
        return valid_participants

    def get_user_submissions(self, contest_id, handle):
        """
        获取指定比赛的指定有效参赛者所有的提交
        必须是作为有效参赛者时的提交 (仅 CONTESTANT)
        """
        # contest.status returns all submissions for a contest, optionally filtered by handle
        submissions = self._make_request("contest.status", {
            "contestId": contest_id,
            "handle": handle
        })
        
        valid_submissions = []
        for sub in submissions:
            # Filter by participant type
            # The submission author field contains participantType
            if sub["author"]["participantType"] == "CONTESTANT":
                valid_submissions.append(sub)
                
        return valid_submissions

    def get_user_rating(self, contest_id, handle, participant_type):
        """
        获取用户在这场比赛时的 rating
        CONTESTANT: 这场比赛 rating 变化后的 rating (newRating)
        """
        if participant_type == "CONTESTANT":
            # Use contest.ratingChanges
            # Note: This returns changes for ALL users in the contest. 
            # It might be heavy to call this for every single user if we don't cache it properly.
            # Ideally, we should fetch this ONCE per contest and store it in a dict.
            # But following the requested interface, we'll implement it to get it.
            # Optimization: The _make_request handles caching, so repeated calls are fine.
            rating_changes = self._make_request("contest.ratingChanges", {"contestId": contest_id})
            
            for change in rating_changes:
                if change["handle"] == handle:
                    return change["newRating"]
            
            # If not found in rating changes (e.g. unrated participant in rated contest?), return None or 0?
            # Some contests are not rated for everyone.
            return None

        return None

    def get_user_rating_history(self, handle):
        """
        获取用户 rating 历史
        """
        return self._make_request("user.rating", {"handle": handle})

    def get_contest_start_time(self, contest_id):
        """
        获取比赛开始时间
        """
        standings = self._make_request("contest.standings", {
            "contestId": contest_id,
            "from": 1,
            "count": 1
        })
        return standings["contest"]["startTimeSeconds"]

    def get_contest_problems(self, contest_id):
        """
        获取指定比赛的所有题目信息
        """
        # We only need the problem list, so we request minimal rows
        data = self._make_request("contest.standings", {
            "contestId": contest_id,
            "from": 1,
            "count": 1
        })
        return data["problems"]

    def get_all_contest_submissions(self, contest_id):
        """
        获取指定比赛的所有提交 (分页获取)
        """
        all_submissions = []
        start_index = 1
        batch_size = 10000 # Max allowed by API usually
        
        while True:
            print(f"Fetching submissions from {start_index}...")
            # We don't cache the intermediate pages permanently if we want fresh data, 
            # but for this task caching is requested. 
            # However, caching every page might be messy. 
            # Let's use the existing _make_request which caches.
            # To avoid infinite loop if cache is stale and incomplete, we trust the API/Cache.
            
            data = self._make_request("contest.status", {
                "contestId": contest_id,
                "from": start_index,
                "count": batch_size
            })
            
            if not data:
                break
                
            all_submissions.extend(data)
            
            if len(data) < batch_size:
                break
                
            start_index += batch_size
            
        return all_submissions

if __name__ == "__main__":
    fetcher = CodeforcesFetcher()
    contest_id = 1669 # Example contest ID (Codeforces Round #784 (Div. 4))
    
    print(f"Fetching participants for contest {contest_id}...")
    problems = fetcher.get_contest_problems(contest_id)
    print(f"Found {len(problems)} problems: {[p['index'] for p in problems]}")

    participants = fetcher.get_valid_participants(contest_id)
    print(f"Found {len(participants)} valid participants.")
    
    # Test with a few participants
    for p in participants[:5]:
        handle = p["handle"]
        p_type = p["participantType"]
        print(f"\nProcessing {handle} ({p_type})...")
        
        rating = fetcher.get_user_rating(contest_id, handle, p_type)
        print(f"Rating: {rating}")
        
        submissions = fetcher.get_user_submissions(contest_id, handle)
        print(f"Found {len(submissions)} submissions.")
        if submissions:
            print(f"Last submission: {submissions[0]['id']} - {submissions[0]['verdict']}")

