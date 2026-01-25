# 🚀 LeetTogether — A LeetCode Accountability Discord Bot

LeetTogether is a Discord bot designed to enforce daily LeetCode discipline through automation, transparency, and light social pressure.

The bot tracks LeetCode submissions of registered users, verifies whether they have solved problems daily, maintains streaks, posts periodic updates, and enables competitive accountability via leaderboards and stats.

This project focuses on backend engineering fundamentals such as API integration, scheduling, state persistence, deduplication, and time-based logic — not just Discord commands.

## 🎯 Motivation

In group challenges like “solve at least 1 LeetCode problem per day”, proof is often shared via screenshots — which is:

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
State Persistence (JSON)
```

### Key Design Principles

- No screenshot-based verification
- Idempotent scheduled jobs (safe to rerun)
- Disk-backed persistence (bot restarts don't lose data)
- IST-based time handling (Asia/Kolkata)
- Single responsibility per module

## 🛠️ Core Technologies

- Python
- discord.py
- LeetCode GraphQL API
- APScheduler (for hourly & daily jobs)
- JSON-based persistence
- pytz + datetime (timezone correctness)
- requests (HTTP client)

## ✅ Implemented Features

### 🔐 User Registration

- Users register their LeetCode username with the bot
- Maps Discord ID → LeetCode username
- Stored persistently
- Used as the foundation for all tracking

### 📡 LeetCode Submission Tracking

- Uses LeetCode's GraphQL API
- Fetches recent submissions for each user
- Filters only Accepted submissions
- Converts timestamps to IST

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
- Fully persistent (`streak.json`)

**Example messages:**

```
✅ @User is on a 5🔥 streak!
```

or

```
Oops! @User forgot to solve today. The streak is now 0🔥
```

### 🏆 Longest Streak Tracking

- Automatically tracks your all-time best streak
- Never loses your record even if current streak resets
- Displayed in `!streak` and `!profile` commands

### 📊 Difficulty Tracking

- Fetches Easy/Medium/Hard breakdown from LeetCode
- Shows total problems solved per difficulty
- Displayed in `!profile` command with color-coded emojis:
  - 🟢 Easy
  - 🟡 Medium
  - 🔴 Hard

### 🔗 Problem Details

- Shows problem difficulty and clickable links
- Links directly to LeetCode problem page
- Displayed in `!today` and `!profile` commands

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
- Announces as soon as someone solves a problem

**Example:**

```
🔥 @Shreyansh solved 3 problem(s)!
- Two Sum
- Binary Search
- Valid Parentheses
```

### 🧠 Deduplication & Reliability

- Every submission is uniquely identified using its timestamp
- **Only counts NEW problems** (re-submissions of previously solved problems don't count)
- Prevents:
  - Double announcements
  - Double streak increments
  - Inflated solve counts from re-solving old problems
- Bot restarts do NOT cause re-announcements

### 💾 Persistent Storage

Currently uses JSON-based storage:

- `users.json` - User registration data
- `streak.json` - Streak tracking data
- `hourly_announcements.json` - Submission tracking
- `config.json` - Bot configuration (announcement channel, etc.)

This keeps the system simple while remaining restart-safe.

## 🧪 Edge Case Handling

- ✔ User registers late at night (e.g., 11:58 PM)
- ✔ User has never solved any problems
- ✔ Multiple submissions of the same problem
- ✔ Bot restarts mid-day
- ✔ Duplicate API responses

**If the LeetCode API is temporarily down during a scheduled job:**

- The job is skipped
- No streaks are modified
- Error is logged

## 🚧 Planned Features (Yet to Be Implemented)

### �️ Database Migration (SQLite)

Planned migration from JSON → SQLite for:

- Scalability
- Query efficiency
- Cleaner schema enforcement

*(This will be done only when JSON becomes limiting.)*

### 🛡️ Grace Period

- Allow 1 missed day per week without losing streak
- Configurable grace rules

## 🧩 Why This Project Matters

This project demonstrates:

- Real-world API integration
- Timezone-safe scheduling
- Stateful backend logic
- Idempotent job design
- Clean separation of concerns

It is not a “Discord bot tutorial project” — it is a backend system with Discord as the interface.

## 📌 Future Vision

LeetTogether aims to become:

- A plug-and-play accountability system
- A reusable backend template for habit tracking
- A solid portfolio project demonstrating backend maturity

---

## 🚀 Getting Started

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file with your Discord bot token:
   ```
   DISCORD_TOKEN=your_token_here
   ```

3. Run the bot:
   ```bash
   python main.py
   ```

## 📝 Available Commands

| Command | Description |
|---------|-------------|
| `!register <username>` | Register your LeetCode username |
| `!unregister` | Remove your registration and data |
| `!me` | Check your registered username |
| `!status` | Check if you've solved today |
| `!streak` | View your current streak, longest streak, and total days |
| `!today` | See today's solves with difficulty and links |
| `!profile [@user]` | View detailed profile (yours or another user's) |
| `!progress` | View today's progress for ALL registered users |
| `!users` | List all registered users |
| `!leaderboard` | View today's solve count leaderboard |
| `!streakboard` | View streak leaderboard |
| `!setchannel #channel` | Set announcement channel (Admin only) |
| `!hello` | Greet the bot |
| `!ping` | Check bot responsiveness |

### Example: `!profile`

```
📊 Profile: Shreyansh

LeetCode: shreyansh_bhagwat

🔥 Streak: 5 days (Best: 12)
📅 Total Days Solved: 47

📈 Problems Solved:
🟢 Easy: 85
🟡 Medium: 62
🔴 Hard: 15
📊 Total: 162

🏅 Global Ranking: #125,432

✅ Solved today!

Today's Problems:
🟡 Two Sum at 14:30
🔴 Median of Two Sorted Arrays at 16:45
```

### Example: `!today`

```
✅ Today's Solves (2 problems)

🟡 Medium — Two Sum at 14:30
🔴 Hard — Median of Two Sorted Arrays at 16:45
```

### Example: `!progress`

```
📊 Today's Progress (January 25, 2026)

1. @Shreyansh — 3 problem(s)
   🟢 Two Sum (Easy) at 10:30
   🟡 3Sum (Medium) at 14:15
   🔴 Merge K Lists (Hard) at 18:45

2. @John — 1 problem(s)
   🟡 Valid Parentheses (Medium) at 12:00

3. @Jane — ❌ Not solved yet

---
Total: 4 problem(s) solved by 2/3 users
```

## ⏰ Scheduled Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| Daily Check | 11:59 PM IST | Announces who solved/didn't solve |
| Streak Update | 11:58 PM IST | Updates streaks for all users |
| Submission Check | Every 5 minutes | Announces new solves (near-instant) |
| Smart Nudges | 9:00 PM IST | DMs users who haven't solved |
| Weekly Recap | Sundays 10 PM IST | Posts weekly leaderboard |