import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import asyncio
from leetcode_logic import (
    has_user_solved_today, 
    get_today_accepted_count, 
    fetch_recent_submissions, 
    get_today_solved_problems,
    get_today_solved_with_difficulty,
    get_difficulty_breakdown,
    get_user_ranking,
    fetch_problem_details,
    get_today_stats,
    fetch_problem_by_number,
    fetch_daily_challenge,
    strip_html,
    get_weekly_solved_problems
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import pytz
from storage import (
    load_users, 
    save_users, 
    load_streak, 
    save_streak,
    get_default_streak_data,
    update_longest_streak,
    remove_user,
    load_config,
    save_config,
    load_weekly,
    save_weekly,
    reset_weekly,
    update_weekly_solve
)
from hourly_announcements import load_announcements, save_announcements
import webserver

user_registry = load_users()
streak_registry = load_streak()
bot_config = load_config()

# Default channel ID (will be overridden by !setchannel)
DEFAULT_CHANNEL_ID = 1461411340580032565

def get_announcement_channel_id():
    """Get the configured announcement channel ID"""
    return bot_config.get("announcement_channel_id", DEFAULT_CHANNEL_ID)

load_dotenv()
token = os.getenv('DISCORD_TOKEN')
secret_role = "Leeter"

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!',intents = intents)
scheduler = AsyncIOScheduler()

ist = pytz.timezone("Asia/Kolkata")
MESSAGE_CHUNK_LIMIT = 1800
MIN_SEND_INTERVAL = 1.0
MAX_SEND_RETRIES = 5
_rate_limit_state = {"lock": None, "next_allowed": 0.0}


async def safe_send(send_callable, *args, **kwargs):
    """Serialize Discord sends with retries so we respect global rate limits."""
    loop = asyncio.get_running_loop()
    if _rate_limit_state["lock"] is None:
        _rate_limit_state["lock"] = asyncio.Lock()
    lock = _rate_limit_state["lock"]

    for attempt in range(1, MAX_SEND_RETRIES + 1):
        async with lock:
            wait_time = max(0.0, _rate_limit_state["next_allowed"] - loop.time())
        if wait_time > 0:
            await asyncio.sleep(wait_time)

        try:
            result = await send_callable(*args, **kwargs)
            async with lock:
                _rate_limit_state["next_allowed"] = loop.time() + MIN_SEND_INTERVAL
            return result
        except discord.errors.HTTPException as e:
            if e.status != 429:
                raise
            retry_after = getattr(e, "retry_after", MIN_SEND_INTERVAL * attempt)
            print(f"Rate limited by Discord (attempt {attempt}/{MAX_SEND_RETRIES}), waiting {retry_after:.2f}s")
            async with lock:
                _rate_limit_state["next_allowed"] = loop.time() + retry_after
            await asyncio.sleep(retry_after + 0.5)
        except Exception as e:
            if attempt == MAX_SEND_RETRIES:
                raise e
            await asyncio.sleep(MIN_SEND_INTERVAL * attempt)

    raise RuntimeError("safe_send exhausted retries")


def chunk_messages(messages, limit=MESSAGE_CHUNK_LIMIT):
    """Group multiple announcement strings into Discord-safe chunks."""
    chunk = ""
    for message in messages:
        entry = message.strip()
        if not entry:
            continue
        addition = entry + "\n\n"
        if len(chunk) + len(addition) > limit and chunk:
            yield chunk.strip()
            chunk = addition
        else:
            chunk += addition

    if chunk.strip():
        yield chunk.strip()


async def daily_check():
    channel = bot.get_channel(get_announcement_channel_id())

    if channel is None:
        print("Channel not found")
        return

    await safe_send(channel.send, "📊 **Daily LeetCode Status Check**")

    for discord_id, leetcode_username in user_registry.items():
        solved = has_user_solved_today(leetcode_username)

        mention = f"<@{discord_id}>"
        if solved:
            await safe_send(channel.send, f"✅ {mention} is safe today!")
        else:
            await safe_send(channel.send, f"❌ {mention} did NOT solve today!")


async def streak_update():
    channel = bot.get_channel(get_announcement_channel_id())

    if channel is None:
        print("Channel not found")
        return
    for discord_id, data in user_registry.items():
        if not discord_id in streak_registry:
            streak_registry[discord_id] = get_default_streak_data()
        
        # Ensure all fields exist for older entries
        if "longest_streak" not in streak_registry[discord_id]:
            streak_registry[discord_id]["longest_streak"] = streak_registry[discord_id].get("streak", 0)
        if "total_days_solved" not in streak_registry[discord_id]:
            streak_registry[discord_id]["total_days_solved"] = 0
            
        leetcode_username = user_registry[discord_id]
        today = datetime.now(pytz.timezone("Asia/Kolkata")).date().isoformat()
        if already_checked_today(discord_id):
            continue
        else:
            if has_user_solved_today(leetcode_username):
                streak_registry[discord_id]["streak"] = streak_registry[discord_id]["streak"] + 1
                streak_registry[discord_id]["total_days_solved"] = streak_registry[discord_id].get("total_days_solved", 0) + 1
                streak = streak_registry[discord_id]["streak"]
                streak_registry[discord_id]["last_checked_date"] = today
                # Update longest streak
                update_longest_streak(streak_registry, discord_id)
                mention = f"<@{discord_id}>"
                await safe_send(channel.send, f"✅ {mention} is on {streak}🔥 streak!")
            else:
                streak_registry[discord_id]["streak"] = 0
                streak_registry[discord_id]["last_checked_date"] = today
                streak = streak_registry[discord_id]["streak"]
                mention = f"<@{discord_id}>"
                await safe_send(channel.send, f"Oops! {mention} forgot to solve today. The streak is now {streak}🔥")
    save_streak(streak_registry)




def already_checked_today(discord_id):
    if not discord_id in streak_registry:
        return False
    
    last_checked_date = streak_registry[discord_id]["last_checked_date"]
    today = datetime.now(pytz.timezone("Asia/Kolkata")).date().isoformat()
    if last_checked_date is None:
        return False
    
    return last_checked_date == today

def sync_user_submissions(discord_id, leetcode_username):
    from leetcode_logic import get_problems_solved_before_today
    
    data = load_announcements()

    if str(discord_id) not in data:
        data[str(discord_id)] = []

    existing_timestamps = {
        entry["timestamp"] for entry in data[str(discord_id)]
    }

    # Get problems that were solved before today (to identify re-solves)
    previously_solved = get_problems_solved_before_today(leetcode_username)

    submissions = fetch_recent_submissions(leetcode_username)

    for sub in submissions:
        if sub["statusDisplay"] != "Accepted":
            continue

        ts = int(sub["timestamp"])
        title_slug = sub.get("titleSlug", "")

        if ts in existing_timestamps:
            continue
        
        # Mark if this is a re-solve (problem was already solved before today)
        is_resubmit = title_slug in previously_solved

        data[str(discord_id)].append({
            "title": sub["title"],
            "titleSlug": title_slug,
            "timestamp": ts,
            "announced": False,
            "is_resubmit": is_resubmit
        })

    save_announcements(data)

async def submission_check_job():
    """Check for new submissions every 5 minutes and announce them"""
    channel = bot.get_channel(get_announcement_channel_id())
    if channel is None:
        print("Announcement channel not found")
        return
    
    # First sync all user submissions from LeetCode API
    for discord_id, leetcode_username in user_registry.items():
        sync_user_submissions(discord_id, leetcode_username)
        await asyncio.sleep(0.5)  # Small delay between API calls

    data = load_announcements()
    announcement_messages = []

    for discord_id, solves in data.items():
        new_solves = [
            s for s in solves if not s.get("announced", False)
        ]

        # Only process if there are new solves
        if not new_solves:
            continue

        mention = f"<@{discord_id}>"
        
        # Separate new problems from re-solves
        new_problems = [s for s in new_solves if not s.get("is_resubmit", False)]
        resubmits = [s for s in new_solves if s.get("is_resubmit", False)]
        
        # Track re-solves as submissions only (not new problems)
        for s in resubmits:
            title_slug = s.get("titleSlug", "")
            details = fetch_problem_details(title_slug) if title_slug else None
            if details:
                diff = details.get("difficulty", "Unknown")
                q_no = details.get("questionFrontendId", "?")
                # Track as submission only, not as new problem
                update_weekly_solve(discord_id, s['title'], title_slug, diff, q_no, is_new_problem=False)
            s["announced"] = True
        
        # Only announce truly new problems
        if not new_problems:
            continue
        
        # Fetch problem details for each new solve
        lines = []
        for s in new_problems:
            title_slug = s.get("titleSlug", "")
            details = fetch_problem_details(title_slug) if title_slug else None
            
            if details:
                q_no = details.get("questionFrontendId", "?")
                diff = details.get("difficulty", "Unknown")
                diff_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}.get(diff, "⚪")
                lines.append(f"{diff_emoji} #{q_no}. {s['title']} ({diff})")
                
                # Track weekly solve as new problem
                update_weekly_solve(discord_id, s['title'], title_slug, diff, q_no, is_new_problem=True)
            else:
                lines.append(f"- {s['title']}")

        announcement_messages.append(
            f"🔥 {mention} solved {len(new_problems)} problem(s)!\n" + "\n".join(lines)
        )

        for s in new_problems:
            s["announced"] = True

    save_announcements(data)

    for chunk in chunk_messages(announcement_messages):
        try:
            await safe_send(channel.send, chunk)
        except Exception as e:
            print(f"Failed to send announcement chunk: {e}")
            break


async def smart_nudge_job():
    """Send DM to users who haven't solved by 9 PM IST"""
    for discord_id, leetcode_username in user_registry.items():
        # Retry logic for API reliability
        solved = has_user_solved_today(leetcode_username)
        if not solved:
            # Wait and retry once more to handle temporary API issues
            await asyncio.sleep(2)
            solved = has_user_solved_today(leetcode_username)
        
        if not solved:
            try:
                user = await bot.fetch_user(int(discord_id))
                if user:
                    await safe_send(
                        user.send,
                        f"⏰ **Friendly Reminder!**\n\n"
                        f"Hey! You haven't solved any LeetCode problem today yet.\n"
                        f"There's still time before midnight! 💪\n\n"
                        f"Keep your streak alive! 🔥"
                    )
            except discord.errors.HTTPException as e:
                if e.status == 429:  # Rate limited
                    retry_after = getattr(e, 'retry_after', 5)
                    print(f"Rate limited on nudge, waiting {retry_after} seconds...")
                    await asyncio.sleep(retry_after + 1)
                else:
                    print(f"Could not send nudge to {discord_id}: {e}")
            except Exception as e:
                print(f"Could not send nudge to {discord_id}: {e}")


def get_current_week_start():
    """Get the Monday that starts the current week (IST timezone)"""
    days_since_monday = today.weekday()
    current_week_start = today - timedelta(days=days_since_monday)
    return current_week_start


def ensure_weekly_synced():
    """Catch up any missed submissions for the current week by checking LeetCode API directly"""
    weekly = load_weekly()
    week_start_str = weekly.get("week_start")
    
    ist = pytz.timezone("Asia/Kolkata")
    today = datetime.now(ist).date()
    current_week_start = get_current_week_start()
    
    # Check if we need to reset (stored week_start is from a previous week)
    if week_start_str:
        try:
            stored_week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
            if stored_week_start < current_week_start:
                # Week has changed, reset the data
                print(f"New week detected! Resetting weekly data. Old: {stored_week_start}, New: {current_week_start}")
                weekly = reset_weekly()
                week_start_str = weekly.get("week_start")
        except:
            pass
    
    if not week_start_str:
        # Initialize with current week start
        weekly["week_start"] = current_week_start.strftime("%Y-%m-%d")
        save_weekly(weekly)
        week_start_str = weekly["week_start"]
    
    try:
        week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
    except:
        return weekly
    
    for discord_id, leetcode_username in user_registry.items():
        # Get this week's solved problems directly from LeetCode
        problems_this_week = get_weekly_solved_problems(leetcode_username, week_start, today)
        
        if not problems_this_week:
            continue
        
        # Initialize user in weekly if not exists
        if str(discord_id) not in weekly["data"]:
            weekly["data"][str(discord_id)] = {
                "unique_problems": 0,
                "submissions": 0,
                "problems": [],
                "easy": 0,
                "medium": 0,
                "hard": 0
            }
        
        user_data = weekly["data"][str(discord_id)]
        existing_slugs = {p.get("titleSlug") for p in user_data.get("problems", [])}
        
        # Add any missing problems
        for p in problems_this_week:
            if p["titleSlug"] not in existing_slugs:
                user_data["unique_problems"] = user_data.get("unique_problems", 0) + 1
                user_data["count"] = user_data["unique_problems"]  # backward compat
                user_data["submissions"] = user_data.get("submissions", 0) + 1
                user_data["problems"].append({
                    "title": p["title"],
                    "titleSlug": p["titleSlug"],
                    "questionNo": p.get("questionNo", "?"),
                    "difficulty": p.get("difficulty", "Unknown")
                })
                
                # Update difficulty counts
                diff_lower = p.get("difficulty", "").lower()
                if diff_lower in ["easy", "medium", "hard"]:
                    user_data[diff_lower] = user_data.get(diff_lower, 0) + 1
    
    save_weekly(weekly)
    return weekly


async def weekly_reset_job():
    """Reset weekly leaderboard on Sunday 11:59 PM"""
    channel = bot.get_channel(get_announcement_channel_id())
    if channel:
        weekly = load_weekly()
        if weekly["data"]:
            await safe_send(channel.send, "🔄 Weekly leaderboard has been reset! Good luck this week! 💪")
    reset_weekly()
    print("Weekly leaderboard reset")


async def weekly_recap_job():
    """Post weekly recap on Sundays"""
    channel = bot.get_channel(get_announcement_channel_id())
    if channel is None:
        return
    
    # Build leaderboard by streak
    streak_leaders = []
    for discord_id in user_registry.keys():
        if discord_id in streak_registry:
            streak = streak_registry[discord_id].get("streak", 0)
            longest = streak_registry[discord_id].get("longest_streak", 0)
            total_days = streak_registry[discord_id].get("total_days_solved", 0)
            streak_leaders.append((discord_id, streak, longest, total_days))
    
    streak_leaders.sort(key=lambda x: (x[1], x[2]), reverse=True)
    
    msg = "📊 **Weekly Recap**\n\n"
    msg += "🏆 **Streak Leaderboard:**\n"
    
    medals = ["🥇", "🥈", "🥉"]
    for i, (discord_id, streak, longest, total_days) in enumerate(streak_leaders[:10]):
        medal = medals[i] if i < 3 else f"{i+1}."
        msg += f"{medal} <@{discord_id}> — **{streak}**🔥 current | **{longest}**🔥 best | **{total_days}** days total\n"
    
    if streak_leaders:
        best_id = streak_leaders[0][0]
        msg += f"\n🌟 **Best Performer:** <@{best_id}> with a **{streak_leaders[0][1]}** day streak!\n"
    
    msg += "\nKeep grinding! 💪"
    
    await safe_send(channel.send, msg)


def scheduled_job():
    asyncio.create_task(daily_check())



scheduler.add_job(
    daily_check,
    "cron",
    hour=23,
    minute=59,
    timezone=ist
)
scheduler.add_job(
    streak_update,
    "cron",
    hour=23,
    minute=58,
    timezone=ist
)
# Check for new submissions every 5 minutes
scheduler.add_job(
    submission_check_job,
    trigger="interval",
    minutes=5
)
# Smart nudge at 9 PM IST
scheduler.add_job(
    smart_nudge_job,
    "cron",
    hour=21,
    minute=0,
    timezone=ist
)
# Weekly recap on Sundays at 10 PM IST
scheduler.add_job(
    weekly_recap_job,
    "cron",
    day_of_week="sun",
    hour=22,
    minute=0,
    timezone=ist
)
# Reset weekly leaderboard on Sundays at 11:59 PM IST
scheduler.add_job(
    weekly_reset_job,
    "cron",
    day_of_week="sun",
    hour=23,
    minute=59,
    timezone=ist
)


@bot.event
async def on_ready():
    print("Bot is online!")

    if not scheduler.running:
        scheduler.start()


@bot.event
async def on_member_join(member):
    await safe_send(member.send, f"Welcome to the server {member.name}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if "shit" in message.content.lower():
        await message.delete()
        await safe_send(message.channel.send, f"{message.author.mention}- Hey, dont use that word! ")
    
    await bot.process_commands(message)

@bot.command()
async def hello(ctx):
    await ctx.send(f"Hello {ctx.author.mention}!")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

@bot.command()
async def assign(ctx, role_name: str):
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if role:
        await ctx.author.add_roles(role)
        await ctx.send(f"Role '{role_name}' has been assigned to you, {ctx.author.mention}!")
    else:
        await ctx.send(f"Role '{role_name}' not found.")

@bot.command()
async def remove(ctx, role_name: str):
    role = discord.utils.get(ctx.guild.roles, name=role_name)   
    if role:
        await ctx.author.remove_roles(role)
        await ctx.send(f"Role '{role_name}' has been removed from you, {ctx.author.mention}!")
    else:
        await ctx.send(f"Role '{role_name}' not found.")

@bot.command()
@commands.has_role("secret_role")
async def secret(ctx):
    await ctx.send("Welcome to the club!")

@secret.error
async def secret_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send("You do not have permission to do that!")

@bot.command()
async def dm(ctx, member: discord.Member, *, content: str):
    try:
        await member.send(content)
        await ctx.send(f"Message sent to {member.mention}.")
    except Exception as e:
        await ctx.send(f"Failed to send message: {e}")
        
@bot.command()
async def register(ctx, leetcode_username):
    user_registry[str(ctx.author.id)] = leetcode_username
    save_users(user_registry)
    await ctx.send(f"✅ Registered **{leetcode_username}**")

@bot.command()
async def me(ctx):
    user_id = str(ctx.author.id)

    if user_id not in user_registry:
        await ctx.send("You are not registered yet.")
        return

    await ctx.send(
        f"Your LeetCode username is **{user_registry[user_id]}**!"
    )

@bot.command()
async def status(ctx):
    user_id = str(ctx.author.id)

    if user_id not in user_registry:
        await ctx.send("You are not registered yet.")
        return

    if has_user_solved_today(user_registry[user_id]):
        await ctx.send("You are safe today!")
    else:
        await ctx.send("You haven't solved today!")

@bot.command()
async def leaderboard(ctx):
    """Show today's leaderboard with unique problems and submissions"""
    results = []

    for discord_id, lc_username in user_registry.items():
        stats = get_today_stats(lc_username)
        results.append((
            discord_id,
            stats["unique"],
            stats["submissions"],
            stats["easy"],
            stats["medium"],
            stats["hard"]
        ))

    # Sort by unique problems first, then submissions as tiebreaker
    results.sort(key=lambda x: (x[1], x[2]), reverse=True)

    if not results:
        await ctx.send("No registered users.")
        return  

    ist = pytz.timezone("Asia/Kolkata")
    today_str = datetime.now(ist).strftime("%B %d, %Y")
    
    msg = f"🏆 **Today's Leaderboard** ({today_str})\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    
    for i, (discord_id, unique, submissions, easy, medium, hard) in enumerate(results[:10]):
        medal = medals[i] if i < 3 else f"{i+1}."
        breakdown = f"🟢{easy} 🟡{medium} 🔴{hard}"
        msg += f"{medal} <@{discord_id}> — **{unique}** problems solved ({submissions} submissions) | {breakdown}\n"

    total_unique = sum(r[1] for r in results)
    total_subs = sum(r[2] for r in results)
    msg += f"\n---\n**Total today:** {total_unique} problems solved ({total_subs} submissions) by {len(results)} users"

    await ctx.send(msg)

@bot.command()
async def streak(ctx):
    """Show your current streak"""
    user_id = str(ctx.author.id)

    if user_id not in user_registry:
        await ctx.send("❌ You are not registered yet. Use `!register <leetcode_username>`")
        return

    if user_id not in streak_registry:
        await ctx.send("🔥 Your current streak: **0** days")
        return

    current = streak_registry[user_id].get("streak", 0)
    longest = streak_registry[user_id].get("longest_streak", 0)
    total = streak_registry[user_id].get("total_days_solved", 0)

    msg = f"🔥 **Your Streak Stats**\n\n"
    msg += f"Current Streak: **{current}** days 🔥\n"
    msg += f"Longest Streak: **{longest}** days 🏆\n"
    msg += f"Total Days Solved: **{total}** days 📅"

    await ctx.send(msg)

@bot.command()
async def unregister(ctx):
    """Remove your registration"""
    user_id = str(ctx.author.id)

    if user_id not in user_registry:
        await ctx.send("❌ You are not registered.")
        return

    username = user_registry[user_id]
    remove_user(user_registry, streak_registry, user_id)
    
    await ctx.send(f"✅ Unregistered **{username}**. Your data has been removed.")

@bot.command()
async def profile(ctx, member: discord.Member = None):
    """View your or another user's profile"""
    if member is None:
        member = ctx.author
    
    user_id = str(member.id)

    if user_id not in user_registry:
        if member == ctx.author:
            await ctx.send("❌ You are not registered yet. Use `!register <leetcode_username>`")
        else:
            await ctx.send(f"❌ {member.display_name} is not registered.")
        return

    leetcode_username = user_registry[user_id]
    
    # Build profile message
    msg = f"📊 **Profile: {member.display_name}**\n\n"
    msg += f"**LeetCode:** [{leetcode_username}](https://leetcode.com/{leetcode_username}/)\n\n"
    
    # Streak info
    if user_id in streak_registry:
        current = streak_registry[user_id].get("streak", 0)
        longest = streak_registry[user_id].get("longest_streak", 0)
        total = streak_registry[user_id].get("total_days_solved", 0)
        msg += f"🔥 **Streak:** {current} days (Best: {longest})\n"
        msg += f"📅 **Total Days Solved:** {total}\n\n"
    else:
        msg += f"🔥 **Streak:** 0 days\n\n"
    
    # Difficulty breakdown
    breakdown = get_difficulty_breakdown(leetcode_username)
    msg += f"📈 **Problems Solved:**\n"
    msg += f"🟢 Easy: **{breakdown.get('Easy', 0)}**\n"
    msg += f"🟡 Medium: **{breakdown.get('Medium', 0)}**\n"
    msg += f"🔴 Hard: **{breakdown.get('Hard', 0)}**\n"
    msg += f"📊 Total: **{breakdown.get('All', 0)}**\n\n"
    
    # Ranking
    ranking = get_user_ranking(leetcode_username)
    if ranking:
        msg += f"🏅 **Global Ranking:** #{ranking:,}\n\n"
    
    # Today's solves
    solved_today = has_user_solved_today(leetcode_username)
    if solved_today:
        msg += "✅ **Solved today!**"
        problems = get_today_solved_with_difficulty(leetcode_username)
        if problems:
            msg += "\n\n**Today's Problems:**\n"
            for p in problems:
                diff_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}.get(p.get("difficulty", ""), "⚪")
                msg += f"{diff_emoji} #{p.get('questionNo', '?')}. [{p['title']}]({p['link']}) at {p['time']}\n"
    else:
        msg += "❌ **Not solved today**"

    await ctx.send(msg)

@bot.command()
async def today(ctx):
    """Show what you solved today with difficulty"""
    user_id = str(ctx.author.id)

    if user_id not in user_registry:
        await ctx.send("❌ You are not registered yet. Use `!register <leetcode_username>`")
        return

    leetcode_username = user_registry[user_id]
    problems = get_today_solved_with_difficulty(leetcode_username)
    
    if not problems:
        await ctx.send("❌ You haven't solved any new problems today.")
        return
    
    msg = f"✅ **Today's Solves ({len(problems)} problems)**\n\n"
    
    for p in problems:
        diff_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}.get(p.get("difficulty", ""), "⚪")
        msg += f"{diff_emoji} **{p.get('difficulty', 'Unknown')}** — #{p.get('questionNo', '?')}. [{p['title']}]({p['link']}) at {p['time']}\n"
    
    await ctx.send(msg)

@bot.command()
async def streakboard(ctx):
    """Show streak leaderboard"""
    results = []

    for discord_id in user_registry.keys():
        if discord_id in streak_registry:
            current = streak_registry[discord_id].get("streak", 0)
            longest = streak_registry[discord_id].get("longest_streak", 0)
            results.append((discord_id, current, longest))
        else:
            results.append((discord_id, 0, 0))

    results.sort(key=lambda x: (x[1], x[2]), reverse=True)

    if not results:
        await ctx.send("No registered users.")
        return  

    msg = "🔥 **Streak Leaderboard**\n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    for i, (discord_id, current, longest) in enumerate(results[:10]):
        medal = medals[i] if i < 3 else f"{i+1}."
        msg += f"{medal} <@{discord_id}> — **{current}**🔥 (Best: {longest})\n"

    await ctx.send(msg)

@bot.command()
@commands.has_permissions(administrator=True)
async def setchannel(ctx, channel: discord.TextChannel = None):
    """Set the announcement channel (Admin only)"""
    global bot_config
    
    if channel is None:
        # Show current channel
        current_id = get_announcement_channel_id()
        current_channel = bot.get_channel(current_id)
        if current_channel:
            await ctx.send(f"📢 Current announcement channel: {current_channel.mention}")
        else:
            await ctx.send(f"📢 Current channel ID: `{current_id}` (channel not found)")
        return
    
    bot_config["announcement_channel_id"] = channel.id
    save_config(bot_config)
    await ctx.send(f"✅ Announcement channel set to {channel.mention}")

@setchannel.error
async def setchannel_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need administrator permissions to use this command.")

@bot.command()
async def progress(ctx):
    """Show today's progress for all registered users"""
    if not user_registry:
        await ctx.send("❌ No registered users yet.")
        return
    
    ist = pytz.timezone("Asia/Kolkata")
    today_str = datetime.now(ist).strftime("%B %d, %Y")
    
    msg = f"📊 **Today's Progress** ({today_str})\n\n"
    
    total_problems = 0
    users_solved = 0
    
    user_progress = []
    
    for discord_id, leetcode_username in user_registry.items():
        problems = get_today_solved_with_difficulty(leetcode_username)
        user_progress.append((discord_id, leetcode_username, problems))
        if problems:
            users_solved += 1
            total_problems += len(problems)
    
    # Sort by number of problems solved (descending)
    user_progress.sort(key=lambda x: len(x[2]), reverse=True)
    
    for i, (discord_id, lc_username, problems) in enumerate(user_progress, 1):
        if problems:
            msg += f"**{i}. <@{discord_id}>** — {len(problems)} problem(s)\n"
            for p in problems:
                diff_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}.get(p.get("difficulty", ""), "⚪")
                msg += f"   {diff_emoji} #{p.get('questionNo', '?')}. {p['title']} ({p.get('difficulty', 'Unknown')}) at {p['time']}\n"
            msg += "\n"
        else:
            msg += f"**{i}. <@{discord_id}>** — ❌ Not solved yet\n\n"
    
    msg += f"---\n**Total:** {total_problems} problem(s) solved by {users_solved}/{len(user_registry)} users"
    
    await ctx.send(msg)

@bot.command()
async def users(ctx):
    """Show all registered users"""
    if not user_registry:
        await ctx.send("❌ No registered users yet.")
        return
    
    msg = "👥 **Registered Users**\n\n"
    
    for i, (discord_id, lc_username) in enumerate(user_registry.items(), 1):
        msg += f"{i}. <@{discord_id}> → [{lc_username}](https://leetcode.com/{lc_username}/)\n"
    
    msg += f"\n**Total:** {len(user_registry)} users"
    
    await ctx.send(msg)

@bot.command()
async def weekly(ctx):
    """Show weekly leaderboard (resets every Sunday 11:59 PM IST)"""
    # Sync any missed submissions before displaying
    weekly_data = ensure_weekly_synced()
    
    if not weekly_data["data"]:
        await ctx.send("📅 No problems solved this week yet!")
        return
    
    # Sort by unique problems (primary), then submissions (secondary)
    results = []
    for discord_id, data in weekly_data["data"].items():
        # Support both old 'count' field and new 'unique_problems' field
        unique = data.get("unique_problems", data.get("count", 0))
        submissions = data.get("submissions", unique)  # fallback to unique if no submissions tracked
        results.append((
            discord_id, 
            unique,
            submissions,
            data.get("easy", 0),
            data.get("medium", 0),
            data.get("hard", 0)
        ))
    
    results.sort(key=lambda x: (x[1], x[2]), reverse=True)
    
    week_start = weekly_data.get("week_start", "Unknown")
    msg = f"📅 **Weekly Leaderboard**\n_(Week starting: {week_start})_\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    
    for i, (discord_id, unique, submissions, easy, medium, hard) in enumerate(results[:10]):
        medal = medals[i] if i < 3 else f"{i+1}."
        breakdown = f"🟢{easy} 🟡{medium} 🔴{hard}"
        msg += f"{medal} <@{discord_id}> — **{unique}** problems solved ({submissions} submissions) | {breakdown}\n"
    
    total_unique = sum(r[1] for r in results)
    total_subs = sum(r[2] for r in results)
    msg += f"\n---\n**Total this week:** {total_unique} problems solved ({total_subs} submissions) by {len(results)} users"
    
    await ctx.send(msg)


@bot.command()
async def problem(ctx, question_no: int):
    """Display full description of a LeetCode problem by question number"""
    await ctx.send(f"🔍 Fetching problem #{question_no}...")
    
    details = fetch_problem_by_number(question_no)
    
    if not details:
        await ctx.send(f"❌ Could not find problem #{question_no}. Please check the question number.")
        return
    
    q_no = details.get("questionFrontendId", "?")
    title = details.get("title", "Unknown")
    difficulty = details.get("difficulty", "Unknown")
    title_slug = details.get("titleSlug", "")
    content = details.get("content", "No description available.")
    tags = details.get("topicTags", [])
    ac_rate = details.get("acRate", 0)
    likes = details.get("likes", 0)
    dislikes = details.get("dislikes", 0)
    
    diff_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}.get(difficulty, "⚪")
    tag_str = ", ".join([t["name"] for t in tags[:5]]) if tags else "None"
    
    # Convert HTML to plain text
    description = strip_html(content)
    
    # Truncate if too long for Discord (2000 char limit)
    if len(description) > 1500:
        description = description[:1500] + "\n\n... _(truncated)_"
    
    link = f"https://leetcode.com/problems/{title_slug}/"
    
    msg = f"{diff_emoji} **#{q_no}. {title}** ({difficulty})\n"
    msg += f"📊 Acceptance: {ac_rate:.1f}% | 👍 {likes} | 👎 {dislikes}\n"
    msg += f"🏷️ Tags: {tag_str}\n"
    msg += f"🔗 {link}\n\n"
    msg += f"**Description:**\n{description}"
    
    # Split message if too long
    if len(msg) > 2000:
        await ctx.send(msg[:2000])
        if len(msg) > 2000:
            await ctx.send(msg[2000:4000])
    else:
        await ctx.send(msg)


@bot.command()
async def daily(ctx):
    """Display today's LeetCode daily challenge"""
    await ctx.send("🌅 Fetching today's daily challenge...")
    
    details = fetch_daily_challenge()
    
    if not details:
        await ctx.send("❌ Could not fetch today's daily challenge. Please try again later.")
        return
    
    q_no = details.get("questionFrontendId", "?")
    title = details.get("title", "Unknown")
    difficulty = details.get("difficulty", "Unknown")
    title_slug = details.get("titleSlug", "")
    content = details.get("content", "No description available.")
    tags = details.get("topicTags", [])
    ac_rate = details.get("acRate", 0)
    likes = details.get("likes", 0)
    dislikes = details.get("dislikes", 0)
    date = details.get("date", "")
    
    diff_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}.get(difficulty, "⚪")
    tag_str = ", ".join([t["name"] for t in tags[:5]]) if tags else "None"
    
    # Convert HTML to plain text
    description = strip_html(content)
    
    # Truncate if too long for Discord (2000 char limit)
    if len(description) > 1500:
        description = description[:1500] + "\n\n... _(truncated)_"
    
    link = f"https://leetcode.com/problems/{title_slug}/"
    
    msg = f"📅 **Daily Challenge** ({date})\n\n"
    msg += f"{diff_emoji} **#{q_no}. {title}** ({difficulty})\n"
    msg += f"📊 Acceptance: {ac_rate:.1f}% | 👍 {likes} | 👎 {dislikes}\n"
    msg += f"🏷️ Tags: {tag_str}\n"
    msg += f"🔗 {link}\n\n"
    msg += f"**Description:**\n{description}"
    
    # Split message if too long
    if len(msg) > 2000:
        await ctx.send(msg[:2000])
        if len(msg) > 2000:
            await ctx.send(msg[2000:4000])
    else:
        await ctx.send(msg)


webserver.keep_alive()
bot.run(token, log_handler=handler, log_level=logging.DEBUG)