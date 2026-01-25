"""
Storage module - Uses MongoDB if available, falls back to JSON files
"""
import json
import os
from datetime import datetime

# Try to import database module
try:
    from database import (
        get_users_collection,
        get_streaks_collection,
        get_config_collection,
        get_weekly_collection
    )
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False

FILE_PATH = "users.json"
STREAK_PATH = "streak.json"
CONFIG_PATH = "config.json"
WEEKLY_PATH = "weekly.json"

# ============== USERS ==============

def load_users():
    """Load users from MongoDB or JSON"""
    if MONGO_AVAILABLE:
        collection = get_users_collection()
        if collection is not None:
            users = {}
            for doc in collection.find():
                users[doc["discord_id"]] = doc["leetcode_username"]
            return users
    
    # Fallback to JSON
    if not os.path.exists(FILE_PATH):
        return {}
    try:
        with open(FILE_PATH, "r") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, Exception):
        return {}

def save_users(data):
    """Save users to MongoDB and JSON"""
    if MONGO_AVAILABLE:
        collection = get_users_collection()
        if collection is not None:
            # Clear and re-insert all
            collection.delete_many({})
            if data:
                docs = [{"discord_id": k, "leetcode_username": v} for k, v in data.items()]
                collection.insert_many(docs)
    
    # Always save to JSON as backup
    with open(FILE_PATH, "w") as f:
        json.dump(data, f, indent=4)

# ============== STREAKS ==============

def load_streak():
    """Load streaks from MongoDB or JSON"""
    if MONGO_AVAILABLE:
        collection = get_streaks_collection()
        if collection is not None:
            streaks = {}
            for doc in collection.find():
                discord_id = doc.pop("discord_id")
                doc.pop("_id", None)
                streaks[discord_id] = doc
            return streaks
    
    # Fallback to JSON
    if not os.path.exists(STREAK_PATH):
        return {}
    try:
        with open(STREAK_PATH, "r") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, Exception):
        return {}

def save_streak(data):
    """Save streaks to MongoDB and JSON"""
    if MONGO_AVAILABLE:
        collection = get_streaks_collection()
        if collection is not None:
            collection.delete_many({})
            if data:
                docs = []
                for discord_id, streak_data in data.items():
                    doc = {"discord_id": discord_id, **streak_data}
                    docs.append(doc)
                collection.insert_many(docs)
    
    # Always save to JSON as backup
    with open(STREAK_PATH, "w") as f:
        json.dump(data, f, indent=4)

# ============== CONFIG ==============

def load_config():
    """Load config from MongoDB or JSON"""
    if MONGO_AVAILABLE:
        collection = get_config_collection()
        if collection is not None:
            doc = collection.find_one({"_id": "bot_config"})
            if doc:
                doc.pop("_id", None)
                return doc
            return {}
    
    # Fallback to JSON
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, Exception):
        return {}

def save_config(data):
    """Save config to MongoDB and JSON"""
    if MONGO_AVAILABLE:
        collection = get_config_collection()
        if collection is not None:
            collection.replace_one(
                {"_id": "bot_config"},
                {"_id": "bot_config", **data},
                upsert=True
            )
    
    # Always save to JSON as backup
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=4)

# ============== WEEKLY ==============

def load_weekly():
    """Load weekly leaderboard from MongoDB or JSON"""
    default = {"week_start": None, "data": {}}
    
    if MONGO_AVAILABLE:
        collection = get_weekly_collection()
        if collection is not None:
            doc = collection.find_one({"_id": "weekly_data"})
            if doc:
                doc.pop("_id", None)
                return doc
            return default
    
    # Fallback to JSON
    if not os.path.exists(WEEKLY_PATH):
        return default
    try:
        with open(WEEKLY_PATH, "r") as f:
            content = f.read().strip()
            if not content:
                return default
            return json.loads(content)
    except (json.JSONDecodeError, Exception):
        return default

def save_weekly(data):
    """Save weekly leaderboard to MongoDB and JSON"""
    if MONGO_AVAILABLE:
        collection = get_weekly_collection()
        if collection is not None:
            collection.replace_one(
                {"_id": "weekly_data"},
                {"_id": "weekly_data", **data},
                upsert=True
            )
    
    # Always save to JSON as backup
    with open(WEEKLY_PATH, "w") as f:
        json.dump(data, f, indent=4)

def reset_weekly():
    """Reset weekly leaderboard data"""
    data = {
        "week_start": datetime.now().strftime("%Y-%m-%d"),
        "data": {}
    }
    save_weekly(data)
    return data

def update_weekly_solve(discord_id, problem_title, title_slug, difficulty, question_no):
    """Add a problem to user's weekly solve count"""
    weekly = load_weekly()
    discord_id = str(discord_id)
    
    if discord_id not in weekly["data"]:
        weekly["data"][discord_id] = {
            "unique_problems": 0,
            "submissions": 0,
            "problems": [],
            "easy": 0,
            "medium": 0,
            "hard": 0
        }
    
    # Always increment submissions count
    weekly["data"][discord_id]["submissions"] = weekly["data"][discord_id].get("submissions", 0) + 1
    
    # Check if problem already counted this week (unique problems)
    existing_slugs = [p.get("titleSlug") for p in weekly["data"][discord_id]["problems"]]
    if title_slug not in existing_slugs:
        weekly["data"][discord_id]["unique_problems"] = weekly["data"][discord_id].get("unique_problems", 0) + 1
        # Keep backward compatibility with old 'count' field
        weekly["data"][discord_id]["count"] = weekly["data"][discord_id]["unique_problems"]
        weekly["data"][discord_id]["problems"].append({
            "title": problem_title,
            "titleSlug": title_slug,
            "questionNo": question_no,
            "difficulty": difficulty
        })
        
        # Update difficulty counts
        diff_lower = difficulty.lower()
        if diff_lower in ["easy", "medium", "hard"]:
            weekly["data"][discord_id][diff_lower] += 1
    
    save_weekly(weekly)
    return weekly

# ============== HELPERS ==============

def get_default_streak_data():
    """Return default streak data structure"""
    return {
        "streak": 0,
        "longest_streak": 0,
        "last_checked_date": None,
        "total_days_solved": 0
    }

def update_longest_streak(streak_registry, discord_id):
    """Update longest streak if current streak is higher"""
    if discord_id not in streak_registry:
        return
    
    current = streak_registry[discord_id].get("streak", 0)
    longest = streak_registry[discord_id].get("longest_streak", 0)
    
    if current > longest:
        streak_registry[discord_id]["longest_streak"] = current

def remove_user(user_registry, streak_registry, discord_id):
    """Remove a user from all registries"""
    discord_id = str(discord_id)
    
    if discord_id in user_registry:
        del user_registry[discord_id]
        save_users(user_registry)
    
    if discord_id in streak_registry:
        del streak_registry[discord_id]
        save_streak(streak_registry)
