import os
import json

ANNOUNCEMENTS_PATH = "hourly_announcements.json"

def load_announcements():
    if not os.path.exists(ANNOUNCEMENTS_PATH):
        return {}
    try:
        with open(ANNOUNCEMENTS_PATH, "r") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, Exception):
        return {}

def save_announcements(data):
    with open(ANNOUNCEMENTS_PATH, "w") as f:
        json.dump(data, f, indent=4)