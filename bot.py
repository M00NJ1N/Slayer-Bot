import os
import discord
from discord.ext import commands, tasks
import random
from datetime import datetime, timedelta
warn_data = {}

# ----------------- CONFIG -----------------
TOKEN = os.getenv("TOKEN") or "YOUR_TOKEN_HERE"
COMMAND_PREFIX = "!"
DEFAULT_ROLE_NAME = "Member"
OWNER_ID = 1169273992289456341
CO_OWNER_ID = 958273785037983754

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# ----------------- DATABASE SIMULATION -----------------
money_data = {}
daily_claimed = {}
blackjack_games = {}
disabled_users = set()  # <-- Track disabled users

# ----------------- HELPERS -----------------
def is_owner(ctx):
    return ctx.author.id == OWNER_ID

def is_owner_or_co(ctx):
    return ctx.author.id in [OWNER_ID, CO_OWNER_ID]

# ----------------- EVENTS -----------------
@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    if not check_scheduled_messages.is_running():
        check_scheduled_messages.start()
        
# ----------------- OWNER ONLY COMMANDS -----------------
@bot.command()
@commands.check(is_owner)
async def ping(ctx):
    await ctx.send(f"Pong! {round(bot.latency*1000)}ms")

@bot.command()
@commands.check(is_owner)
async def lock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(f"{channel.mention} has been locked 🔒")

@bot.command()
@commands.check(is_owner)
async def unlock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(f"{channel.mention} has been unlocked 🔓")

# ----------------- SHUTDOWN / DISABLE -----------------
@bot.command()
@commands.check(is_owner)
async def shutdown(ctx):
    """Shuts down the bot (owner only)."""
    await ctx.send("Shutting down... Bye! 👋")
    await bot.close()

@bot.command()
@commands.check(is_owner)
async def disable_user(ctx, user: discord.Member):
    """Prevents a user from using commands."""
    disabled_users.add(user.id)
    await ctx.send(f"{user} has been disabled from using bot commands.")

@bot.command()
@commands.check(is_owner)
async def enable_user(ctx, user: discord.Member):
    """Re-enables a previously disabled user."""
    disabled_users.discard(user.id)
    await ctx.send(f"{user} can now use bot commands again.")

# Global check for disabled users
@bot.check
async def global_disabled_check(ctx):
    if ctx.author.id in disabled_users:
        await ctx.send("You are temporarily disabled from using the bot.")
        return False
    return True

# ----------------- CLIP COMMAND -----------------
@bot.command()
async def clip(ctx, message_id: int, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    try:
        message = await channel.fetch_message(message_id)
        content = message.content
        author = message.author
        timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
        await ctx.author.send(f"Clipped message from {author} at {timestamp}:\n{content}")
        await ctx.send("Message clipped to your DMs.")
    except:
        await ctx.send("Message not found!")

# ----------------- BLACKJACK -----------------
@bot.command()
async def blackjack(ctx, wager: int = 0):
    if ctx.author.id in blackjack_games:
        await ctx.send("You are already in a blackjack game!")
        return
    deck = [2,3,4,5,6,7,8,9,10,10,10,10,11]*4
    random.shuffle(deck)
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]
    blackjack_games[ctx.author.id] = {"player": player_hand, "dealer": dealer_hand, "deck": deck, "wager": wager}
    await ctx.send(f"Blackjack started! Your hand: {player_hand}, dealer shows: {dealer_hand[0]}")

@bot.command()
async def hit(ctx):
    game = blackjack_games.get(ctx.author.id)
    if not game:
        await ctx.send("You are not in a blackjack game!")
        return
    game["player"].append(game["deck"].pop())
    total = sum(game["player"])
    await ctx.send(f"Your hand: {game['player']}, total: {total}")
    if total > 21:
        await ctx.send("Bust! You lose.")
        del blackjack_games[ctx.author.id]
    elif total == 21:
        await ctx.send("Blackjack! You win!")
        del blackjack_games[ctx.author.id]

@bot.command()
async def stand(ctx):
    game = blackjack_games.get(ctx.author.id)
    if not game:
        await ctx.send("You are not in a blackjack game!")
        return
    deck = game["deck"]
    dealer_total = sum(game["dealer"])
    player_total = sum(game["player"])
    while dealer_total < 17:
        game["dealer"].append(deck.pop())
        dealer_total = sum(game["dealer"])
    await ctx.send(f"Dealer hand: {game['dealer']}, total: {dealer_total}")
    if dealer_total > 21 or player_total > dealer_total:
        await ctx.send("You win!")
    elif dealer_total == player_total:
        await ctx.send("Draw!")
    else:
        await ctx.send("You lose!")
    del blackjack_games[ctx.author.id]

# ----------------- MODERATION -----------------
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, days: int = 0, *, reason=None):
    try:
        await member.ban(reason=reason, delete_message_days=days)
        await ctx.send(f"{member} was banned. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send("I do not have permission to ban that member.")

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"{member} was kicked. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send("Cannot kick that member.")

@bot.command()
@commands.has_permissions(administrator=True)
async def warn(ctx, member: discord.Member, *, reason=None):
    if member.id not in warn_data:
        warn_data[member.id] = 0
    warn_data[member.id] += 1
    await ctx.send(f"{member} warned. Total warns: {warn_data[member.id]}")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, limit:int):
    deleted = await ctx.channel.purge(limit=limit)
    await ctx.send(f"Deleted {len(deleted)} messages.", delete_after=5)

# ----------------- ECONOMY -----------------
@bot.command()
async def balance(ctx, member: discord.Member = None):
    member = member or ctx.author
    bal = money_data.get(member.id,0)
    await ctx.send(f"{member} has {bal} coins.")

@bot.command()
async def daily(ctx):
    now = datetime.utcnow()
    last_claimed = daily_claimed.get(ctx.author.id)
    if last_claimed and now - last_claimed < timedelta(hours=24):
        remaining = timedelta(hours=24) - (now - last_claimed)
        await ctx.send(f"You have already claimed daily coins. Come back in {remaining}.")
        return
    coins = random.randint(50,200)
    money_data[ctx.author.id] = money_data.get(ctx.author.id,0)+coins
    daily_claimed[ctx.author.id] = now
    await ctx.send(f"{ctx.author} collected {coins} coins today!")

@bot.command()
async def pay(ctx, member: discord.Member, amount:int):
    if money_data.get(ctx.author.id,0) < amount:
        await ctx.send("Not enough coins!")
        return
    money_data[ctx.author.id] -= amount
    money_data[member.id] = money_data.get(member.id,0)+amount
    await ctx.send(f"{ctx.author} paid {member} {amount} coins.")

@bot.command()
async def setbalance(ctx, member: discord.Member, amount:int):
    if not is_owner_or_co(ctx):
        await ctx.send("You do not have permission.")
        return
    money_data[member.id] = amount
    await ctx.send(f"{member}'s balance set to {amount} coins.")

@bot.command()
async def leaderboard(ctx, top:int=10):
    top_users = sorted(money_data.items(), key=lambda x:x[1], reverse=True)[:top]
    embed = discord.Embed(title=f"Top {top} Richest Users", color=discord.Color.gold())
    for i, (uid, bal) in enumerate(top_users,1):
        member = ctx.guild.get_member(uid)
        if member:
            embed.add_field(name=f"{i}. {member}", value=f"{bal} coins", inline=False)
    await ctx.send(embed=embed)

# ----------------- FUN -----------------
@bot.command()
async def coinflip(ctx):
    result = random.choice(["Heads","Tails"])
    await ctx.send(f"{ctx.author.mention} flipped {result}.")

@bot.command()
async def roll(ctx, sides:int=6):
    result = random.randint(1,sides)
    await ctx.send(f"{ctx.author.mention} rolled a {sides}-sided dice: {result}")

@bot.command()
async def hug(ctx, member: discord.Member=None):
    member = member or ctx.author
    await ctx.send(f"{ctx.author.mention} hugs {member.mention} 🤗")

@bot.command()
async def slap(ctx, member: discord.Member=None):
    member = member or ctx.author
    await ctx.send(f"{ctx.author.mention} slaps {member.mention} 👋")

@bot.command()
async def say(ctx, *, text):
    await ctx.send(text)

@bot.command()
async def avatar(ctx, member: discord.Member=None):
    member = member or ctx.author
    await ctx.send(member.display_avatar.url)

# ----------------- SCHEDULED MESSAGES -----------------
scheduled_messages = []

@bot.command()
async def schedule(ctx, minutes:int, *, message):
    send_time = datetime.utcnow() + timedelta(minutes=minutes)
    scheduled_messages.append({"channel": ctx.channel, "message": message, "time": send_time})
    await ctx.send(f"Message scheduled in {minutes} minutes.")

@tasks.loop(seconds=10)
async def check_scheduled_messages():
    now = datetime.utcnow()
    for msg in scheduled_messages[:]:
        if now >= msg["time"]:
            await msg["channel"].send(msg["message"])
            scheduled_messages.remove(msg)

# ----------------- OWNER ONLY: DM ALL -----------------
@bot.command()
@commands.check(is_owner)
async def dmall(ctx, *, message):
    """DMs all members in the server (Owner only)."""
    success = 0
    failed = 0
    for member in ctx.guild.members:
        if member.bot:
            continue
        try:
            await member.send(message)
            success += 1
        except:
            failed += 1
    await ctx.send(f"Message sent to {success} members. Failed to send to {failed} members.")

# ----------------- MODERATION: TIMEOUT -----------------
@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int, *, reason=None):
    """Timeout a member for X minutes."""
    if member == ctx.author:
        await ctx.send("You cannot timeout yourself!")
        return
    try:
        duration = timedelta(minutes=minutes)
        await member.timeout_for(duration, reason=reason)
        await ctx.send(f"{member.mention} has been timed out for {minutes} minutes. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send("I do not have permission to timeout this member.")
    except Exception as e:
        await ctx.send(f"An error occurred: {e}")

# ----------------- AUTOROLE -----------------
@bot.command()
@commands.check(is_owner)
async def set_autorole(ctx, role: discord.Role):
    """Set the role that will be automatically assigned to new members."""
    global DEFAULT_ROLE_NAME
    DEFAULT_ROLE_NAME = role.name
    await ctx.send(f"Auto-role set to {role.mention}.")

@bot.event
async def on_member_join(member):
    """Assigns the auto-role to new members."""
    role = discord.utils.get(member.guild.roles, name=DEFAULT_ROLE_NAME)
    if role:
        try:
            await member.add_roles(role)
            print(f"{member} was given role {DEFAULT_ROLE_NAME}")
        except discord.Forbidden:
            print(f"Cannot assign role to {member}")

# ----------------- RUN BOT -----------------
bot.run(TOKEN)
