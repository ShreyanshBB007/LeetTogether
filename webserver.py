from flask import Flask, jsonify
from threading import Thread
import json
import os

app = Flask('')

@app.route('/')
def home():
    return "its a fooking discord bot ok"

@app.route('/data-backup')
def data_backup():
    """Temporary endpoint to recover data - REMOVE AFTER USE"""
    data = {}
    
    for filename in ['users.json', 'streak.json', 'hourly_annoucements.json', 'config.json', 'weekly.json']:
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    content = f.read().strip()
                    data[filename] = json.loads(content) if content else {}
            except:
                data[filename] = "error reading"
        else:
            data[filename] = "file not found"
    
    return jsonify(data)

def run():
    app.run(host="0.0.0.0", port = 8080)

def keep_alive():
    t = Thread(target=run)
    t.start()