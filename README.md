# 🚀 LeetTogether — A LeetCode Accountability Discord Bot

LeetTogether is a Discord bot designed to enforce daily LeetCode discipline through automation, transparency, and light social pressure.

The bot tracks LeetCode submissions of registered users, verifies whether they have solved problems daily, maintains streaks, posts periodic updates, and enables competitive accountability via leaderboards and stats.

This project focuses on backend engineering fundamentals such as API integration, scheduling, state persistence, deduplication, and time-based logic — not just Discord commands.

## 🎯 Motivation

In group challenges like "solve at least 1 LeetCode problem per day", proof is often shared via screenshots — which is:

- Manual
- Easy to fake
- Hard to track historically

LeetTogether automates this process by directly querying LeetCode, maintaining verifiable records, and enforcing rules consistently.

## 🧠 High-Level Architecture

```
Discord Commands / Scheduler
        ↓
Business Logic Layer
        ↓
LeetCode GraphQL API
        ↓
State Persistence (MongoDB + JSON backup)
```

### Key Design Principles

- No screenshot-based verification
- Idempotent scheduled jobs (safe to rerun)
- MongoDB-backed persistence (data persists across deployments)
- IST-based time handling (Asia/Kolkata)
- Single responsibility per module

## 🛠️ Core Technologies

- Python
- discord.py
- LeetCode GraphQL API
- APScheduler (for scheduled jobs)
- **MongoDB Atlas** (persistent cloud database)
- JSON (local backup)
- pytz + datetime (timezone correctness)
- requests (HTTP client)
- Flask (keepalive webserver)

## ✅ Implemented Features

### 🔐 User Registration

- Users register their LeetCode username with the bot
- Maps Discord ID → LeetCode username
- Stored persistently in MongoDB
- Used as the foundation for all tracking

### 📡 LeetCode Submission Tracking

- Uses LeetCode's GraphQL API
- Fetches recent submissions for each user
- Filters only Accepted submissions
- Converts timestamps to IST
- **Shows question numbers** (e.g., #1. Two Sum)

### 📅 Daily Solve Verification

- Checks whether a user has solved at least one problem today
- Used by:
  - `!status` command
  - Daily streak update job

### 🔥 Streak Tracking (Daily)

- Runs once daily at 11:59 PM IST
- For each registered user:
  - Increments streak if solved today
  - Resets streak to 0 otherwise
- Prevents double updates using `last_checked_date`
- **Tracks longest streak** (all-time best)
- **Tracks total days solved**
- Fully persistent (MongoDB)

**Example messages:**

```
✅ @User is on a 5🔥 streak!
```

or

```
Oops! @User forgot to solve today. The streak is now 0🔥
```

### 🏆 Leaderboards

#### Daily Leaderboard (`!leaderboard`)
Shows today's rankings sorted by:
1. **Unique problems solved** (primary)
2. **Total submissions** (tiebreaker)

```
🏆 Today's Leaderboard (January 25, 2026)

🥇 @User1 — 5 problems solved (7 submissions) | 🟢2 🟡2 🔴1
🥈 @User2 — 3 problems solved (4 submissions) | 🟢1 🟡2 🔴0
🥉 @User3 — 3 problems solved (3 submissions) | 🟢2 🟡1 🔴0

---
Total today: 11 problems solved (14 submissions) by 3 users
```

#### Weekly Leaderboard (`!weekly`)
Shows this week's rankings (resets Sunday 11:59 PM IST):

```
📅 Weekly Leaderboard
(Week starting: 2026-01-19)

🥇 @User1 — 12 problems solved (18 submissions) | 🟢4 🟡5 🔴3
🥈 @User2 — 8 problems solved (10 submissions) | 🟢3 🟡4 🔴1
🥉 @User3 — 5 problems solved (5 submissions) | 🟢2 🟡2 🔴1

---
Total this week: 25 problems solved (33 submissions) by 3 users
```

#### Streak Leaderboard (`!streakboard`)
Shows all-time streak rankings.

### 📊 Difficulty Tracking

- Fetches Easy/Medium/Hard breakdown from LeetCode
- Shows total problems solved per difficulty
- Color-coded emojis:
  - 🟢 Easy
  - 🟡 Medium
  - 🔴 Hard

### 🔗 Problem Details with Question Numbers

- Shows LeetCode question number before title (e.g., #1. Two Sum)
- Shows problem difficulty
- Clickable links to problem page
- Displayed in announcements, `!today`, `!profile`, `!progress`

**Example announcement:**
```
🔥 @Shreyansh solved 2 problem(s)!
🟢 #1. Two Sum (Easy)
🟡 #15. 3Sum (Medium)
```

### 🔔 Smart Nudges (9 PM IST)

- Sends DM reminders to users who haven't solved today
- Runs daily at 9 PM IST (before midnight deadline)
- Gentle, non-spammy reminders

**Example DM:**
```
⏰ Friendly Reminder!

Hey! You haven't solved any LeetCode problem today yet.
There's still time before midnight! 💪

Keep your streak alive! 🔥
```

### 📈 Weekly Recap (Sundays)

- Auto-posts every Sunday at 10 PM IST
- Shows streak leaderboard with medals (🥇🥈🥉)
- Highlights best performer of the week
- Includes current streak, longest streak, and total days

### ⚡ Near-Instant Submission Announcements

- Checks for new submissions **every 5 minutes**
- Detects new accepted submissions only
- Uses timestamp-based deduplication
- **Only counts NEW problems** (re-submissions don't count)
- Shows question number, title, and difficulty

### 🧠 Deduplication & Reliability

- Every submission is uniquely identified using its timestamp
- **Only counts NEW problems** (re-submissions of previously solved problems don't count)
- Prevents:
  - Double announcements
  - Double streak increments
  - Inflated solve counts from re-solving old problems
- Bot restarts do NOT cause re-announcements

### 💾 Persistent Storage (MongoDB Atlas)

Uses MongoDB Atlas for cloud-persistent storage:

- `users` collection - User registration data
- `streaks` collection - Streak tracking data
- `announcements` collection - Submission tracking
- `config` collection - Bot configuration
- `weekly` collection - Weekly leaderboard data

**JSON backup files** are also maintained locally for redundancy.

This ensures data persists across Render deployments and bot restarts.

## 🧪 Edge Case Handling

- ✔ User registers late at night (e.g., 11:58 PM)
- ✔ User has never solved any problems
- ✔ Multiple submissions of the same problem
- ✔ Bot restarts mid-day
- ✔ Duplicate API responses
- ✔ Render redeployments (data in MongoDB)

**If the LeetCode API is temporarily down during a scheduled job:**

- The job is skipped
- No streaks are modified
- Error is logged

## 🚧 Planned Features

### 🛡️ Grace Period

- Allow 1 missed day per week without losing streak
- Configurable grace rules

---

## 🚀 Getting Started

### 1. Install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Create a `.env` file:
```
DISCORD_TOKEN=your_discord_bot_token
MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net/
```

### 3. Set up MongoDB Atlas (Free Tier):
1. Create account at [mongodb.com/cloud/atlas](https://mongodb.com/cloud/atlas)
2. Create a free M0 cluster
3. Create database user and get connection string
4. Add connection string to `.env` and Render environment variables

### 4. Run the bot:
```bash
python main.py
```

### 5. Deploy to Render:
1. Connect GitHub repo to Render
2. Add environment variables (`DISCORD_TOKEN`, `MONGODB_URI`)
3. Deploy!

---

## 📝 Available Commands

| Command | Description |
|---------|-------------|
| `!register <username>` | Register your LeetCode username |
| `!unregister` | Remove your registration and data |
| `!me` | Check your registered username |
| `!status` | Check if you've solved today |
| `!streak` | View your current streak, longest streak, and total days |
| `!today` | See today's solves with question numbers and difficulty |
| `!profile [@user]` | View detailed profile (yours or another user's) |
| `!progress` | View today's progress for ALL registered users |
| `!users` | List all registered users |
| `!leaderboard` | Today's leaderboard (unique problems + submissions) |
| `!weekly` | Weekly leaderboard (resets Sunday 11:59 PM IST) |
| `!streakboard` | View streak leaderboard |
| `!setchannel #channel` | Set announcement channel (Admin only) |
| `!hello` | Greet the bot |
| `!ping` | Check bot responsiveness |

---

## 📊 Example Outputs

### `!profile`

```
📊 Profile: Shreyansh

LeetCode: shreyansh_bhagwat

🔥 Streak: 5 days (Best: 12)
📅 Total Days Solved: 47

📈 Problems Solved:
🟢 Easy: 25
🟡 Medium: 32
🔴 Hard: 5
📊 Total: 62

🏅 Global Ranking: #225,432

✅ Solved today!

Today's Problems:
🟡 #1. Two Sum at 14:30
🔴 #4. Median of Two Sorted Arrays at 16:45
```

### `!today`

```
✅ Today's Solves (2 problems)

🟡 #1. Two Sum (Medium) at 14:30
🔴 #4. Median of Two Sorted Arrays (Hard) at 16:45
```

### `!progress`

```
📊 Today's Progress (January 25, 2026)

1. @Shreyansh — 3 problem(s)
   🟢 #1. Two Sum (Easy) at 10:30
   🟡 #15. 3Sum (Medium) at 14:15
   🔴 #23. Merge K Lists (Hard) at 18:45

2. @John — 1 problem(s)
   🟡 #20. Valid Parentheses (Medium) at 12:00

3. @Jane — ❌ Not solved yet

---
Total: 4 problem(s) solved by 2/3 users
```

### `!leaderboard`

```
🏆 Today's Leaderboard (January 25, 2026)

🥇 @Shreyansh — 5 problems solved (7 submissions) | 🟢2 🟡2 🔴1
🥈 @John — 3 problems solved (4 submissions) | 🟢1 🟡2 🔴0
🥉 @Jane — 2 problems solved (2 submissions) | 🟢1 🟡1 🔴0

---
Total today: 10 problems solved (13 submissions) by 3 users
```

### `!weekly`

```
📅 Weekly Leaderboard
(Week starting: 2026-01-19)

🥇 @Shreyansh — 15 problems solved (22 submissions) | 🟢5 🟡7 🔴3
🥈 @John — 10 problems solved (12 submissions) | 🟢4 🟡5 🔴1
🥉 @Jane — 6 problems solved (6 submissions) | 🟢3 🟡2 🔴1

---
Total this week: 31 problems solved (40 submissions) by 3 users
```

---

## ⏰ Scheduled Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| Submission Check | Every 5 minutes | Announces new solves (near-instant) |
| Smart Nudges | 9:00 PM IST | DMs users who haven't solved |
| Streak Update | 11:58 PM IST | Updates streaks for all users |
| Daily Check | 11:59 PM IST | Announces who solved/didn't solve |
| Weekly Recap | Sundays 10:00 PM IST | Posts weekly summary |
| Weekly Reset | Sundays 11:59 PM IST | Resets weekly leaderboard |

---

## 🧩 Why This Project Matters

This project demonstrates:

- Real-world API integration (LeetCode GraphQL)
- Timezone-safe scheduling (IST)
- Stateful backend logic
- Idempotent job design
- Cloud database integration (MongoDB Atlas)
- Clean separation of concerns

It is not a "Discord bot tutorial project" — it is a backend system with Discord as the interface.

---

## 📌 Tech Stack

| Layer | Technology |
|-------|------------|
| Bot Framework | discord.py |
| API | LeetCode GraphQL |
| Database | MongoDB Atlas |
| Scheduler | APScheduler |
| Hosting | Render |
| Language | Python 3.10+ |

---

