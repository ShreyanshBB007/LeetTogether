import json
import os

FILE_PATH = "users.json"
STREAK_PATH = "streak.json"
CONFIG_PATH = "config.json"

def load_users():
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
    
def load_streak():
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

def load_config():
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
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=4)
    
def save_streak(data):
    with open(STREAK_PATH, "w") as f:
        json.dump(data, f, indent=4)


def save_users(data):
    with open(FILE_PATH, "w") as f:
        json.dump(data, f, indent=4)

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
