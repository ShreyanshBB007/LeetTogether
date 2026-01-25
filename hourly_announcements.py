import os
import json

# Try to import database module
try:
    from database import get_announcements_collection
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False

ANNOUNCEMENTS_PATH = "hourly_announcements.json"

def load_announcements():
    """Load announcements from MongoDB or JSON"""
    if MONGO_AVAILABLE:
        collection = get_announcements_collection()
        if collection is not None:
            announcements = {}
            for doc in collection.find():
                discord_id = doc.get("discord_id")
                if discord_id:
                    doc.pop("_id", None)
                    doc.pop("discord_id", None)
                    announcements[discord_id] = doc.get("solves", [])
            return announcements
    
    # Fallback to JSON
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
    """Save announcements to MongoDB and JSON"""
    if MONGO_AVAILABLE:
        collection = get_announcements_collection()
        if collection is not None:
            collection.delete_many({})
            if data:
                docs = [{"discord_id": k, "solves": v} for k, v in data.items()]
                collection.insert_many(docs)
    
    # Always save to JSON as backup
    with open(ANNOUNCEMENTS_PATH, "w") as f:
        json.dump(data, f, indent=4)