# ---------------- Part 1: Setup, Config, Databases, and Helper Functions ----------------

import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import random
from datetime import datetime, timedelta

# ---------------- CONFIG ----------------
TOKEN = os.getenv("TOKEN") or "YOUR_BOT_TOKEN_HERE"
COMMAND_PREFIX = "!"
OWNER_ID = 1169273992289456341
CO_OWNER_ID = 958273785037983754
DEFAULT_ROLE_NAME = "Member"
LOG_CHANNEL_NAME = "bot-logs"
WELCOME_CHANNEL_NAME = "arrivals"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)
tree = bot.tree  # for slash commands

# ---------------- DATABASE SIMULATION ----------------
# Economy
money_data = {}
daily_claimed = {}

# Levels / XP
xp_data = {}
level_data = {}

# Moderation
warn_data = {}
disabled_users = set()

# Invite tracking
invite_cache = {}   # guild_id -> {invite_code: uses}
invite_data = {}    # inviter_id -> total invites

# Giveaways
giveaways = {}  # guild_id -> giveaway info

# Scheduled messages
scheduled_messages = []

# Autorole
autorole_id = None

# Reaction / Mini-games
reaction_games = {}
tictactoe_games = {}
blackjack_games = {}

# ---------------- HELPER FUNCTIONS ----------------
def is_owner(user):
    return user.id == OWNER_ID

def is_owner_or_co(user):
    return user.id in [OWNER_ID, CO_OWNER_ID]

def add_xp(user_id: int, amount: int = None):
    """Add XP and handle level-ups. Returns (leveled_up, new_level)"""
    amount = amount or random.randint(5, 15)
    xp_data[user_id] = xp_data.get(user_id, 0) + amount
    current_level = level_data.get(user_id, 0)
    required_xp = int(100 * (1.5 ** current_level))  # exponentially harder
    leveled_up = False
    new_level = current_level
    while xp_data[user_id] >= required_xp:
        xp_data[user_id] -= required_xp
        current_level += 1
        new_level = current_level
        leveled_up = True
        required_xp = int(100 * (1.5 ** current_level))
    level_data[user_id] = current_level
    return leveled_up, new_level

async def get_log_channel(guild: discord.Guild):
    channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if not channel:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        channel = await guild.create_text_channel(LOG_CHANNEL_NAME, overwrites=overwrites)
    return channel

async def log_action(guild: discord.Guild, message: str):
    channel = await get_log_channel(guild)
    await channel.send(message)

# ---------------- EVENTS ----------------
@bot.event
async def on_ready():
    print(f"🚀 Bot online as {bot.user}")
    # Start scheduled messages loop
    if not check_scheduled_messages.is_running():
        check_scheduled_messages.start()
    if not check_giveaways.is_running():
        check_giveaways.start()
    # Cache invites
    for guild in bot.guilds:
        invites = await guild.invites()
        invite_cache[guild.id] = {i.code: i.uses for i in invites}
    try:
        await tree.sync()
        print("✅ Slash commands synced.")
    except Exception as e:
        print(f"❌ Error syncing slash commands: {e}")

@bot.event
async def on_invite_create(invite):
    invite_cache[invite.guild.id] = {i.code: i.uses for i in await invite.guild.invites()}

@bot.event
async def on_invite_delete(invite):
    invite_cache[invite.guild.id] = {i.code: i.uses for i in await invite.guild.invites()}

@bot.event
async def on_message(message):
    if message.author.bot or message.author.id in disabled_users:
        return
    leveled_up, new_level = add_xp(message.author.id)
    if leveled_up:
        await message.channel.send(f"🎉 {message.author.mention} leveled up to **{new_level}**!")
    await bot.process_commands(message)
    
# ---------------- Part 2: Owner / Co-Owner Commands & Admin Utilities ----------------

# ---------------- OWNER / CO-OWNER COMMANDS ----------------

@bot.command()
async def shutdown(ctx):
    """Shutdown the bot (Owner/Co-owner only)."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You do not have permission to shutdown the bot.")
        return

    await ctx.send("⚡ Shutting down the bot...")
    await log_action(ctx.guild, f"{ctx.author} shut down the bot.")
    await bot.close()


@bot.command()
async def disable_user(ctx, member: discord.Member):
    """Disable a user from using bot commands."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You cannot disable users.")
        return

    disabled_users.add(member.id)

    await ctx.send(f"🚫 {member.mention} can no longer use bot commands.")
    await log_action(ctx.guild, f"{ctx.author} disabled {member} from using commands.")


@bot.command()
async def enable_user(ctx, member: discord.Member):
    """Re-enable a disabled user."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You cannot enable users.")
        return

    disabled_users.discard(member.id)

    await ctx.send(f"✅ {member.mention} can now use bot commands again.")
    await log_action(ctx.guild, f"{ctx.author} enabled {member} for commands.")


# ---------------- BROADCAST ----------------

@bot.command()
async def broadcast(ctx, *, message):
    """Send a message to all servers."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You do not have permission.")
        return

    sent = 0

    for guild in bot.guilds:
        channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)

        if not channel:
            continue

        try:
            await channel.send(f"📢 **Broadcast from {ctx.author}:**\n{message}")
            sent += 1
        except:
            continue

    await ctx.send(f"✅ Broadcast sent to {sent} servers.")


# ---------------- AUTOROLE ----------------

@bot.command()
async def autorole(ctx, role: discord.Role):
    """Set the autorole for new members."""
    global autorole_id

    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You cannot set autorole.")
        return

    autorole_id = role.id

    await ctx.send(f"✅ Autorole set to **{role.name}**.")
    await log_action(ctx.guild, f"{ctx.author} set autorole to {role.name}.")


# ---------------- DM ALL MEMBERS ----------------

@bot.command()
async def dmall(ctx, *, message):
    """DM all server members."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You cannot use this command.")
        return

    sent = 0

    for member in ctx.guild.members:
        if member.bot:
            continue

        try:
            await member.send(message)
            sent += 1
        except:
            continue

    await ctx.send(f"📬 Sent DM to **{sent} members**.")
    await log_action(ctx.guild, f"{ctx.author} DM'd {sent} members.")


# ---------------- ECONOMY ADMIN ----------------

@bot.command()
async def setbalance(ctx, member: discord.Member, amount: int):
    """Set a user's balance."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You cannot set balances.")
        return

    money_data[member.id] = amount

    await ctx.send(f"💰 {member.mention}'s balance set to **{amount}** coins.")
    await log_action(ctx.guild, f"{ctx.author} set {member}'s balance to {amount}.")


@bot.command()
async def addcoins(ctx, member: discord.Member, amount: int):
    """Add coins to a user."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You cannot add coins.")
        return

    money_data[member.id] = money_data.get(member.id, 0) + amount

    await ctx.send(f"💰 Added **{amount} coins** to {member.mention}.")
    await log_action(ctx.guild, f"{ctx.author} added {amount} coins to {member}.")


@bot.command()
async def removecoins(ctx, member: discord.Member, amount: int):
    """Remove coins from a user."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You cannot remove coins.")
        return

    money_data[member.id] = max(0, money_data.get(member.id, 0) - amount)

    await ctx.send(f"💰 Removed **{amount} coins** from {member.mention}.")
    await log_action(ctx.guild, f"{ctx.author} removed {amount} coins from {member}.")


# ---------------- BOT INFO ----------------

@bot.command()
async def botinfo(ctx):
    """Show bot information."""
    embed = discord.Embed(
        title="🤖 Bot Information",
        color=discord.Color.blue()
    )

    embed.add_field(name="Servers", value=len(bot.guilds))
    embed.add_field(name="Users", value=len(bot.users))
    embed.add_field(name="Latency", value=f"{round(bot.latency*1000)} ms")
    embed.add_field(name="Prefix", value=COMMAND_PREFIX)

    await ctx.send(embed=embed)
    
# ---------------- Part 3: Moderation Commands ----------------

# ---------------- WARN SYSTEM ----------------

@bot.command()
async def warn(ctx, member: discord.Member, *, reason="No reason provided"):
    """Warn a user."""
    if not ctx.author.guild_permissions.manage_messages:
        await ctx.send("❌ You do not have permission to warn users.")
        return

    warn_data[member.id] = warn_data.get(member.id, 0) + 1

    await ctx.send(
        f"⚠️ {member.mention} has been warned.\n"
        f"Reason: {reason}\n"
        f"Total warnings: {warn_data[member.id]}"
    )

    await log_action(
        ctx.guild,
        f"{ctx.author} warned {member} | Reason: {reason}"
    )

    try:
        await member.send(
            f"You were warned in **{ctx.guild.name}**.\nReason: {reason}"
        )
    except:
        pass


@bot.command()
async def warnings(ctx, member: discord.Member):
    """Check warnings for a user."""
    count = warn_data.get(member.id, 0)
    await ctx.send(f"⚠️ {member.mention} has **{count} warnings**.")


@bot.command()
async def clearwarnings(ctx, member: discord.Member):
    """Clear a user's warnings."""
    if not ctx.author.guild_permissions.manage_messages:
        await ctx.send("❌ You cannot clear warnings.")
        return

    warn_data[member.id] = 0
    await ctx.send(f"✅ Cleared warnings for {member.mention}.")


# ---------------- KICK ----------------

@bot.command()
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    """Kick a member."""
    if not ctx.author.guild_permissions.kick_members:
        await ctx.send("❌ You cannot kick members.")
        return

    try:
        await member.kick(reason=reason)

        await ctx.send(f"👢 {member} was kicked.\nReason: {reason}")

        await log_action(
            ctx.guild,
            f"{ctx.author} kicked {member} | Reason: {reason}"
        )

    except discord.Forbidden:
        await ctx.send("❌ I cannot kick this user.")


# ---------------- BAN ----------------

@bot.command()
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    """Ban a member."""
    if not ctx.author.guild_permissions.ban_members:
        await ctx.send("❌ You cannot ban members.")
        return

    try:
        await member.ban(reason=reason)

        await ctx.send(f"🔨 {member} was banned.\nReason: {reason}")

        await log_action(
            ctx.guild,
            f"{ctx.author} banned {member} | Reason: {reason}"
        )

    except discord.Forbidden:
        await ctx.send("❌ I cannot ban this user.")


# ---------------- UNBAN ----------------

@bot.command()
async def unban(ctx, user_id: int):
    """Unban a user by ID."""
    if not ctx.author.guild_permissions.ban_members:
        await ctx.send("❌ You cannot unban users.")
        return

    user = await bot.fetch_user(user_id)

    try:
        await ctx.guild.unban(user)

        await ctx.send(f"✅ {user} has been unbanned.")

        await log_action(
            ctx.guild,
            f"{ctx.author} unbanned {user}"
        )

    except:
        await ctx.send("❌ Could not unban this user.")


# ---------------- TIMEOUT (MUTE) ----------------

@bot.command()
async def timeout(ctx, member: discord.Member, minutes: int):
    """Timeout a member for a number of minutes."""
    if not ctx.author.guild_permissions.moderate_members:
        await ctx.send("❌ You cannot timeout members.")
        return

    try:
        duration = timedelta(minutes=minutes)

        await member.timeout(duration)

        await ctx.send(
            f"🔇 {member.mention} was timed out for **{minutes} minutes**."
        )

        await log_action(
            ctx.guild,
            f"{ctx.author} timed out {member} for {minutes} minutes."
        )

    except:
        await ctx.send("❌ Could not timeout this user.")


# ---------------- LOCK CHANNEL ----------------

@bot.command()
async def lock(ctx):
    """Lock the current channel."""
    if not ctx.author.guild_permissions.manage_channels:
        await ctx.send("❌ You cannot lock channels.")
        return

    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False

    await ctx.channel.set_permissions(
        ctx.guild.default_role,
        overwrite=overwrite
    )

    await ctx.send("🔒 Channel locked.")

    await log_action(
        ctx.guild,
        f"{ctx.author} locked {ctx.channel.name}"
    )


# ---------------- UNLOCK CHANNEL ----------------

@bot.command()
async def unlock(ctx):
    """Unlock the current channel."""
    if not ctx.author.guild_permissions.manage_channels:
        await ctx.send("❌ You cannot unlock channels.")
        return

    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True

    await ctx.channel.set_permissions(
        ctx.guild.default_role,
        overwrite=overwrite
    )

    await ctx.send("🔓 Channel unlocked.")

    await log_action(
        ctx.guild,
        f"{ctx.author} unlocked {ctx.channel.name}"
    )


# ---------------- PURGE MESSAGES ----------------

@bot.command()
async def purge(ctx, amount: int):
    """Delete multiple messages."""
    if not ctx.author.guild_permissions.manage_messages:
        await ctx.send("❌ You cannot purge messages.")
        return

    deleted = await ctx.channel.purge(limit=amount + 1)

    await ctx.send(
        f"🧹 Deleted **{len(deleted)-1} messages**.",
        delete_after=5
    )

    await log_action(
        ctx.guild,
        f"{ctx.author} purged {len(deleted)-1} messages in {ctx.channel}"
    )
    
# ---------------- Part 4: Invite Tracking, Welcome, Autorole, Leaderboards ----------------

# ---------------- AUTOROLE SETUP ----------------
autorole_id = None  # default is None, set via command

@bot.command()
async def set_autorole(ctx, role: discord.Role):
    """Set the role automatically assigned to new members."""
    if not is_owner_or_co(ctx.author) and not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ You do not have permission to set autorole.")
        return

    global autorole_id
    autorole_id = role.id
    await ctx.send(f"✅ Autorole set to **{role.name}**.")
    await log_action(ctx.guild, f"{ctx.author} set autorole to {role.name}.")


# ---------------- WELCOME + INVITE TRACKING ----------------
invite_cache = {}  # guild_id -> {invite_code: uses}
invite_data = {}   # inviter_id -> total_invites

@bot.event
async def on_ready():
    """Cache invites when bot starts."""
    for guild in bot.guilds:
        invites = await guild.invites()
        invite_cache[guild.id] = {i.code: i.uses for i in invites}
    print(f"✅ Invite cache initialized for {len(bot.guilds)} guild(s).")


@bot.event
async def on_member_join(member: discord.Member):
    """Handle welcome message, autorole, and invite tracking."""
    guild = member.guild
    used_invite = None
    invites_before = invite_cache.get(guild.id, {})
    invites_after = await guild.invites()

    # Determine which invite was used
    for invite in invites_after:
        if invite.uses > invites_before.get(invite.code, 0):
            used_invite = invite
            break

    inviter = used_invite.inviter if used_invite else None

    # Update inviter stats
    if inviter:
        invite_data[inviter.id] = invite_data.get(inviter.id, 0) + 1

    # Assign autorole
    if autorole_id:
        role = guild.get_role(autorole_id)
        if role:
            try:
                await member.add_roles(role)
            except discord.Forbidden:
                print(f"Cannot assign autorole to {member}")

    # Welcome message
    channel = discord.utils.get(guild.text_channels, name=WELCOME_CHANNEL_NAME)
    if channel:
        msg = f"👋 Welcome {member.mention}!\nUsername: {member}\n"
        msg += f"Invited by: {inviter.mention}" if inviter else "Inviter not tracked."
        msg += f"\nCurrent total invites by {inviter.mention}: {invite_data.get(inviter.id, 0)}" if inviter else ""
        await channel.send(msg)

    # Update invite cache
    invite_cache[guild.id] = {i.code: i.uses for i in invites_after}


# ---------------- INVITE LEADERBOARD ----------------
@bot.command()
async def invite_leaderboard(ctx, top: int = 10):
    """Show top inviters in the server."""
    sorted_invites = sorted(invite_data.items(), key=lambda x: x[1], reverse=True)[:top]
    embed = discord.Embed(title=f"🏆 Top {top} Inviters", color=discord.Color.purple())
    for i, (user_id, count) in enumerate(sorted_invites, start=1):
        member = ctx.guild.get_member(user_id)
        if member:
            embed.add_field(name=f"{i}. {member}", value=f"{count} invites", inline=False)
    await ctx.send(embed=embed)


# ---------------- XP / LEVEL INTEGRATION ----------------
level_data = {}  # user_id -> level
xp_data = {}     # user_id -> XP

def add_xp(user_id: int, min_xp: int = 5, max_xp: int = 15):
    """Add XP to a user and handle level up."""
    xp_gain = random.randint(min_xp, max_xp)
    xp_data[user_id] = xp_data.get(user_id, 0) + xp_gain

    current_level = level_data.get(user_id, 0)
    # Level-up formula: XP required increases exponentially
    required_xp = int(100 * (1.5 ** current_level))
    if xp_data[user_id] >= required_xp:
        level_data[user_id] = current_level + 1
        xp_data[user_id] -= required_xp
        return True, current_level + 1
    return False, current_level


@bot.command()
async def level(ctx, member: discord.Member = None):
    """Check the level and XP of a member."""
    member = member or ctx.author
    lvl = level_data.get(member.id, 0)
    xp = xp_data.get(member.id, 0)
    required = int(100 * (1.5 ** lvl))
    await ctx.send(f"🏆 {member} is level **{lvl}** with **{xp}/{required} XP**.")


@bot.command()
async def rank(ctx, member: discord.Member = None):
    """Check the server rank of a member based on level and XP."""
    member = member or ctx.author
    sorted_users = sorted(level_data.items(), key=lambda x: (x[1], xp_data.get(x[0],0)), reverse=True)
    for i, (uid, _) in enumerate(sorted_users, start=1):
        if uid == member.id:
            await ctx.send(f"📊 {member} is rank **{i}** in the server!")
            return
    await ctx.send("❌ Member not found in rank list.")


# ---------------- XP ON MESSAGE ----------------
@bot.event
async def on_message(message):
    """Award XP for every message and process commands."""
    if message.author.bot or message.author.id in disabled_users:
        return
    leveled_up, new_level = add_xp(message.author.id)
    if leveled_up:
        await message.channel.send(f"🎉 {message.author.mention} leveled up to **{new_level}**!")
    await bot.process_commands(message)
  
# ---------------- Part 5: Fun Commands, Economy & Mini-Games ----------------

# ----------------- FUN COMMANDS -----------------
@bot.command()
async def coinflip(ctx):
    """Flip a coin."""
    result = random.choice(["Heads", "Tails"])
    await ctx.send(f"🪙 {ctx.author.mention} flipped **{result}**!")

@bot.command()
async def roll(ctx, sides: int = 6):
    """Roll a dice with N sides."""
    result = random.randint(1, sides)
    await ctx.send(f"🎲 {ctx.author.mention} rolled a **{result}** on a {sides}-sided dice!")

@bot.command()
async def hug(ctx, member: discord.Member = None):
    """Hug a member."""
    member = member or ctx.author
    await ctx.send(f"🤗 {ctx.author.mention} hugs {member.mention}")

@bot.command()
async def slap(ctx, member: discord.Member = None):
    """Slap a member."""
    member = member or ctx.author
    await ctx.send(f"👋 {ctx.author.mention} slaps {member.mention}")

@bot.command()
async def say(ctx, *, text):
    """Bot repeats a message."""
    await ctx.send(f"🗣 {text}")

@bot.command()
async def avatar(ctx, member: discord.Member = None):
    """Get a user's avatar."""
    member = member or ctx.author
    await ctx.send(member.display_avatar.url)


# ----------------- ECONOMY COMMANDS -----------------
@bot.command()
async def balance(ctx, member: discord.Member = None):
    """Check a member's coin balance."""
    member = member or ctx.author
    bal = money_data.get(member.id, 0)
    await ctx.send(f"💰 {member.mention} has **{bal} coins**.")

@bot.command()
async def pay(ctx, member: discord.Member, amount: int):
    """Pay another member coins."""
    sender_bal = money_data.get(ctx.author.id, 0)
    if sender_bal < amount:
        await ctx.send("❌ Not enough coins!")
        return
    money_data[ctx.author.id] -= amount
    money_data[member.id] = money_data.get(member.id, 0) + amount
    await ctx.send(f"✅ {ctx.author.mention} paid {member.mention} **{amount} coins**.")

@bot.command()
async def daily(ctx):
    """Claim daily coins (24h cooldown)."""
    now = datetime.utcnow()
    last_claim = daily_claimed.get(ctx.author.id)
    if last_claim and now - last_claim < timedelta(hours=24):
        remaining = timedelta(hours=24) - (now - last_claim)
        await ctx.send(f"⏳ Already claimed daily coins. Try again in {remaining}.")
        return
    coins = random.randint(50, 200)
    money_data[ctx.author.id] = money_data.get(ctx.author.id, 0) + coins
    daily_claimed[ctx.author.id] = now
    await ctx.send(f"💵 You collected **{coins} coins** today!")

@bot.command()
async def setbalance(ctx, member: discord.Member, amount: int):
    """Set a user's balance (Owner/Co-owner only)."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You do not have permission.")
        return
    money_data[member.id] = amount
    await ctx.send(f"✅ {member.mention}'s balance is now **{amount} coins**.")


@bot.command()
async def leaderboard(ctx, top: int = 10):
    """Show top coin holders."""
    sorted_balances = sorted(money_data.items(), key=lambda x: x[1], reverse=True)[:top]
    embed = discord.Embed(title=f"🏆 Top {top} Richest Users", color=discord.Color.gold())
    for i, (uid, bal) in enumerate(sorted_balances, 1):
        member = ctx.guild.get_member(uid)
        if member:
            embed.add_field(name=f"{i}. {member}", value=f"{bal} coins", inline=False)
    await ctx.send(embed=embed)


# ----------------- BLACKJACK MINI-GAME -----------------
blackjack_games = {}  # user_id -> game data

@bot.command()
async def blackjack(ctx, wager: int = 0):
    """Start a blackjack game."""
    if ctx.author.id in blackjack_games:
        await ctx.send("❌ Already in a blackjack game!")
        return
    deck = [2,3,4,5,6,7,8,9,10,10,10,10,11]*4
    random.shuffle(deck)
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]
    blackjack_games[ctx.author.id] = {"player": player_hand, "dealer": dealer_hand, "deck": deck, "wager": wager}
    await ctx.send(f"♠ Blackjack started! Your hand: {player_hand}, dealer shows: {dealer_hand[0]}")


@bot.command()
async def hit(ctx):
    """Draw a card in blackjack."""
    game = blackjack_games.get(ctx.author.id)
    if not game:
        await ctx.send("❌ Not in a blackjack game!")
        return
    game["player"].append(game["deck"].pop())
    total = sum(game["player"])
    await ctx.send(f"Your hand: {game['player']}, total: {total}")
    if total > 21:
        await ctx.send("💥 Bust! You lose.")
        del blackjack_games[ctx.author.id]
    elif total == 21:
        await ctx.send("🎉 Blackjack! You win!")
        del blackjack_games[ctx.author.id]


@bot.command()
async def stand(ctx):
    """End turn and let dealer play in blackjack."""
    game = blackjack_games.get(ctx.author.id)
    if not game:
        await ctx.send("❌ Not in a blackjack game!")
        return
    deck = game["deck"]
    dealer_total = sum(game["dealer"])
    player_total = sum(game["player"])
    while dealer_total < 17:
        game["dealer"].append(deck.pop())
        dealer_total = sum(game["dealer"])
    await ctx.send(f"Dealer hand: {game['dealer']}, total: {dealer_total}")
    if dealer_total > 21 or player_total > dealer_total:
        await ctx.send("✅ You win!")
    elif dealer_total == player_total:
        await ctx.send("⚖ Draw!")
    else:
        await ctx.send("❌ You lose!")
    del blackjack_games[ctx.author.id]


# ----------------- SCHEDULED MESSAGES -----------------
scheduled_messages = []

@bot.command()
async def schedule(ctx, minutes: int, *, message):
    """Schedule a message to be sent after X minutes."""
    send_time = datetime.utcnow() + timedelta(minutes=minutes)
    scheduled_messages.append({"channel": ctx.channel, "message": message, "time": send_time})
    await ctx.send(f"⏳ Message scheduled in {minutes} minutes.")


@tasks.loop(seconds=10)
async def check_scheduled_messages():
    """Send scheduled messages when time arrives."""
    now = datetime.utcnow()
    for msg in scheduled_messages[:]:
        if now >= msg["time"]:
            await msg["channel"].send(msg["message"])
            scheduled_messages.remove(msg)
            
# ---------------- Part 6: Advanced Giveaways, Reaction Games & Mini-Games ----------------

# ----------------- ADVANCED GIVEAWAYS -----------------
giveaways = {}  # guild_id -> giveaway info

@bot.command()
@commands.has_permissions(administrator=True)
async def giveaway(ctx, duration: int, *, prize: str):
    """Start an advanced giveaway."""
    if ctx.guild.id in giveaways:
        await ctx.send("❌ A giveaway is already running!")
        return
    end_time = datetime.utcnow() + timedelta(minutes=duration)
    msg = await ctx.send(f"🎉 Giveaway for **{prize}**! React with 🎉 to enter! Ends in {duration} minutes.")
    await msg.add_reaction("🎉")
    giveaways[ctx.guild.id] = {
        "channel": ctx.channel,
        "message": msg,
        "prize": prize,
        "end": end_time,
        "entries": set()
    }

@tasks.loop(seconds=30)
async def check_giveaways():
    """Automatically conclude giveaways."""
    now = datetime.utcnow()
    to_remove = []
    for guild_id, data in giveaways.items():
        if now >= data["end"]:
            channel = data["channel"]
            if data["entries"]:
                winner = random.choice(list(data["entries"]))
                await channel.send(f"🎊 Giveaway ended! Winner: {winner.mention}")
            else:
                await channel.send(f"Giveaway for **{data['prize']}** ended with no entries.")
            to_remove.append(guild_id)
    for gid in to_remove:
        giveaways.pop(gid, None)

@bot.command()
@commands.has_permissions(administrator=True)
async def reroll(ctx, guild_id: int):
    """Manually reroll a giveaway winner."""
    data = giveaways.get(guild_id)
    if not data:
        await ctx.send("❌ No giveaway found for this server.")
        return
    if not data["entries"]:
        await ctx.send("❌ No entries to reroll.")
        return
    winner = random.choice(list(data["entries"]))
    await data["channel"].send(f"🎉 Giveaway rerolled! New winner: {winner.mention}")


@bot.event
async def on_reaction_add(reaction, user):
    """Handle reactions for giveaways and reaction-based mini-games."""
    if user.bot:
        return
    # Giveaway entry
    for data in giveaways.values():
        if data["message"].id == reaction.message.id and reaction.emoji == "🎉":
            data["entries"].add(user)

# ----------------- REACTION GAMES (RPS) -----------------
reaction_games = {}  # user_id -> game data

@bot.command()
async def rps(ctx, opponent: discord.Member):
    """Rock Paper Scissors game."""
    if ctx.author.id in reaction_games or opponent.id in reaction_games:
        await ctx.send("❌ One of the players is already in a game!")
        return
    msg = await ctx.send(f"{ctx.author.mention} vs {opponent.mention}: React with ✊ ✋ ✌️")
    for emoji in ["✊", "✋", "✌️"]:
        await msg.add_reaction(emoji)
    reaction_games[ctx.author.id] = {"opponent": opponent, "message": msg, "choices": {}}
    reaction_games[opponent.id] = reaction_games[ctx.author.id]

@bot.event
async def on_reaction_add(reaction, user):
    """Process RPS game reactions."""
    if user.bot:
        return
    game = reaction_games.get(user.id)
    if game and reaction.message.id == game["message"].id:
        game["choices"][user.id] = reaction.emoji
        if len(game["choices"]) == 2:
            p1, p2 = list(game["choices"].keys())
            choice1, choice2 = game["choices"][p1], game["choices"][p2]
            winner_text = None
            if choice1 == choice2:
                winner_text = "⚖ It's a draw!"
            elif (choice1=="✊" and choice2=="✌️") or (choice1=="✋" and choice2=="✊") or (choice1=="✌️" and choice2=="✋"):
                winner_text = f"🎉 {bot.get_user(p1).mention} wins!"
            else:
                winner_text = f"🎉 {bot.get_user(p2).mention} wins!"
            await reaction.message.channel.send(winner_text)
            # Clean up
            for uid in [p1, p2]:
                reaction_games.pop(uid, None)

# ----------------- CATCH MINI-GAME -----------------
@bot.command()
async def catch(ctx):
    """Catch a wild creature and earn coins."""
    creatures = ["Dragon", "Goblin", "Phoenix", "Unicorn", "Slime"]
    creature = random.choice(creatures)
    await ctx.send(f"A wild **{creature}** appeared! Type `catch` to catch it!")

    def check(m):
        return m.content.lower() == "catch" and m.author == ctx.author

    try:
        msg = await bot.wait_for('message', check=check, timeout=15)
        reward = random.randint(50, 200)
        money_data[ctx.author.id] = money_data.get(ctx.author.id, 0) + reward
        await ctx.send(f"✅ You caught the {creature} and earned {reward} coins!")
    except asyncio.TimeoutError:
        await ctx.send(f"❌ The {creature} escaped!")

# ----------------- TRIVIA MINI-GAME -----------------
trivia_questions = [
    {"q": "What is the capital of France?", "a": "paris"},
    {"q": "Who wrote Hamlet?", "a": "shakespeare"},
    {"q": "2+2*2=?", "a": "6"},
    {"q": "Largest ocean on Earth?", "a": "pacific"},
    {"q": "10 squared?", "a": "100"},
]

@bot.command()
async def trivia(ctx):
    """Answer a trivia question to earn coins."""
    question = random.choice(trivia_questions)
    await ctx.send(f"❓ Trivia: {question['q']}")

    def check(m):
        return m.author == ctx.author

    try:
        msg = await bot.wait_for('message', check=check, timeout=20)
        if msg.content.lower() == question['a']:
            reward = random.randint(50, 150)
            money_data[ctx.author.id] = money_data.get(ctx.author.id, 0) + reward
            await ctx.send(f"✅ Correct! You earned {reward} coins.")
        else:
            await ctx.send("❌ Incorrect answer!")
    except asyncio.TimeoutError:
        await ctx.send("⏱ Time's up!")

# ----------------- LOOT / QUEST -----------------
@bot.command()
async def loot(ctx):
    """Open a crate and get random items."""
    items = ["Sword", "Shield", "Potion", "Gold", "Gem"]
    found = random.choice(items)
    await ctx.send(f"📦 You opened a crate and got: **{found}**!")

@bot.command()
async def quest(ctx):
    """Complete a quest to earn coins."""
    reward = random.randint(50, 150)
    money_data[ctx.author.id] = money_data.get(ctx.author.id, 0) + reward
    await ctx.send(f"🗡 You completed a quest and got {reward} coins!")
    
# ---------------- Part 7: Levels, Autorole, Invite Leaderboard, DM Utilities & Bot Run ----------------

# ----------------- LEVEL / XP SYSTEM -----------------
xp_data = {}
level_data = {}

def add_xp(user_id: int):
    """Add XP and handle level-ups with exponential growth."""
    xp_data[user_id] = xp_data.get(user_id, 0) + random.randint(5, 15)
    level = level_data.get(user_id, 0)
    required_xp = int(100 * (1.5 ** level))
    if xp_data[user_id] >= required_xp:
        level_data[user_id] = level + 1
        xp_data[user_id] -= required_xp
        return True, level + 1
    return False, level

@bot.command()
async def level(ctx, member: discord.Member = None):
    """Check the level and XP of a member."""
    member = member or ctx.author
    lvl = level_data.get(member.id, 0)
    xp = xp_data.get(member.id, 0)
    required = int(100 * (1.5 ** lvl))
    await ctx.send(f"🏆 {member} is level **{lvl}** with **{xp}/{required} XP**.")

@bot.command()
async def rank(ctx, member: discord.Member = None):
    """Check rank of a member based on XP."""
    member = member or ctx.author
    sorted_users = sorted(level_data.items(), key=lambda x: (x[1], xp_data.get(x[0],0)), reverse=True)
    for i, (uid, _) in enumerate(sorted_users, start=1):
        if uid == member.id:
            await ctx.send(f"📊 {member} is rank **{i}** in the server!")
            return
    await ctx.send("❌ Member not found in rank list.")

# ----------------- AUTOROLE -----------------
autorole_id = None

@bot.command()
@commands.has_permissions(administrator=True)
async def set_autorole(ctx, role: discord.Role):
    """Set a role that new members get automatically."""
    global autorole_id
    autorole_id = role.id
    await ctx.send(f"✅ Autorole set to **{role.name}**.")

@bot.event
async def on_member_join(member: discord.Member):
    """Give autorole and welcome new members."""
    if autorole_id:
        role = member.guild.get_role(autorole_id)
        if role:
            try:
                await member.add_roles(role)
                await member.send(f"Welcome! You were given the {role.name} role automatically.")
            except discord.Forbidden:
                print(f"Cannot assign autorole to {member}.")

# ----------------- DM ALL UTILITY -----------------
@bot.command()
@commands.has_permissions(administrator=True)
async def dmall(ctx, *, message):
    """DM all members in the server (non-bots)."""
    success = 0
    for member in ctx.guild.members:
        if not member.bot:
            try:
                await member.send(message)
                success += 1
            except:
                continue
    await ctx.send(f"✅ DMed {success} members.")

# ----------------- TIMEOUT / MUTING -----------------
@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int, *, reason=None):
    """Timeout a member for X minutes."""
    try:
        until = datetime.utcnow() + timedelta(minutes=minutes)
        await member.timeout(until, reason=reason)
        await ctx.send(f"⏱ {member} has been timed out for {minutes} minutes. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send("❌ Cannot timeout this member.")

# ----------------- SCHEDULED MESSAGES -----------------
scheduled_messages = []

@bot.command()
async def schedule(ctx, minutes:int, *, message):
    """Schedule a message in X minutes."""
    send_time = datetime.utcnow() + timedelta(minutes=minutes)
    scheduled_messages.append({"channel": ctx.channel, "message": message, "time": send_time})
    await ctx.send(f"📅 Message scheduled in {minutes} minutes.")

@tasks.loop(seconds=10)
async def check_scheduled_messages():
    """Send scheduled messages when the time is reached."""
    now = datetime.utcnow()
    for msg in scheduled_messages[:]:
        if now >= msg["time"]:
            await msg["channel"].send(msg["message"])
            scheduled_messages.remove(msg)

# ----------------- PING COMMAND -----------------
@bot.command()
async def ping(ctx):
    """Check bot latency."""
    await ctx.send(f"🏓 Pong! Latency: {round(bot.latency * 1000)}ms")

# ----------------- DISABLE / ENABLE USERS -----------------
@bot.command()
async def disablebot(ctx, member: discord.Member):
    """Disable a user from using bot commands."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You do not have permission.")
        return
    disabled_users.add(member.id)
    await ctx.send(f"🚫 {member} has been disabled from using the bot.")

@bot.command()
async def enablebot(ctx, member: discord.Member):
    """Enable a previously disabled user."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You do not have permission.")
        return
    disabled_users.discard(member.id)
    await ctx.send(f"✅ {member} can now use bot commands again.")

# ----------------- FINAL BOT RUN -----------------
@bot.event
async def on_ready():
    print(f"🚀 Slayer-Bot online as {bot.user}")
    if not check_scheduled_messages.is_running():
        check_scheduled_messages.start()
    if not check_giveaways.is_running():
        check_giveaways.start()

if __name__ == "__main__":
    print("🚀 Starting Slayer-Bot...")
    try:
        bot.run(os.getenv("TOKEN") or "YOUR_BOT_TOKEN_HERE")
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
