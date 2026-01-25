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
    fetch_problem_details
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
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
    save_config
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

async def daily_check():
    channel = bot.get_channel(get_announcement_channel_id())

    if channel is None:
        print("Channel not found")
        return

    await channel.send("📊 **Daily LeetCode Status Check**")

    for discord_id, leetcode_username in user_registry.items():
        solved = has_user_solved_today(leetcode_username)

        mention = f"<@{discord_id}>"
        if solved:
            await channel.send(f"✅ {mention} is safe today!")
        else:
            await channel.send(f"❌ {mention} did NOT solve today!")


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
                await channel.send(f"✅ {mention} is on {streak}🔥 streak!")
            else:
                streak_registry[discord_id]["streak"] = 0
                streak_registry[discord_id]["last_checked_date"] = today
                streak = streak_registry[discord_id]["streak"]
                mention = f"<@{discord_id}>"
                await channel.send(f"Oops! {mention} forgot to solve today. The streak is now {streak}🔥")
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
    data = load_announcements()

    if str(discord_id) not in data:
        data[str(discord_id)] = []

    existing_timestamps = {
        entry["timestamp"] for entry in data[str(discord_id)]
    }

    submissions = fetch_recent_submissions(leetcode_username)

    for sub in submissions:
        if sub["statusDisplay"] != "Accepted":
            continue

        ts = int(sub["timestamp"])

        if ts in existing_timestamps:
            continue

        data[str(discord_id)].append({
            "title": sub["title"],
            "titleSlug": sub.get("titleSlug", ""),
            "timestamp": ts,
            "announced": False
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

    data = load_announcements()

    for discord_id, solves in data.items():
        new_solves = [
            s for s in solves if not s.get("announced", False)
        ]

        # Only announce if there are new solves
        if not new_solves:
            continue

        mention = f"<@{discord_id}>"
        
        # Fetch problem details for each solve
        lines = []
        for s in new_solves:
            title_slug = s.get("titleSlug", "")
            details = fetch_problem_details(title_slug) if title_slug else None
            
            if details:
                q_no = details.get("questionFrontendId", "?")
                diff = details.get("difficulty", "Unknown")
                diff_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}.get(diff, "⚪")
                lines.append(f"{diff_emoji} #{q_no}. {s['title']} ({diff})")
            else:
                lines.append(f"- {s['title']}")

        await channel.send(
            f"🔥 {mention} solved {len(new_solves)} problem(s)!\n" + "\n".join(lines)
        )

        for s in new_solves:
            s["announced"] = True

    save_announcements(data)


async def smart_nudge_job():
    """Send DM to users who haven't solved by 9 PM IST"""
    for discord_id, leetcode_username in user_registry.items():
        if not has_user_solved_today(leetcode_username):
            try:
                user = await bot.fetch_user(int(discord_id))
                if user:
                    await user.send(
                        f"⏰ **Friendly Reminder!**\n\n"
                        f"Hey! You haven't solved any LeetCode problem today yet.\n"
                        f"There's still time before midnight! 💪\n\n"
                        f"Keep your streak alive! 🔥"
                    )
            except Exception as e:
                print(f"Could not send nudge to {discord_id}: {e}")


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
    
    await channel.send(msg)


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


@bot.event
async def on_ready():
    print("Bot is online!")

    if not scheduler.running:
        scheduler.start()


@bot.event
async def on_member_join(member):
    await member.send(f"Welcome to the server {member.name}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if "shit" in message.content.lower():
        await message.delete()
        await message.channel.send(f"{message.author.mention}- Hey, dont use that word! ")
    
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
    results = []

    for discord_id, lc_username in user_registry.items():
        count = get_today_accepted_count(lc_username)
        results.append((discord_id, count))

    results.sort(key=lambda x: x[1], reverse=True)

    if not results:
        await ctx.send("No registered users.")
        return  

    msg = "🏆 **Today's Leaderboard**\n\n"
    rank = 1
    for discord_id, count in results:
        msg += f"{rank}. <@{discord_id}> — **{count}** solved\n"
        rank += 1

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


webserver.keep_alive()
bot.run(token, log_handler=handler, log_level=logging.DEBUG)