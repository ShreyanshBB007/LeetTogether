import requests
from datetime import datetime
import pytz

def fetch_recent_submissions(username):
    """Fetch recent submissions from LeetCode GraphQL API"""
    url = "https://leetcode.com/graphql"

    query = """
    query recentSubmissions($username: String!) {
      recentSubmissionList(username: $username, limit: 20) {
        title
        titleSlug
        timestamp
        statusDisplay
      }
    }
    """

    variables = {"username": username}

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json={"query": query, "variables": variables},
            timeout=10
        )
        data = response.json()
        if data.get("data") and data["data"].get("recentSubmissionList"):
            return data["data"]["recentSubmissionList"]
        return []
    except Exception as e:
        print(f"Error fetching submissions for {username}: {e}")
        return []

def fetch_all_solved_problems(username):
    """Fetch all problems the user has ever solved (AC submissions)"""
    url = "https://leetcode.com/graphql"

    query = """
    query userProblemsSolved($username: String!) {
      recentAcSubmissionList(username: $username, limit: 100) {
        title
        titleSlug
        timestamp
      }
    }
    """

    variables = {"username": username}

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json={"query": query, "variables": variables},
            timeout=10
        )
        data = response.json()
        if data.get("data") and data["data"].get("recentAcSubmissionList"):
            return data["data"]["recentAcSubmissionList"]
        return []
    except Exception as e:
        print(f"Error fetching solved problems for {username}: {e}")
        return []

def fetch_problem_details(title_slug):
    """Fetch problem details including difficulty"""
    url = "https://leetcode.com/graphql"

    query = """
    query questionData($titleSlug: String!) {
      question(titleSlug: $titleSlug) {
        title
        titleSlug
        difficulty
        topicTags {
          name
        }
      }
    }
    """

    variables = {"titleSlug": title_slug}

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json={"query": query, "variables": variables},
            timeout=10
        )
        data = response.json()
        if data.get("data") and data["data"].get("question"):
            return data["data"]["question"]
        return None
    except Exception as e:
        print(f"Error fetching problem details for {title_slug}: {e}")
        return None

def fetch_user_stats(username):
    """Fetch user's overall stats including difficulty breakdown"""
    url = "https://leetcode.com/graphql"

    query = """
    query userStats($username: String!) {
      matchedUser(username: $username) {
        username
        submitStatsGlobal {
          acSubmissionNum {
            difficulty
            count
          }
        }
        profile {
          ranking
          reputation
        }
      }
    }
    """

    variables = {"username": username}

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json={"query": query, "variables": variables},
            timeout=10
        )
        data = response.json()
        if data.get("data") and data["data"].get("matchedUser"):
            return data["data"]["matchedUser"]
        return None
    except Exception as e:
        print(f"Error fetching user stats for {username}: {e}")
        return None

def get_problems_solved_before_today(username):
    """Get set of problem slugs that were solved before today"""
    all_solved = fetch_all_solved_problems(username)
    
    if not all_solved:
        return set()
    
    ist = pytz.timezone("Asia/Kolkata")
    today = datetime.now(ist).date()
    
    solved_before_today = set()
    
    for s in all_solved:
        ts = int(s["timestamp"])
        ist_time = datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.utc).astimezone(ist)
        
        # If solved before today, add to the set
        if ist_time.date() < today:
            solved_before_today.add(s.get("titleSlug", ""))
    
    return solved_before_today

def has_user_solved_today(username):
    """Check if user has solved at least one NEW problem today (IST)"""
    submissions = fetch_recent_submissions(username)
    
    if not submissions:
        return False

    # Get problems solved before today
    previously_solved = get_problems_solved_before_today(username)

    ist = pytz.timezone("Asia/Kolkata")
    today = datetime.now(ist).date()

    for submission in submissions:
        ts = int(submission["timestamp"])
        status = submission["statusDisplay"]
        title_slug = submission.get("titleSlug", "")

        utc_time = datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.utc)
        ist_time = utc_time.astimezone(ist)

        # Only count if: Accepted, solved today, AND not previously solved
        if status == "Accepted" and ist_time.date() == today:
            if title_slug not in previously_solved:
                return True

    return False

def get_today_accepted_count(leetcode_username):
    """Get the count of NEW problems solved today"""
    submissions = fetch_recent_submissions(leetcode_username)

    if not submissions:
        return 0

    # Get problems solved before today
    previously_solved = get_problems_solved_before_today(leetcode_username)

    ist = pytz.timezone("Asia/Kolkata")
    today = datetime.now(ist).date()

    count = 0
    seen_titles = set()  # Avoid counting same problem multiple times today
    
    for s in submissions:
        if s["statusDisplay"] != "Accepted":
            continue

        title_slug = s.get("titleSlug", "")
        if title_slug in seen_titles:
            continue
        
        # Skip if already solved before today
        if title_slug in previously_solved:
            continue
            
        ts = int(s["timestamp"])
        time = datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.utc).astimezone(ist)

        if time.date() == today:
            count += 1
            seen_titles.add(title_slug)

    return count

def get_today_solved_problems(username):
    """Get list of NEW problems solved today"""
    submissions = fetch_recent_submissions(username)
    
    if not submissions:
        return []
    
    # Get problems solved before today
    previously_solved = get_problems_solved_before_today(username)
    
    ist = pytz.timezone("Asia/Kolkata")
    today = datetime.now(ist).date()
    
    solved = []
    seen_titles = set()
    
    for s in submissions:
        if s["statusDisplay"] != "Accepted":
            continue
            
        title = s.get("title", "")
        title_slug = s.get("titleSlug", "")
        
        if title_slug in seen_titles:
            continue
        
        # Skip if already solved before today
        if title_slug in previously_solved:
            continue
        
        ts = int(s["timestamp"])
        ist_time = datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.utc).astimezone(ist)
        
        if ist_time.date() == today:
            solved.append({
                "title": title,
                "titleSlug": title_slug,
                "timestamp": ts,
                "time": ist_time.strftime("%H:%M")
            })
            seen_titles.add(title_slug)
    
    return solved

def get_today_solved_with_difficulty(username):
    """Get list of NEW problems solved today with difficulty info"""
    problems = get_today_solved_problems(username)
    
    for p in problems:
        details = fetch_problem_details(p["titleSlug"])
        if details:
            p["difficulty"] = details.get("difficulty", "Unknown")
            p["link"] = f"https://leetcode.com/problems/{p['titleSlug']}/"
        else:
            p["difficulty"] = "Unknown"
            p["link"] = f"https://leetcode.com/problems/{p['titleSlug']}/"
    
    return problems

def get_difficulty_breakdown(username):
    """Get difficulty breakdown of all solved problems"""
    stats = fetch_user_stats(username)
    
    if not stats:
        return {"Easy": 0, "Medium": 0, "Hard": 0, "All": 0}
    
    breakdown = {"Easy": 0, "Medium": 0, "Hard": 0, "All": 0}
    
    ac_stats = stats.get("submitStatsGlobal", {}).get("acSubmissionNum", [])
    for item in ac_stats:
        diff = item.get("difficulty", "")
        count = item.get("count", 0)
        if diff in breakdown:
            breakdown[diff] = count
    
    return breakdown

def get_user_ranking(username):
    """Get user's global ranking"""
    stats = fetch_user_stats(username)
    
    if not stats or not stats.get("profile"):
        return None
    
    return stats["profile"].get("ranking")
