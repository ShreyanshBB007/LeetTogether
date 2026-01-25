"""
MongoDB database module for persistent storage
"""
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv('MONGODB_URI')

# Initialize MongoDB client
client = None
db = None

def get_db():
    """Get database connection, initialize if needed"""
    global client, db
    
    if db is not None:
        return db
    
    if not MONGODB_URI:
        print("WARNING: MONGODB_URI not set, falling back to JSON files")
        return None
    
    try:
        client = MongoClient(MONGODB_URI)
        db = client.leettogether  # Database name
        # Test connection
        client.admin.command('ping')
        print("✅ Connected to MongoDB!")
        return db
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        return None

def close_db():
    """Close database connection"""
    global client
    if client:
        client.close()

# Collection helpers
def get_users_collection():
    database = get_db()
    if database is not None:
        return database.users
    return None

def get_streaks_collection():
    database = get_db()
    if database is not None:
        return database.streaks
    return None

def get_config_collection():
    database = get_db()
    if database is not None:
        return database.config
    return None

def get_announcements_collection():
    database = get_db()
    if database is not None:
        return database.announcements
    return None

def get_weekly_collection():
    database = get_db()
    if database is not None:
        return database.weekly
    return None
