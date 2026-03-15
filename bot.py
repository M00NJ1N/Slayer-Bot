# ----------------- Slayer-Bot Clean Unified Version -----------------
import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import random
from datetime import datetime, timedelta

# ----------------- CONFIG -----------------
TOKEN = os.getenv("TOKEN") or "YOUR_BOT_TOKEN_HERE"
COMMAND_PREFIX = "!"
OWNER_ID = 1169273992289456341
CO_OWNER_ID = 958273785037983754
DEFAULT_ROLE_NAME = "Member"
LOG_CHANNEL_NAME = "bot-logs"
WELCOME_CHANNEL_NAME = "arrivals"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)
tree = bot.tree  # For slash commands

# ----------------- DATABASES -----------------
# Economy
money_data = {}
daily_claimed = {}

# XP / Levels
xp_data = {}
level_data = {}

# Moderation
warn_data = {}
disabled_users = set()

# Invites
invite_cache = {}  # guild_id -> {code: uses}
invite_data = {}   # user_id -> total invites

# Autorole
autorole_id = None

# Giveaways
giveaways = {}

# Scheduled messages
scheduled_messages = []

# Mini-games
reaction_games = {}
blackjack_games = {}

# ----------------- HELPER FUNCTIONS -----------------
def is_owner(user):
    return user.id == OWNER_ID

def is_owner_or_co(user):
    return user.id in [OWNER_ID, CO_OWNER_ID]

def add_xp(user_id):
    """Add XP and check for level up (exponential growth)."""
    xp_data[user_id] = xp_data.get(user_id, 0) + random.randint(5, 15)
    lvl = level_data.get(user_id, 0)
    required_xp = int(100 * (1.5 ** lvl))
    if xp_data[user_id] >= required_xp:
        level_data[user_id] = lvl + 1
        xp_data[user_id] -= required_xp
        return True, lvl + 1
    return False, lvl

async def get_log_channel(guild: discord.Guild):
    channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if not channel:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        channel = await guild.create_text_channel(LOG_CHANNEL_NAME, overwrites=overwrites)
    return channel

async def log_action(guild, message):
    channel = await get_log_channel(guild)
    await channel.send(message)

# ----------------- EVENTS -----------------
@bot.event
async def on_ready():
    print(f"🚀 Bot online as {bot.user}")
    if not check_scheduled_messages.is_running():
        check_scheduled_messages.start()
    if not check_giveaways.is_running():
        check_giveaways.start()
    for guild in bot.guilds:
        invite_cache[guild.id] = {i.code: i.uses for i in await guild.invites()}
    try:
        await tree.sync()
    except Exception as e:
        print(f"❌ Slash command sync error: {e}")

@bot.event
async def on_member_join(member):
    # Autorole
    if autorole_id:
        role = member.guild.get_role(autorole_id)
        if role:
            try:
                await member.add_roles(role)
                await member.send(f"✅ You were automatically given the {role.name} role!")
            except discord.Forbidden:
                print(f"Cannot assign autorole to {member}.")

    # Welcome message & invite tracking
    guild_invites_after = await member.guild.invites()
    used_invite = None
    before_cache = invite_cache.get(member.guild.id, {})
    for invite in guild_invites_after:
        if invite.uses > before_cache.get(invite.code, 0):
            used_invite = invite
            break
    inviter = used_invite.inviter if used_invite else None
    arrivals_channel = discord.utils.get(member.guild.text_channels, name=WELCOME_CHANNEL_NAME)
    if arrivals_channel:
        msg = f"👋 Welcome {member.mention}!\nUsername: {member}\n"
        msg += f"Invited by: {inviter.mention}" if inviter else "Invite not tracked."
        await arrivals_channel.send(msg)
    if inviter:
        invite_data[inviter.id] = invite_data.get(inviter.id, 0) + 1

    # Update invite cache
    invite_cache[member.guild.id] = {i.code: i.uses for i in guild_invites_after}

    # Initialize economy and XP
    money_data[member.id] = 100
    daily_claimed[member.id] = datetime.utcnow() - timedelta(days=1)
    xp_data[member.id] = 0
    level_data[member.id] = 0
    warn_data[member.id] = 0

@bot.event
async def on_message(message):
    if message.author.bot or message.author.id in disabled_users:
        return
    leveled_up, new_level = add_xp(message.author.id)
    if leveled_up:
        await message.channel.send(f"🎉 {message.author.mention} leveled up to **{new_level}**!")
    await bot.process_commands(message)

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    # Giveaways
    for data in giveaways.values():
        if data["message"].id == reaction.message.id and str(reaction.emoji) == "🎉":
            data["entries"].add(user)
            
# ---------------- Part 2: Owner/Co-owner, Economy, XP & Fun -----------------

# ----------------- OWNER / CO-OWNER COMMANDS -----------------
@bot.command()
async def shutdown(ctx):
    """Shutdown the bot (Owner/Co-owner only)."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You do not have permission to shutdown the bot.")
        return
    await ctx.send("⚡ Shutting down...")
    await log_action(ctx.guild, f"{ctx.author} shut down the bot.")
    await bot.close()

@bot.command()
async def disable_user(ctx, member: discord.Member):
    """Disable a user from using bot commands."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You cannot disable users.")
        return
    disabled_users.add(member.id)
    await ctx.send(f"🚫 {member.mention} is now disabled from bot commands.")
    await log_action(ctx.guild, f"{ctx.author} disabled {member}.")

@bot.command()
async def enable_user(ctx, member: discord.Member):
    """Enable a previously disabled user."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You cannot enable users.")
        return
    disabled_users.discard(member.id)
    await ctx.send(f"✅ {member.mention} can now use bot commands.")
    await log_action(ctx.guild, f"{ctx.author} enabled {member}.")

@bot.command()
async def broadcast(ctx, *, message):
    """Send a broadcast message to all servers (Owner/Co-owner only)."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You cannot broadcast messages.")
        return
    for guild in bot.guilds:
        try:
            channel = await get_log_channel(guild)
            await channel.send(f"📢 Broadcast from {ctx.author.mention}: {message}")
        except:
            continue
    await ctx.send("✅ Broadcast sent to all servers.")
    await log_action(ctx.guild, f"{ctx.author} broadcasted a message.")

@bot.command()
async def autorole(ctx, role: discord.Role):
    """Set autorole for new members (Owner/Co-owner only)."""
    global autorole_id
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You cannot set autorole.")
        return
    autorole_id = role.id
    await ctx.send(f"✅ Autorole set to {role.name}.")
    await log_action(ctx.guild, f"{ctx.author} set autorole to {role.name}.")

@bot.command()
async def dmall(ctx, *, message):
    """Send DM to all non-bot members (Owner/Co-owner only)."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You cannot DM all users.")
        return
    success = 0
    for member in ctx.guild.members:
        if not member.bot:
            try:
                await member.send(message)
                success += 1
            except:
                continue
    await ctx.send(f"✅ Sent DM to {success} members.")
    await log_action(ctx.guild, f"{ctx.author} DM’d {success} members.")

# ----------------- ECONOMY COMMANDS -----------------
@bot.command()
async def balance(ctx, member: discord.Member = None):
    """Check your or another user's balance."""
    member = member or ctx.author
    bal = money_data.get(member.id, 0)
    await ctx.send(f"💰 {member.mention} has {bal} coins.")

@bot.command()
async def pay(ctx, member: discord.Member, amount: int):
    """Pay coins to another member."""
    if money_data.get(ctx.author.id, 0) < amount:
        await ctx.send("❌ You don't have enough coins.")
        return
    money_data[ctx.author.id] -= amount
    money_data[member.id] = money_data.get(member.id, 0) + amount
    await ctx.send(f"✅ {ctx.author.mention} paid {member.mention} {amount} coins.")

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
    await ctx.send(f"💵 You received {coins} coins!")

@bot.command()
async def setbalance(ctx, member: discord.Member, amount: int):
    """Set a user's balance (Owner/Co-owner only)."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You do not have permission.")
        return
    money_data[member.id] = amount
    await ctx.send(f"✅ {member.mention}'s balance set to {amount} coins.")

@bot.command()
async def leaderboard(ctx, top: int = 10):
    """Show top coin holders in the server."""
    sorted_balances = sorted(money_data.items(), key=lambda x: x[1], reverse=True)[:top]
    embed = discord.Embed(title=f"🏆 Top {top} Richest Users", color=discord.Color.gold())
    for i, (uid, bal) in enumerate(sorted_balances, 1):
        member = ctx.guild.get_member(uid)
        if member:
            embed.add_field(name=f"{i}. {member}", value=f"{bal} coins", inline=False)
    await ctx.send(embed=embed)

# ----------------- XP & LEVEL COMMANDS -----------------
@bot.command()
async def level(ctx, member: discord.Member = None):
    """Check your or a member's level and XP."""
    member = member or ctx.author
    lvl = level_data.get(member.id, 0)
    xp = xp_data.get(member.id, 0)
    required = int(100 * (1.5 ** lvl))
    await ctx.send(f"🏆 {member.mention} is level **{lvl}** with **{xp}/{required} XP**.")

@bot.command()
async def rank(ctx, member: discord.Member = None):
    """Check server rank of a member based on level."""
    member = member or ctx.author
    sorted_users = sorted(level_data.items(), key=lambda x: (x[1], xp_data.get(x[0], 0)), reverse=True)
    for i, (uid, _) in enumerate(sorted_users, start=1):
        if uid == member.id:
            await ctx.send(f"📊 {member.mention} is rank **{i}** in the server!")
            return
    await ctx.send("❌ Member not found in rank list.")

# ----------------- FUN COMMANDS -----------------
@bot.command()
async def coinflip(ctx):
    """Flip a coin."""
    result = random.choice(["Heads", "Tails"])
    await ctx.send(f"🪙 {ctx.author.mention} flipped {result}!")

@bot.command()
async def roll(ctx, sides: int = 6):
    """Roll a dice with N sides."""
    result = random.randint(1, sides)
    await ctx.send(f"🎲 {ctx.author.mention} rolled a {sides}-sided dice: {result}")

@bot.command()
async def hug(ctx, member: discord.Member = None):
    """Hug a member."""
    member = member or ctx.author
    await ctx.send(f"{ctx.author.mention} hugs {member.mention} 🤗")

@bot.command()
async def slap(ctx, member: discord.Member = None):
    """Slap a member."""
    member = member or ctx.author
    await ctx.send(f"{ctx.author.mention} slaps {member.mention} 👋")

@bot.command()
async def say(ctx, *, text):
    """Make the bot repeat text."""
    await ctx.send(f"🗣 {text}")

@bot.command()
async def avatar(ctx, member: discord.Member = None):
    """Show a member's avatar."""
    member = member or ctx.author
    await ctx.send(member.display_avatar.url)

# ----------------- SCHEDULED MESSAGES -----------------
@bot.command()
async def schedule(ctx, minutes: int, *, message):
    """Schedule a message to send after X minutes."""
    send_time = datetime.utcnow() + timedelta(minutes=minutes)
    scheduled_messages.append({"channel": ctx.channel, "message": message, "time": send_time})
    await ctx.send(f"⏳ Message scheduled in {minutes} minutes.")

@tasks.loop(seconds=10)
async def check_scheduled_messages():
    now = datetime.utcnow()
    for msg in scheduled_messages[:]:
        if now >= msg["time"]:
            await msg["channel"].send(msg["message"])
            scheduled_messages.remove(msg)
            
# ---------------- Part 3: Advanced Giveaways, Mini-Games & Events -----------------

# ----------------- ADVANCED GIVEAWAYS -----------------
giveaways = {}  # guild_id -> giveaway data

@bot.command()
@commands.has_permissions(administrator=True)
async def giveaway(ctx, duration: int, *, prize: str):
    """Start an advanced giveaway in the current channel."""
    if ctx.guild.id in giveaways:
        await ctx.send("❌ A giveaway is already running!")
        return
    end_time = datetime.utcnow() + timedelta(minutes=duration)
    msg = await ctx.send(f"🎉 Giveaway for **{prize}**! React with 🎉 to enter! Ends in {duration} minutes.")
    await msg.add_reaction("🎉")
    giveaways[ctx.guild.id] = {"channel": ctx.channel, "message": msg, "prize": prize, "end": end_time, "entries": set()}

@tasks.loop(seconds=30)
async def check_giveaways():
    """Check all giveaways and announce winners."""
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

# ----------------- REACTION BASED MINI-GAMES -----------------
reaction_games = {}

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

@bot.command()
async def catch(ctx):
    """Catch a wild creature to earn coins."""
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

# ----------------- TRIVIA -----------------
trivia_questions = [
    {"q": "What is the capital of France?", "a": "paris"},
    {"q": "Who wrote Hamlet?", "a": "shakespeare"},
    {"q": "2+2*2=?", "a": "6"},
    {"q": "What is the largest ocean on Earth?", "a": "pacific"},
    {"q": "What is 10 squared?", "a": "100"},
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
    """Open a crate and get a random item."""
    items = ["Sword", "Shield", "Potion", "Gold", "Gem"]
    found = random.choice(items)
    await ctx.send(f"📦 You opened a crate and got: **{found}**!")

@bot.command()
async def quest(ctx):
    """Complete a quest to earn coins."""
    reward = random.randint(50, 150)
    money_data[ctx.author.id] = money_data.get(ctx.author.id, 0) + reward
    await ctx.send(f"🗡 You completed a quest and got {reward} coins!")

# ----------------- GIVEAWAY REACTION HANDLER -----------------
@bot.event
async def on_reaction_add(reaction, user):
    """Handle reactions for giveaways and reaction mini-games."""
    if user.bot:
        return
    # Track giveaway entries
    for data in giveaways.values():
        if data["message"].id == reaction.message.id and reaction.emoji == "🎉":
            data["entries"].add(user)
            
# ---------------- Part 4: Blackjack, XP/Level System, Scheduled Messages -----------------

# ----------------- BLACKJACK MINI-GAME -----------------
blackjack_games = {}

@bot.command()
async def blackjack(ctx, wager: int = 0):
    """Start a blackjack game."""
    if ctx.author.id in blackjack_games:
        await ctx.send("❌ You are already in a blackjack game!")
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
        await ctx.send("❌ You are not in a blackjack game!")
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
    """End your turn and let the dealer play."""
    game = blackjack_games.get(ctx.author.id)
    if not game:
        await ctx.send("❌ You are not in a blackjack game!")
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

# ----------------- XP / LEVEL SYSTEM -----------------
xp_data = {}
level_data = {}

def add_xp(user_id):
    """Add XP and level up if threshold reached. Harder each level."""
    xp_gain = random.randint(5, 15)
    xp_data[user_id] = xp_data.get(user_id, 0) + xp_gain
    level = level_data.get(user_id, 0)
    required_xp = int(100 * (1.5 ** level))  # exponential growth
    if xp_data[user_id] >= required_xp:
        level_data[user_id] = level + 1
        xp_data[user_id] -= required_xp
        return True, level + 1
    return False, level

@bot.command()
async def level(ctx, member: discord.Member = None):
    """Check level and XP of a member."""
    member = member or ctx.author
    lvl = level_data.get(member.id, 0)
    xp = xp_data.get(member.id, 0)
    required = int(100 * (1.5 ** lvl))
    await ctx.send(f"🏆 {member} is level **{lvl}** with **{xp}/{required} XP**.")

@bot.command()
async def rank(ctx, member: discord.Member = None):
    """Check a member's rank based on level and XP."""
    member = member or ctx.author
    sorted_users = sorted(level_data.items(), key=lambda x: (x[1], xp_data.get(x[0],0)), reverse=True)
    for i, (uid, _) in enumerate(sorted_users, start=1):
        if uid == member.id:
            await ctx.send(f"📊 {member} is rank **{i}** in the server!")
            return
    await ctx.send("❌ Member not found in rank list.")

# ----------------- SCHEDULED MESSAGES -----------------
scheduled_messages = []

@bot.command()
async def schedule(ctx, minutes: int, *, message):
    """Schedule a message to be sent after X minutes."""
    send_time = datetime.utcnow() + timedelta(minutes=minutes)
    scheduled_messages.append({"channel": ctx.channel, "message": message, "time": send_time})
    await ctx.send(f"📅 Message scheduled in {minutes} minutes.")

@tasks.loop(seconds=10)
async def check_scheduled_messages():
    """Check and send scheduled messages."""
    now = datetime.utcnow()
    for msg in scheduled_messages[:]:
        if now >= msg["time"]:
            await msg["channel"].send(msg["message"])
            scheduled_messages.remove(msg)

# ----------------- ON_MESSAGE EVENT (XP + Commands) -----------------
@bot.event
async def on_message(message):
    """Add XP for messages and process commands."""
    if message.author.bot or message.author.id in disabled_users:
        return
    leveled_up, new_level = add_xp(message.author.id)
    if leveled_up:
        await message.channel.send(f"🎉 {message.author.mention} leveled up to **{new_level}**!")
    await bot.process_commands(message)
    
# ---------------- Part 5: Economy, Mini-Games & Advanced Giveaways -----------------

# ----------------- ECONOMY COMMANDS -----------------
money_data = {}
daily_claimed = {}

@bot.command()
async def balance(ctx, member: discord.Member = None):
    """Check a member's coin balance."""
    member = member or ctx.author
    bal = money_data.get(member.id, 0)
    await ctx.send(f"💰 {member.mention} has {bal} coins.")

@bot.command()
async def pay(ctx, member: discord.Member, amount: int):
    """Pay coins to another member."""
    if money_data.get(ctx.author.id, 0) < amount:
        await ctx.send("❌ Not enough coins!")
        return
    money_data[ctx.author.id] -= amount
    money_data[member.id] = money_data.get(member.id, 0) + amount
    await ctx.send(f"✅ {ctx.author.mention} paid {member.mention} {amount} coins.")

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
    await ctx.send(f"💵 You collected {coins} coins today!")

@bot.command()
async def leaderboard(ctx, top: int = 10):
    """Show top coin holders in the server."""
    sorted_balances = sorted(money_data.items(), key=lambda x: x[1], reverse=True)[:top]
    embed = discord.Embed(title=f"🏆 Top {top} Richest Users", color=discord.Color.gold())
    for i, (uid, bal) in enumerate(sorted_balances, 1):
        member = ctx.guild.get_member(uid)
        if member:
            embed.add_field(name=f"{i}. {member}", value=f"{bal} coins", inline=False)
    await ctx.send(embed=embed)

# ----------------- MINI-GAMES -----------------
import asyncio

@bot.command()
async def loot(ctx):
    """Open a crate and get a random item."""
    items = ["Sword", "Shield", "Potion", "Gold", "Gem"]
    found = random.choice(items)
    await ctx.send(f"📦 You opened a crate and got: **{found}**!")

@bot.command()
async def quest(ctx):
    """Complete a quest and earn coins."""
    reward = random.randint(50, 150)
    money_data[ctx.author.id] = money_data.get(ctx.author.id, 0) + reward
    await ctx.send(f"🗡 You completed a quest and got {reward} coins!")

@bot.command()
async def trivia(ctx):
    """Answer a trivia question to earn coins."""
    trivia_questions = [
        {"q": "What is the capital of France?", "a": "paris"},
        {"q": "Who wrote Hamlet?", "a": "shakespeare"},
        {"q": "2+2*2=?", "a": "6"},
        {"q": "What is the largest ocean on Earth?", "a": "pacific"},
        {"q": "What is 10 squared?", "a": "100"},
    ]
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

@bot.command()
async def catch(ctx):
    """Catch a wild creature to earn coins."""
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

# ----------------- REACTION GAMES (RPS) -----------------
reaction_games = {}

@bot.command()
async def rps(ctx, opponent: discord.Member):
    """Play Rock-Paper-Scissors with another user."""
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
    """Handle reactions for giveaways and RPS."""
    if user.bot:
        return
    # RPS
    for game in reaction_games.values():
        if reaction.message.id == game["message"].id:
            game["choices"][user.id] = reaction.emoji
            if len(game["choices"]) == 2:
                p1, p2 = list(game["choices"].keys())
                c1, c2 = game["choices"][p1], game["choices"][p2]
                winner_text = None
                if c1 == c2:
                    winner_text = "It's a draw!"
                elif (c1=="✊" and c2=="✌️") or (c1=="✋" and c2=="✊") or (c1=="✌️" and c2=="✋"):
                    winner_text = f"{bot.get_user(p1).mention} wins!"
                else:
                    winner_text = f"{bot.get_user(p2).mention} wins!"
                await reaction.message.channel.send(winner_text)
                for uid in [p1, p2]:
                    reaction_games.pop(uid, None)
                    
# ---------------- Part 6: Invite Tracking, Autorole, DM-All, and Moderation Utilities -----------------

# ----------------- AUTOROLE -----------------
autorole_id = None

@bot.command()
@commands.has_permissions(administrator=True)
async def set_autorole(ctx, role: discord.Role):
    """Set a role to be automatically assigned to new members."""
    global autorole_id
    autorole_id = role.id
    await ctx.send(f"✅ Autorole set to **{role.name}**.")

# ----------------- INVITE TRACKING -----------------
invite_cache = {}
invite_data = {}

@bot.event
async def on_ready():
    """Cache all guild invites on bot ready."""
    for guild in bot.guilds:
        invites = await guild.invites()
        invite_cache[guild.id] = {i.code: i.uses for i in invites}

@bot.event
async def on_member_join(member: discord.Member):
    """Handle autorole assignment and invite tracking on join."""
    # Autorole
    if autorole_id:
        role = member.guild.get_role(autorole_id)
        if role:
            try:
                await member.add_roles(role)
                await member.send(f"Welcome! You were given the {role.name} role automatically.")
            except discord.Forbidden:
                print(f"Cannot assign autorole to {member}.")

    # Invite tracking
    guild_invites_before = invite_cache.get(member.guild.id, {})
    guild_invites_after = await member.guild.invites()
    used_invite = None
    for invite in guild_invites_after:
        if invite.uses > guild_invites_before.get(invite.code, 0):
            used_invite = invite
            break
    inviter = used_invite.inviter if used_invite else None
    if inviter:
        invite_data[inviter.id] = invite_data.get(inviter.id, 0) + 1

    # Welcome message
    arrivals_channel = discord.utils.get(member.guild.text_channels, name="arrivals")
    if arrivals_channel:
        inviter_name = inviter.mention if inviter else "Unknown"
        await arrivals_channel.send(
            f"👋 Welcome {member.mention}!\n"
            f"Joined: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Invited by: {inviter_name}"
        )

    # Update invite cache
    invite_cache[member.guild.id] = {i.code: i.uses for i in guild_invites_after}

# ----------------- INVITE LEADERBOARD -----------------
@bot.command()
async def invite_leaderboard(ctx, top:int=10):
    """Show the top inviters in the server."""
    sorted_invites = sorted(invite_data.items(), key=lambda x: x[1], reverse=True)[:top]
    embed = discord.Embed(title=f"Top {top} Inviters", color=discord.Color.purple())
    for i, (uid, count) in enumerate(sorted_invites, start=1):
        member = ctx.guild.get_member(uid)
        if member:
            embed.add_field(name=f"{i}. {member}", value=f"{count} invites", inline=False)
    await ctx.send(embed=embed)

# ----------------- DM-ALL COMMAND -----------------
@bot.command()
@commands.has_permissions(administrator=True)
async def dmall(ctx, *, message):
    """Send a DM to all non-bot members of the server."""
    success = 0
    for member in ctx.guild.members:
        if not member.bot:
            try:
                await member.send(message)
                success += 1
            except:
                continue
    await ctx.send(f"✅ DMed {success} members.")

# ----------------- TIMEOUT / MUTE COMMAND -----------------
@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int, *, reason=None):
    """Put a member in timeout for a number of minutes."""
    try:
        until = datetime.utcnow() + timedelta(minutes=minutes)
        await member.timeout(until, reason=reason)
        await ctx.send(f"⏱ {member.mention} has been timed out for {minutes} minutes. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send("❌ Cannot timeout this member.")

# ----------------- CLEANUP / PURGE -----------------
@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, limit:int=50):
    """Delete the last N messages in a channel."""
    deleted = await ctx.channel.purge(limit=limit)
    await ctx.send(f"🧹 Deleted {len(deleted)} messages.", delete_after=5)

# ----------------- SHUTDOWN / DISABLE USER -----------------
disabled_users = set()

@bot.command()
async def shutdown(ctx):
    """Shut down the bot (Owner / Co-owner only)."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You do not have permission.")
        return
    await ctx.send("⚡ Shutting down...")
    await bot.close()

@bot.command()
async def disable_user(ctx, member: discord.Member):
    """Disable a user from using bot commands."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You do not have permission.")
        return
    disabled_users.add(member.id)
    await ctx.send(f"🚫 {member} has been disabled from using the bot.")

@bot.command()
async def enable_user(ctx, member: discord.Member):
    """Enable a previously disabled user."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("❌ You do not have permission.")
        return
    disabled_users.discard(member.id)
    await ctx.send(f"✅ {member} can now use bot commands again.")

# ----------------- PING COMMAND -----------------
@bot.command()
async def ping(ctx):
    """Check bot latency."""
    await ctx.send(f"🏓 Pong! Latency: {round(bot.latency * 1000)}ms")
    
# ---------------- Part 7: XP / Levels, On-Message XP, and Bot Run -----------------

# ----------------- LEVELS / XP -----------------
level_data = {}
xp_data = {}

def add_xp(user_id):
    """Add XP to a user and handle level-ups (harder with higher levels)."""
    xp_gain = random.randint(5, 15)
    xp_data[user_id] = xp_data.get(user_id, 0) + xp_gain
    level = level_data.get(user_id, 0)
    required_xp = int(100 * (1.5 ** level))  # exponential XP curve
    if xp_data[user_id] >= required_xp:
        xp_data[user_id] -= required_xp
        level_data[user_id] = level + 1
        return True, level + 1
    return False, level

@bot.command()
async def level(ctx, member: discord.Member = None):
    """Check a member's level and current XP."""
    member = member or ctx.author
    lvl = level_data.get(member.id, 0)
    xp = xp_data.get(member.id, 0)
    required = int(100 * (1.5 ** lvl))
    await ctx.send(f"🏆 {member} is level **{lvl}** with **{xp}/{required} XP**.")

@bot.command()
async def rank(ctx, member: discord.Member = None):
    """Check the rank of a member based on XP and level."""
    member = member or ctx.author
    sorted_users = sorted(level_data.items(), key=lambda x: (x[1], xp_data.get(x[0],0)), reverse=True)
    for i, (uid, _) in enumerate(sorted_users, start=1):
        if uid == member.id:
            await ctx.send(f"📊 {member} is rank **{i}** in the server!")
            return
    await ctx.send("❌ Member not found in rank list.")

# ----------------- ON_MESSAGE XP -----------------
@bot.event
async def on_message(message):
    """Award XP on message and process commands."""
    if message.author.bot or message.author.id in disabled_users:
        return
    leveled_up, new_level = add_xp(message.author.id)
    if leveled_up:
        await message.channel.send(f"🎉 {message.author.mention} leveled up to **{new_level}**!")
    await bot.process_commands(message)

# ----------------- FINAL BOT RUN -----------------
if __name__ == "__main__":
    print("🚀 Starting Slayer-Bot...")
    try:
        bot.run(os.getenv("TOKEN") or "YOUR_BOT_TOKEN_HERE")
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
