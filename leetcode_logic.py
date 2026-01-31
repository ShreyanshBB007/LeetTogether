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
    """Fetch all problems the user has ever solved (AC submissions) - last 100 only"""
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

def fetch_all_solved_problem_slugs(username):
    """Fetch ALL unique problem slugs the user has ever solved (not just recent 100)"""
    url = "https://leetcode.com/graphql"

    query = """
    query userProblemsSolved($username: String!) {
      allQuestionsCount {
        difficulty
        count
      }
      matchedUser(username: $username) {
        problemsSolvedBeatsStats {
          difficulty
          percentage
        }
        submitStatsGlobal {
          acSubmissionNum {
            difficulty
            count
          }
        }
      }
    }
    """

    # This query doesn't give us slugs, so we need a different approach
    # Use the submission list API with higher limit or pagination
    
    # Try to get solved questions list
    query2 = """
    query userProfileUserQuestionProgress($userSlug: String!) {
      userProfileUserQuestionProgress(userSlug: $userSlug) {
        numAcceptedQuestions {
          difficulty
          count
        }
      }
    }
    """
    
    # Actually, let's use the AC submission list but check for first solve date
    # by looking at ALL submissions for problems solved today
    
    variables = {"username": username}

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    # Get a larger list of recent AC submissions
    query_large = """
    query userProblemsSolved($username: String!) {
      recentAcSubmissionList(username: $username, limit: 500) {
        title
        titleSlug
        timestamp
      }
    }
    """

    try:
        response = requests.post(
            url,
            headers=headers,
            json={"query": query_large, "variables": variables},
            timeout=15
        )
        data = response.json()
        if data.get("data") and data["data"].get("recentAcSubmissionList"):
            submissions = data["data"]["recentAcSubmissionList"]
            # Return set of all unique slugs
            return {s.get("titleSlug", "") for s in submissions if s.get("titleSlug")}
        return set()
    except Exception as e:
        print(f"Error fetching all solved problem slugs for {username}: {e}")
        return set()

def get_first_solve_date(username, title_slug):
    """Get the date when user FIRST solved a problem (earliest AC submission)"""
    all_solved = fetch_all_solved_problems(username)
    
    if not all_solved:
        return None
    
    ist = pytz.timezone("Asia/Kolkata")
    earliest_date = None
    
    for s in all_solved:
        if s.get("titleSlug") == title_slug:
            ts = int(s["timestamp"])
            ist_time = datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.utc).astimezone(ist)
            if earliest_date is None or ist_time.date() < earliest_date:
                earliest_date = ist_time.date()
    
    return earliest_date

def fetch_problem_details(title_slug):
    """Fetch problem details including difficulty and question number"""
    url = "https://leetcode.com/graphql"

    query = """
    query questionData($titleSlug: String!) {
      question(titleSlug: $titleSlug) {
        questionFrontendId
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
    """Get set of problem slugs that were solved before today.
    
    Uses a larger limit (500) to catch older problems.
    For each problem, finds the EARLIEST solve date - if it's before today,
    the problem counts as previously solved.
    """
    url = "https://leetcode.com/graphql"
    
    # Fetch with higher limit to catch older solves
    query = """
    query userProblemsSolved($username: String!) {
      recentAcSubmissionList(username: $username, limit: 500) {
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
            timeout=15
        )
        data = response.json()
        all_solved = data.get("data", {}).get("recentAcSubmissionList", [])
    except Exception as e:
        print(f"Error fetching solved problems for {username}: {e}")
        all_solved = []
    
    if not all_solved:
        return set()
    
    ist = pytz.timezone("Asia/Kolkata")
    today = datetime.now(ist).date()
    
    # Track the EARLIEST solve date for each problem
    earliest_solve = {}
    
    for s in all_solved:
        title_slug = s.get("titleSlug", "")
        if not title_slug:
            continue
            
        ts = int(s["timestamp"])
        ist_time = datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.utc).astimezone(ist)
        solve_date = ist_time.date()
        
        # Keep track of earliest solve date per problem
        if title_slug not in earliest_solve or solve_date < earliest_solve[title_slug]:
            earliest_solve[title_slug] = solve_date
    
    # Return problems whose FIRST solve was before today
    solved_before_today = {
        slug for slug, first_date in earliest_solve.items() 
        if first_date < today
    }
    
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
    """Get list of NEW problems solved today with difficulty info and question number"""
    problems = get_today_solved_problems(username)
    
    for p in problems:
        details = fetch_problem_details(p["titleSlug"])
        if details:
            p["questionNo"] = details.get("questionFrontendId", "?")
            p["difficulty"] = details.get("difficulty", "Unknown")
            p["link"] = f"https://leetcode.com/problems/{p['titleSlug']}/"
        else:
            p["questionNo"] = "?"
            p["difficulty"] = "Unknown"
            p["link"] = f"https://leetcode.com/problems/{p['titleSlug']}/"
    
    return problems

def get_today_stats(username):
    """Get today's stats: unique problems, total submissions, difficulty breakdown"""
    submissions = fetch_recent_submissions(username)
    
    if not submissions:
        return {"unique": 0, "submissions": 0, "easy": 0, "medium": 0, "hard": 0}
    
    previously_solved = get_problems_solved_before_today(username)
    
    ist = pytz.timezone("Asia/Kolkata")
    today = datetime.now(ist).date()
    
    unique_problems = set()
    total_submissions = 0
    easy = 0
    medium = 0
    hard = 0
    
    for s in submissions:
        if s["statusDisplay"] != "Accepted":
            continue
        
        ts = int(s["timestamp"])
        time = datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.utc).astimezone(ist)
        
        if time.date() != today:
            continue
        
        title_slug = s.get("titleSlug", "")
        
        # Skip if already solved before today
        if title_slug in previously_solved:
            continue
        
        # Count all submissions today
        total_submissions += 1
        
        # Only count unique problems for difficulty
        if title_slug not in unique_problems:
            unique_problems.add(title_slug)
            details = fetch_problem_details(title_slug)
            if details:
                diff = details.get("difficulty", "Unknown")
                if diff == "Easy":
                    easy += 1
                elif diff == "Medium":
                    medium += 1
                elif diff == "Hard":
                    hard += 1
    
    return {
        "unique": len(unique_problems),
        "submissions": total_submissions,
        "easy": easy,
        "medium": medium,
        "hard": hard
    }

def get_weekly_solved_problems(username, week_start, week_end):
    """Get list of NEW problems solved within a date range (for weekly sync)"""
    url = "https://leetcode.com/graphql"
    
    # Get recent AC submissions with larger limit for weekly data
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
            timeout=15
        )
        data = response.json()
        all_submissions = data.get("data", {}).get("recentAcSubmissionList", [])
    except Exception as e:
        print(f"Error fetching weekly submissions for {username}: {e}")
        return []
    
    if not all_submissions:
        return []
    
    ist = pytz.timezone("Asia/Kolkata")
    
    # Track the EARLIEST solve date for each problem to identify truly new problems
    earliest_solve = {}
    
    for s in all_submissions:
        title_slug = s.get("titleSlug", "")
        if not title_slug:
            continue
            
        ts = int(s["timestamp"])
        ist_time = datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.utc).astimezone(ist)
        solve_date = ist_time.date()
        
        if title_slug not in earliest_solve or solve_date < earliest_solve[title_slug]["date"]:
            earliest_solve[title_slug] = {
                "date": solve_date,
                "title": s.get("title", ""),
                "titleSlug": title_slug,
                "timestamp": ts
            }
    
    # Get problems first solved within the week range
    weekly_problems = []
    seen_slugs = set()
    
    for slug, info in earliest_solve.items():
        if info["date"] >= week_start and info["date"] <= week_end:
            if slug not in seen_slugs:
                # Fetch problem details for difficulty
                details = fetch_problem_details(slug)
                weekly_problems.append({
                    "title": info["title"],
                    "titleSlug": slug,
                    "timestamp": info["timestamp"],
                    "questionNo": details.get("questionFrontendId", "?") if details else "?",
                    "difficulty": details.get("difficulty", "Unknown") if details else "Unknown"
                })
                seen_slugs.add(slug)
    
    return weekly_problems


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

def fetch_problem_full_details(title_slug):
    """Fetch full problem details including description"""
    url = "https://leetcode.com/graphql"

    query = """
    query questionData($titleSlug: String!) {
      question(titleSlug: $titleSlug) {
        questionFrontendId
        title
        titleSlug
        difficulty
        content
        likes
        dislikes
        topicTags {
          name
        }
        stats
        hints
        acRate
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
        print(f"Error fetching full problem details for {title_slug}: {e}")
        return None

def fetch_problem_by_number(question_no):
    """Fetch problem details by question number (frontend ID)"""
    url = "https://leetcode.com/graphql"

    # First, we need to get the titleSlug from the question number
    query = """
    query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
      problemsetQuestionList: questionList(
        categorySlug: $categorySlug
        limit: $limit
        skip: $skip
        filters: $filters
      ) {
        questions: data {
          questionFrontendId
          title
          titleSlug
          difficulty
        }
      }
    }
    """

    variables = {
        "categorySlug": "",
        "skip": 0,
        "limit": 1,
        "filters": {"searchKeywords": str(question_no)}
    }

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
        questions = data.get("data", {}).get("problemsetQuestionList", {}).get("questions", [])
        
        # Find exact match for question number
        for q in questions:
            if q.get("questionFrontendId") == str(question_no):
                # Now fetch full details using titleSlug
                return fetch_problem_full_details(q["titleSlug"])
        
        return None
    except Exception as e:
        print(f"Error fetching problem by number {question_no}: {e}")
        return None

def fetch_daily_challenge():
    """Fetch today's daily challenge problem"""
    url = "https://leetcode.com/graphql"

    query = """
    query questionOfToday {
      activeDailyCodingChallengeQuestion {
        date
        link
        question {
          questionFrontendId
          title
          titleSlug
          difficulty
          content
          likes
          dislikes
          topicTags {
            name
          }
          acRate
        }
      }
    }
    """

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json={"query": query},
            timeout=10
        )
        data = response.json()
        daily = data.get("data", {}).get("activeDailyCodingChallengeQuestion")
        if daily and daily.get("question"):
            result = daily["question"]
            result["date"] = daily.get("date")
            result["link"] = daily.get("link")
            return result
        return None
    except Exception as e:
        print(f"Error fetching daily challenge: {e}")
        return None

def strip_html(html_content):
    """Strip HTML tags and convert to plain text for Discord"""
    import re
    if not html_content:
        return ""
    
    # Replace common HTML entities
    text = html_content.replace("&nbsp;", " ")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&amp;", "&")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    
    # Replace <br>, <p>, <li> with newlines
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'</p>', '\n\n', text)
    text = re.sub(r'<li>', '\n• ', text)
    
    # Replace <code> and <pre> with markdown code blocks
    text = re.sub(r'<pre>(.*?)</pre>', r'```\n\1\n```', text, flags=re.DOTALL)
    text = re.sub(r'<code>(.*?)</code>', r'`\1`', text)
    
    # Replace <strong> and <b> with bold
    text = re.sub(r'<(strong|b)>(.*?)</(strong|b)>', r'**\2**', text)
    
    # Replace <em> and <i> with italic
    text = re.sub(r'<(em|i)>(.*?)</(em|i)>', r'*\2*', text)
    
    # Remove all other HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Clean up multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()
