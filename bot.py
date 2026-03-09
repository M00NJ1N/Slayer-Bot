import os
import discord
from discord.ext import commands, tasks
import asyncio
import random
from datetime import datetime, timedelta

# ----------------- CONFIG -----------------
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("No bot token found! Set the TOKEN environment variable!")

COMMAND_PREFIX = "!"
DEFAULT_ROLE_NAME = "Member"
OWNER_ID = 1169273992289456341  # Your Discord ID
CO_OWNER_ID = 958273785037983754  # Your co-owner (limited permissions)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# ----------------- DATABASE SIMULATION -----------------
xp_data = {}
money_data = {}
warn_data = {}
daily_claimed = {}  # track daily commands
logs_channel_name = "bot-logs"

# ----------------- HELPER FUNCTIONS -----------------
async def get_logs_channel(guild):
    channel = discord.utils.get(guild.channels, name=logs_channel_name)
    if not channel:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        channel = await guild.create_text_channel(logs_channel_name, overwrites=overwrites)
    return channel

async def log_action(guild, message):
    channel = await get_logs_channel(guild)
    await channel.send(message)

def is_owner(ctx):
    return ctx.author.id == OWNER_ID

def is_owner_or_co(ctx):
    return ctx.author.id in [OWNER_ID, CO_OWNER_ID]

# ----------------- EVENTS -----------------
@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    if not giveaway_loop.is_running():
        giveaway_loop.start()
    for guild in bot.guilds:
        await get_logs_channel(guild)

@bot.event
async def on_member_join(member):
    role = discord.utils.get(member.guild.roles, name=DEFAULT_ROLE_NAME)
    if role:
        try:
            await member.add_roles(role)
            await log_action(member.guild, f"{member} joined and was given the {DEFAULT_ROLE_NAME} role.")
        except discord.Forbidden:
            print(f"Cannot add role to {member}, missing permissions.")
    xp_data[member.id] = 0
    money_data[member.id] = 100
    warn_data[member.id] = 0

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    xp_data[message.author.id] = xp_data.get(message.author.id, 0) + random.randint(5, 15)
    await log_action(message.guild, f"{message.author} sent a message in {message.channel}: {message.content}")
    await bot.process_commands(message)

# ----------------- MODERATION -----------------
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, days: int = 0, *, reason=None):
    try:
        await member.ban(reason=reason, delete_message_days=days)
        await ctx.send(f"{member} was banned. Reason: {reason}")
        await log_action(ctx.guild, f"{ctx.author} banned {member} for reason: {reason}, deleted {days} days of messages.")
    except discord.Forbidden:
        await ctx.send("I do not have permission to ban that member.")

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"{member} was kicked. Reason: {reason}")
        await log_action(ctx.guild, f"{ctx.author} kicked {member}. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send("I cannot kick that member.")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int, *, reason=None):
    try:
        until = datetime.utcnow() + timedelta(minutes=minutes)
        await member.timeout(until, reason=reason)
        await ctx.send(f"{member} timed out for {minutes} minutes. Reason: {reason}")
        await log_action(ctx.guild, f"{ctx.author} timed out {member} for {minutes} minutes. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send("I cannot timeout that member.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, limit: int):
    deleted = await ctx.channel.purge(limit=limit)
    await ctx.send(f"Deleted {len(deleted)} messages.", delete_after=5)
    await log_action(ctx.guild, f"{ctx.author} purged {len(deleted)} messages in {ctx.channel}.")

@bot.command()
@commands.has_permissions(ban_members=True)
async def softban(ctx, member: discord.Member, *, reason=None):
    try:
        await member.ban(reason=reason, delete_message_days=7)
        await member.unban(reason="Softban completed")
        await ctx.send(f"{member} was softbanned.")
        await log_action(ctx.guild, f"{ctx.author} softbanned {member}. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send("Cannot softban this member.")

@bot.command()
@commands.has_permissions(administrator=True)
async def warn(ctx, member: discord.Member, *, reason=None):
    warn_data[member.id] = warn_data.get(member.id, 0) + 1
    await ctx.send(f"{member} warned. Total warns: {warn_data[member.id]} Reason: {reason}")
    await log_action(ctx.guild, f"{ctx.author} warned {member}. Total warns: {warn_data[member.id]}. Reason: {reason}")

# ----------------- DMS -----------------
@bot.command()
@commands.has_permissions(administrator=True)
async def dmall(ctx, *, message):
    success = 0
    for member in ctx.guild.members:
        if not member.bot:
            try:
                await member.send(message)
                success += 1
            except:
                pass
    await ctx.send(f"DM sent to {success} members.")
    await log_action(ctx.guild, f"{ctx.author} sent a DM to {success} members: {message}")

# ----------------- GIVEAWAYS -----------------
giveaways = {}

@bot.command()
@commands.has_permissions(administrator=True)
async def giveaway(ctx, duration: int, *, prize):
    if ctx.guild.id in giveaways:
        await ctx.send("A giveaway is already running!")
        return
    end_time = datetime.utcnow() + timedelta(minutes=duration)
    giveaways[ctx.guild.id] = {"channel": ctx.channel, "prize": prize, "end": end_time, "entries": set()}
    await ctx.send(f"🎉 Giveaway started for **{prize}**! Ends in {duration} minutes.\nReact with 🎉 to enter!")
    await log_action(ctx.guild, f"{ctx.author} started a giveaway for {prize} lasting {duration} minutes.")

@tasks.loop(seconds=30)
async def giveaway_loop():
    to_remove = []
    for guild_id, data in giveaways.items():
        if datetime.utcnow() >= data["end"]:
            channel = data["channel"]
            if data["entries"]:
                winner = random.choice(list(data["entries"]))
                await channel.send(f"🎉 Giveaway for **{data['prize']}** ended! Winner: {winner.mention}")
                await log_action(channel.guild, f"Giveaway for {data['prize']} ended. Winner: {winner}.")
            else:
                await channel.send(f"Giveaway for **{data['prize']}** ended with no entries.")
                await log_action(channel.guild, f"Giveaway for {data['prize']} ended with no entries.")
            to_remove.append(guild_id)
    for guild_id in to_remove:
        giveaways.pop(guild_id, None)

@bot.event
async def on_reaction_add(reaction, user):
    if reaction.emoji == "🎉" and not user.bot:
        for data in giveaways.values():
            if data["channel"].id == reaction.message.channel.id:
                data["entries"].add(user)
                await log_action(reaction.message.guild, f"{user} entered the giveaway for {data['prize']}.")

# ----------------- ECONOMY -----------------
@bot.command()
async def balance(ctx, member: discord.Member = None):
    member = member or ctx.author
    bal = money_data.get(member.id, 0)
    await ctx.send(f"{member} has {bal} coins.")
    await log_action(ctx.guild, f"{ctx.author} checked balance of {member}: {bal} coins.")

@bot.command()
async def daily(ctx):
    user = ctx.author
    now = datetime.utcnow()
    last_claim = daily_claimed.get(user.id)
    if last_claim and (now - last_claim).total_seconds() < 86400:
        await ctx.send("You can only claim daily once every 24 hours.")
        return
    coins = random.randint(50, 200)
    money_data[user.id] = money_data.get(user.id, 0) + coins
    daily_claimed[user.id] = now
    await ctx.send(f"{user} collected {coins} coins today!")
    await log_action(ctx.guild, f"{user} claimed daily reward: {coins} coins.")

@bot.command()
async def pay(ctx, member: discord.Member, amount: int):
    sender = ctx.author
    if money_data.get(sender.id, 0) < amount:
        await ctx.send("Not enough coins!")
        return
    money_data[sender.id] -= amount
    money_data[member.id] = money_data.get(member.id, 0) + amount
    await ctx.send(f"{sender} paid {member} {amount} coins.")
    await log_action(ctx.guild, f"{sender} paid {member} {amount} coins.")

@bot.command()
@commands.has_permissions(administrator=True)
async def setbalance(ctx, member: discord.Member, amount: int):
    money_data[member.id] = amount
    await ctx.send(f"{member}'s balance set to {amount} coins.")
    await log_action(ctx.guild, f"{ctx.author} set balance of {member} to {amount} coins.")

# ----------------- LEVELS -----------------
@bot.command()
async def level(ctx, member: discord.Member = None):
    member = member or ctx.author
    xp = xp_data.get(member.id, 0)
    lvl = xp // 100
    await ctx.send(f"{member} is level {lvl} with {xp} XP.")
    await log_action(ctx.guild, f"{ctx.author} checked level of {member}: {lvl}.")

# ----------------- FUN COMMANDS -----------------
@bot.command()
async def coinflip(ctx):
    result = random.choice(["Heads","Tails"])
    await ctx.send(f"🪙 {ctx.author.mention} flipped {result}")
    await log_action(ctx.guild, f"{ctx.author} flipped a coin: {result}")

@bot.command()
async def roll(ctx, sides: int = 6):
    result = random.randint(1, sides)
    await ctx.send(f"{ctx.author.mention} rolled a {sides}-sided dice: {result}")
    await log_action(ctx.guild, f"{ctx.author} rolled a {sides}-sided dice: {result}")

@bot.command()
async def hug(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"{ctx.author.mention} hugs {member.mention} 🤗")
    await log_action(ctx.guild, f"{ctx.author} hugged {member}.")

@bot.command()
async def kiss(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"{ctx.author.mention} kisses {member.mention} 😘")
    await log_action(ctx.guild, f"{ctx.author} kissed {member}.")

@bot.command()
async def slap(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"{ctx.author.mention} slaps {member.mention} 👋")
    await log_action(ctx.guild, f"{ctx.author} slapped {member}.")

@bot.command()
async def say(ctx, *, text):
    await ctx.send(text)
    await log_action(ctx.guild, f"{ctx.author} used say: {text}")

@bot.command()
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(member.display_avatar.url)
    await log_action(ctx.guild, f"{ctx.author} requested avatar of {member}.")

# ----------------- UTILITIES -----------------
@bot.command()
async def serverinfo(ctx):
    g = ctx.guild
    embed = discord.Embed(title=f"{g.name}", description=f"ID: {g.id}", color=discord.Color.blue())
    embed.add_field(name="Owner", value=g.owner)
    embed.add_field(name="Members", value=g.member_count)
    embed.add_field(name="Text Channels", value=len(g.text_channels))
    embed.add_field(name="Voice Channels", value=len(g.voice_channels))
    embed.add_field(name="Roles", value=len(g.roles))
    embed.add_field(name="Created At", value=g.created_at.strftime("%Y-%m-%d %H:%M:%S"))
    await ctx.send(embed=embed)
    await log_action(ctx.guild, f"{ctx.author} requested server info for {g.name}.")

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"{member}", color=discord.Color.green())
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Bot?", value=member.bot)
    embed.add_field(name="Created At", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"))
    embed.add_field(name="Joined At", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"))
    await ctx.send(embed=embed)
    await log_action(ctx.guild, f"{ctx.author} requested info on {member}.")
    
# ----------------- AUTOROLE -----------------
@bot.command()
@commands.has_permissions(administrator=True)
async def setautorole(ctx, role: discord.Role):
    global DEFAULT_ROLE_NAME
    DEFAULT_ROLE_NAME = role.name
    await ctx.send(f"Autorole set to {role.name}. New members will automatically get this role.")
    await log_action(ctx.guild, f"{ctx.author} set autorole to {role.name}.")

# ----------------- CHANNEL LOCK/UNLOCK -----------------
@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(f"{channel.mention} is now locked.")
    await log_action(ctx.guild, f"{ctx.author} locked {channel}.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(f"{channel.mention} is now unlocked.")
    await log_action(ctx.guild, f"{ctx.author} unlocked {channel}.")

# ----------------- OWNER-ONLY COMMANDS -----------------
@bot.command()
async def shutdown(ctx):
    if ctx.author.id != OWNER_ID:
        await ctx.send("You do not have permission to shut down the bot.")
        return
    await ctx.send("Shutting down...")
    await log_action(ctx.guild, f"{ctx.author} shut down the bot.")
    await bot.close()

@bot.command()
async def disablebot(ctx, member: discord.Member):
    if ctx.author.id != OWNER_ID:
        await ctx.send("You cannot disable the bot for other users.")
        return
    # simulation: mark user as disabled
    disabled_users.add(member.id)
    await ctx.send(f"{member} can no longer use the bot.")
    await log_action(ctx.guild, f"{ctx.author} disabled bot for {member}.")

@bot.command()
async def broadcast(ctx, *, message):
    if ctx.author.id != OWNER_ID:
        await ctx.send("Only the bot owner can use broadcast.")
        return
    for guild in bot.guilds:
        for channel in guild.text_channels:
            try:
                await channel.send(message)
            except:
                continue
    await ctx.send("Broadcast sent to all servers.")
    await log_action(ctx.guild, f"{ctx.author} broadcasted message to all servers.")

# ----------------- REACTION BASED MINI GAMES -----------------
tic_tac_toe_games = {}

@bot.command()
async def tictactoe(ctx, opponent: discord.Member, wager: int = 0):
    player1 = ctx.author
    player2 = opponent
    if player1.id in tic_tac_toe_games or player2.id in tic_tac_toe_games:
        await ctx.send("One of the players is already in a game.")
        return

    board = [" "]*9
    turn = player1
    game_id = f"{player1.id}-{player2.id}"
    tic_tac_toe_games[player1.id] = game_id
    tic_tac_toe_games[player2.id] = game_id

    async def print_board():
        return (f"{board[0]} | {board[1]} | {board[2]}\n"
                f"{board[3]} | {board[4]} | {board[5]}\n"
                f"{board[6]} | {board[7]} | {board[8]}")

    await ctx.send(f"Tic Tac Toe started between {player1.mention} and {player2.mention}!\n{await print_board()}")

    # For simplicity, use reactions to input moves in a real scenario, would add buttons or check messages

@bot.command()
async def blackjack(ctx):
    # simplified blackjack game
    user = ctx.author
    cards = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"]*4
    random.shuffle(cards)
    player_hand = [cards.pop(), cards.pop()]
    dealer_hand = [cards.pop(), cards.pop()]
    await ctx.send(f"Blackjack started! Your cards: {player_hand}, Dealer shows: {dealer_hand[0]}")
    await log_action(ctx.guild, f"{user} started a blackjack game. Player: {player_hand}, Dealer: {dealer_hand}")

# ----------------- SCHEDULED MESSAGES -----------------
scheduled_messages = []

@bot.command()
async def schedule(ctx, minutes: int, *, message):
    send_time = datetime.utcnow() + timedelta(minutes=minutes)
    scheduled_messages.append({"channel": ctx.channel, "message": message, "time": send_time})
    await ctx.send(f"Message scheduled to be sent in {minutes} minutes (blurred).")
    await log_action(ctx.guild, f"{ctx.author} scheduled a message for {minutes} minutes: {message}")

@tasks.loop(seconds=10)
async def check_scheduled_messages():
    now = datetime.utcnow()
    for msg in scheduled_messages[:]:
        if now >= msg["time"]:
            await msg["channel"].send(msg["message"])
            scheduled_messages.remove(msg)
            await log_action(msg["channel"].guild, f"Scheduled message sent: {msg['message']}")

# ----------------- CLIP COMMAND -----------------
@bot.command()
async def clip(ctx, message: discord.Message):
    content = message.content
    author = message.author
    timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
    await ctx.author.send(f"Clipped message from {author} at {timestamp}:\n{content}")
    await ctx.send("Message clipped to your DMs.")
    await log_action(ctx.guild, f"{ctx.author} clipped a message from {author} at {timestamp}.")

# ----------------- ADDITIONAL FUN COMMANDS -----------------
@bot.command()
async def crime(ctx):
    success = random.choice([True, False])
    reward = random.randint(50, 200)
    if success:
        money_data[ctx.author.id] = money_data.get(ctx.author.id, 0) + reward
        await ctx.send(f"You committed a crime successfully and earned {reward} coins!")
        await log_action(ctx.guild, f"{ctx.author} committed a crime and earned {reward} coins.")
    else:
        await ctx.send("You failed and got nothing.")
        await log_action(ctx.guild, f"{ctx.author} attempted a crime but failed.")

@bot.command()
async def loot(ctx):
    items = ["Sword","Shield","Potion","Gold","Gem"]
    found = random.choice(items)
    await ctx.send(f"You opened a crate and got: {found}")
    await log_action(ctx.guild, f"{ctx.author} opened a crate and found {found}.")

@bot.command()
async def quest(ctx):
    reward = random.randint(50,150)
    money_data[ctx.author.id] = money_data.get(ctx.author.id,0) + reward
    await ctx.send(f"You completed a daily quest and got {reward} coins!")
    await log_action(ctx.guild, f"{ctx.author} completed a quest and got {reward} coins.")

# ----------------- DUEL -----------------
duel_games = {}

@bot.command()
async def duel(ctx, opponent: discord.Member, wager: int = 0):
    player1 = ctx.author
    player2 = opponent
    if player1.id in duel_games or player2.id in duel_games:
        await ctx.send("One of the players is already in a duel.")
        return
    result = random.choice([player1, player2])
    if wager > 0:
        money_data[result.id] = money_data.get(result.id,0)+wager
        money_data[player1.id] -= wager
        money_data[player2.id] -= wager
    await ctx.send(f"Duel finished! Winner: {result.mention}")
    await log_action(ctx.guild, f"{player1} and {player2} dueled. Winner: {result}. Wager: {wager}")
    
# ----------------- CATCH GAME -----------------
catch_games = {}

@bot.command()
async def catch(ctx):
    creatures = ["Dragon", "Goblin", "Phoenix", "Unicorn", "Slime"]
    creature = random.choice(creatures)
    await ctx.send(f"A wild {creature} appeared! Type `catch` to catch it!")

    def check(m):
        return m.content.lower() == "catch" and m.author == ctx.author

    try:
        msg = await bot.wait_for('message', check=check, timeout=15)
        reward = random.randint(50, 200)
        money_data[ctx.author.id] = money_data.get(ctx.author.id, 0) + reward
        await ctx.send(f"You caught the {creature} and earned {reward} coins!")
        await log_action(ctx.guild, f"{ctx.author} caught a {creature} and earned {reward} coins.")
    except asyncio.TimeoutError:
        await ctx.send(f"The {creature} escaped!")
        await log_action(ctx.guild, f"{ctx.author} failed to catch {creature}.")

# ----------------- TRIVIA -----------------
trivia_questions = [
    {"q": "What is the capital of France?", "a": "paris"},
    {"q": "Who wrote Hamlet?", "a": "shakespeare"},
    {"q": "2+2*2=?", "a": "6"},
]

@bot.command()
async def trivia(ctx):
    question = random.choice(trivia_questions)
    await ctx.send(f"Trivia: {question['q']}")

    def check(m):
        return m.author == ctx.author

    try:
        msg = await bot.wait_for('message', check=check, timeout=15)
        if msg.content.lower() == question['a']:
            reward = random.randint(50, 150)
            money_data[ctx.author.id] = money_data.get(ctx.author.id, 0) + reward
            await ctx.send(f"Correct! You earned {reward} coins.")
            await log_action(ctx.guild, f"{ctx.author} answered trivia correctly and earned {reward} coins.")
        else:
            await ctx.send("Incorrect answer!")
            await log_action(ctx.guild, f"{ctx.author} answered trivia incorrectly.")
    except asyncio.TimeoutError:
        await ctx.send("Time's up!")

# ----------------- BALANCE AND LEADERBOARD -----------------
@bot.command()
async def balance(ctx, member: discord.Member = None):
    member = member or ctx.author
    bal = money_data.get(member.id, 0)
    await ctx.send(f"{member} has {bal} coins.")
    await log_action(ctx.guild, f"{ctx.author} checked balance of {member}: {bal} coins.")

@bot.command()
async def setbalance(ctx, member: discord.Member, amount: int):
    if not is_owner_or_co(ctx):
        await ctx.send("You do not have permission to set balances.")
        return
    money_data[member.id] = amount
    await ctx.send(f"{member}'s balance is now set to {amount} coins.")
    await log_action(ctx.guild, f"{ctx.author} set {member}'s balance to {amount} coins.")

@bot.command()
async def leaderboard(ctx):
    top_users = sorted(money_data.items(), key=lambda x: x[1], reverse=True)[:10]
    embed = discord.Embed(title="Top 10 Richest Users", color=discord.Color.gold())
    for user_id, bal in top_users:
        member = ctx.guild.get_member(user_id)
        if member:
            embed.add_field(name=member.display_name, value=f"{bal} coins", inline=False)
    await ctx.send(embed=embed)
    await log_action(ctx.guild, f"{ctx.author} checked the leaderboard.")

# ----------------- DAILY COINS -----------------
@bot.command()
async def daily(ctx):
    user = ctx.author
    now = datetime.utcnow()
    last_claim = daily_claimed.get(user.id)
    if last_claim and now - last_claim < timedelta(hours=24):
        remaining = timedelta(hours=24) - (now - last_claim)
        await ctx.send(f"You have already claimed daily coins. Come back in {remaining}.")
        return
    coins = random.randint(50, 200)
    money_data[user.id] = money_data.get(user.id, 0) + coins
    daily_claimed[user.id] = now
    await ctx.send(f"You collected {coins} coins today!")
    await log_action(ctx.guild, f"{ctx.author} collected daily coins: {coins}")

# ----------------- COINFLIP -----------------
@bot.command()
async def coinflip(ctx):
    result = random.choice(["Heads", "Tails"])
    await ctx.send(f"{ctx.author.mention} flipped a coin and got {result}.")
    await log_action(ctx.guild, f"{ctx.author} flipped a coin: {result}")

# ----------------- ROLL DICE -----------------
@bot.command()
async def roll(ctx, sides: int = 6):
    result = random.randint(1, sides)
    await ctx.send(f"{ctx.author.mention} rolled a {sides}-sided dice: {result}")
    await log_action(ctx.guild, f"{ctx.author} rolled a {sides}-sided dice: {result}")

# ----------------- FUN EMOTES -----------------
@bot.command()
async def hug(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"{ctx.author.mention} hugs {member.mention} 🤗")
    await log_action(ctx.guild, f"{ctx.author} hugged {member}")

@bot.command()
async def kiss(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"{ctx.author.mention} kisses {member.mention} 😘")
    await log_action(ctx.guild, f"{ctx.author} kissed {member}")

@bot.command()
async def slap(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"{ctx.author.mention} slaps {member.mention} 👋")
    await log_action(ctx.guild, f"{ctx.author} slapped {member}")

@bot.command()
async def say(ctx, *, text):
    await ctx.send(text)
    await log_action(ctx.guild, f"{ctx.author} used say: {text}")

@bot.command()
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(member.display_avatar.url)
    await log_action(ctx.guild, f"{ctx.author} checked avatar of {member}")

# ----------------- SERVER & USER INFO -----------------
@bot.command()
async def serverinfo(ctx):
    g = ctx.guild
    embed = discord.Embed(title=f"{g.name}", description=f"ID: {g.id}", color=discord.Color.blue())
    embed.add_field(name="Owner", value=g.owner)
    embed.add_field(name="Members", value=g.member_count)
    embed.add_field(name="Text Channels", value=len(g.text_channels))
    embed.add_field(name="Voice Channels", value=len(g.voice_channels))
    embed.add_field(name="Roles", value=len(g.roles))
    embed.add_field(name="Created At", value=g.created_at.strftime("%Y-%m-%d %H:%M:%S"))
    await ctx.send(embed=embed)
    await log_action(ctx.guild, f"{ctx.author} checked server info.")

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    country = getattr(member, 'locale', 'Unknown')  # placeholder
    embed = discord.Embed(title=f"{member}", color=discord.Color.green())
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Bot?", value=member.bot)
    embed.add_field(name="Country", value=country)
    embed.add_field(name="Created At", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"))
    embed.add_field(name="Joined At", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"))
    await ctx.send(embed=embed)
    await log_action(ctx.guild, f"{ctx.author} checked userinfo for {member}")
    
# ----------------- OWNER COMMANDS -----------------
@bot.command()
async def shutdown(ctx):
    if not is_owner(ctx):
        await ctx.send("You cannot use this command.")
        return
    await ctx.send("Shutting down the bot...")
    await log_action(ctx.guild, f"{ctx.author} shut down the bot.")
    await bot.close()

@bot.command()
async def broadcast(ctx, *, message):
    if not is_owner(ctx):
        await ctx.send("You cannot use this command.")
        return
    for guild in bot.guilds:
        channel = await get_logs_channel(guild)
        await channel.send(f"Broadcast from owner: {message}")
    await ctx.send("Broadcast sent to all servers.")
    await log_action(ctx.guild, f"{ctx.author} broadcasted: {message}")

@bot.command()
async def disablebot(ctx, member: discord.Member):
    if not is_owner(ctx):
        await ctx.send("You cannot use this command.")
        return
    if member.id == OWNER_ID:
        await ctx.send("Cannot disable bot for the owner.")
        return
    member_disabled[member.id] = True
    await ctx.send(f"{member} is now disabled from using bot commands.")
    await log_action(ctx.guild, f"{ctx.author} disabled bot for {member}")

# ----------------- GIVEAWAYS -----------------
giveaways = {}

@bot.command()
@commands.has_permissions(administrator=True)
async def giveaway(ctx, duration: int, *, prize):
    if ctx.guild.id in giveaways:
        await ctx.send("A giveaway is already running!")
        return
    end_time = datetime.utcnow() + timedelta(minutes=duration)
    giveaways[ctx.guild.id] = {"channel": ctx.channel, "prize": prize, "end": end_time, "entries": set()}
    msg = await ctx.send(f"🎉 Giveaway started for **{prize}**! React with 🎉 to enter!")
    await msg.add_reaction("🎉")
    await log_action(ctx.guild, f"{ctx.author} started a giveaway for {prize} lasting {duration} minutes.")

@tasks.loop(seconds=30)
async def giveaway_loop():
    to_remove = []
    for guild_id, data in giveaways.items():
        if datetime.utcnow() >= data["end"]:
            channel = data["channel"]
            if data["entries"]:
                winner = random.choice(list(data["entries"]))
                await channel.send(f"🎉 Giveaway for **{data['prize']}** ended! Winner: {winner.mention}")
                money_data[winner.id] = money_data.get(winner.id, 0) + 500  # example reward
            else:
                await channel.send(f"Giveaway for **{data['prize']}** ended with no entries.")
            to_remove.append(guild_id)
    for guild_id in to_remove:
        giveaways.pop(guild_id, None)

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    if reaction.emoji == "🎉":
        for data in giveaways.values():
            if data["channel"].id == reaction.message.channel.id:
                data["entries"].add(user)
                await log_action(reaction.message.guild, f"{user} entered giveaway for {data['prize']}")

# ----------------- TIC TAC TOE -----------------
tictactoe_games = {}

@bot.command()
async def ttt(ctx, opponent: discord.Member, wager: int = 0):
    if ctx.author.id in tictactoe_games or opponent.id in tictactoe_games:
        await ctx.send("One of the players is already in a Tic Tac Toe game!")
        return

    board = ["⬜"] * 9
    turn = ctx.author
    tictactoe_games[ctx.author.id] = {"opponent": opponent, "board": board, "turn": turn, "wager": wager}
    tictactoe_games[opponent.id] = tictactoe_games[ctx.author.id]

    await ctx.send(f"Tic Tac Toe started between {ctx.author} and {opponent}. {'Wager: ' + str(wager) + ' coins' if wager > 0 else 'No wager.'}")
    await print_board(ctx, board)

async def print_board(ctx, board):
    lines = ""
    for i in range(0, 9, 3):
        lines += "".join(board[i:i+3]) + "\n"
    await ctx.send(f"```\n{lines}\n```")

@bot.command()
async def place(ctx, position: int):
    game = tictactoe_games.get(ctx.author.id)
    if not game:
        await ctx.send("You are not in a Tic Tac Toe game.")
        return
    if ctx.author != game["turn"]:
        await ctx.send("It's not your turn.")
        return
    if position < 1 or position > 9 or game["board"][position-1] != "⬜":
        await ctx.send("Invalid position.")
        return

    symbol = "❌" if ctx.author == list(tictactoe_games.keys())[0] else "⭕"
    game["board"][position-1] = symbol

    winner = check_winner(game["board"])
    if winner:
        await ctx.send(f"{ctx.author} won the game!")
        if game["wager"] > 0:
            money_data[ctx.author.id] = money_data.get(ctx.author.id, 0) + game["wager"] * 2
        cleanup_game(game)
        return

    game["turn"] = game["opponent"] if ctx.author == game["turn"] else ctx["turn"]
    await print_board(ctx, game["board"])

def check_winner(board):
    lines = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for a,b,c in lines:
        if board[a] == board[b] == board[c] != "⬜":
            return True
    return False

def cleanup_game(game):
    for key in list(tictactoe_games.keys()):
        if tictactoe_games[key] == game:
            del tictactoe_games[key]

# ----------------- BLACKJACK -----------------
blackjack_games = {}

@bot.command()
async def blackjack(ctx, wager: int = 0):
    if ctx.author.id in blackjack_games:
        await ctx.send("You are already in a blackjack game!")
        return
    deck = [2,3,4,5,6,7,8,9,10,10,10,10,11]*4
    random.shuffle(deck)
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]
    blackjack_games[ctx.author.id] = {"player": player_hand, "dealer": dealer_hand, "wager": wager}

    await ctx.send(f"Blackjack started! Your hand: {player_hand}, dealer shows: {dealer_hand[0]}")
    
# ----------------- BLACKJACK CONTINUED -----------------
@bot.command()
async def hit(ctx):
    game = blackjack_games.get(ctx.author.id)
    if not game:
        await ctx.send("You are not in a blackjack game!")
        return
    deck = [2,3,4,5,6,7,8,9,10,10,10,10,11]*4
    random.shuffle(deck)
    game["player"].append(deck.pop())
    total = sum(game["player"])
    await ctx.send(f"Your hand: {game['player']}, total: {total}")
    if total > 21:
        await ctx.send("Bust! You lose.")
        cleanup_blackjack(ctx.author.id)
    elif total == 21:
        await ctx.send("Blackjack! You win!")
        if game["wager"] > 0:
            money_data[ctx.author.id] = money_data.get(ctx.author.id,0) + game["wager"]*2
        cleanup_blackjack(ctx.author.id)

@bot.command()
async def stand(ctx):
    game = blackjack_games.get(ctx.author.id)
    if not game:
        await ctx.send("You are not in a blackjack game!")
        return
    dealer_total = sum(game["dealer"])
    player_total = sum(game["player"])
    while dealer_total < 17:
        deck = [2,3,4,5,6,7,8,9,10,10,10,10,11]*4
        random.shuffle(deck)
        game["dealer"].append(deck.pop())
        dealer_total = sum(game["dealer"])
    await ctx.send(f"Dealer hand: {game['dealer']}, total: {dealer_total}")
    if dealer_total > 21 or player_total > dealer_total:
        await ctx.send("You win!")
        if game["wager"] > 0:
            money_data[ctx.author.id] = money_data.get(ctx.author.id,0) + game["wager"]*2
    elif dealer_total == player_total:
        await ctx.send("Draw!")
        if game["wager"] > 0:
            money_data[ctx.author.id] = money_data.get(ctx.author.id,0) + game["wager"]
    else:
        await ctx.send("You lose!")
    cleanup_blackjack(ctx.author.id)

def cleanup_blackjack(user_id):
    if user_id in blackjack_games:
        del blackjack_games[user_id]

# ----------------- AUTOROLE -----------------
@bot.event
async def on_member_join(member):
    role = discord.utils.get(member.guild.roles, name=DEFAULT_ROLE_NAME)
    if role:
        try:
            await member.add_roles(role)
            await log_action(member.guild, f"{member} joined and was given {DEFAULT_ROLE_NAME} role automatically.")
        except discord.Forbidden:
            print(f"Cannot add role to {member}, missing permissions.")

# ----------------- LOCK / UNLOCK CHANNEL -----------------
@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(f"{channel.mention} has been locked.")
    await log_action(ctx.guild, f"{ctx.author} locked {channel}.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(f"{channel.mention} has been unlocked.")
    await log_action(ctx.guild, f"{ctx.author} unlocked {channel}.")

# ----------------- REACTION GAMES -----------------
reaction_games = {}

@bot.command()
async def rps(ctx, opponent: discord.Member):
    if ctx.author.id in reaction_games or opponent.id in reaction_games:
        await ctx.send("One of the players is already in a reaction game!")
        return
    msg = await ctx.send(f"{ctx.author.mention} vs {opponent.mention}: React with ✊ ✋ ✌️ to play Rock-Paper-Scissors!")
    for emoji in ["✊","✋","✌️"]:
        await msg.add_reaction(emoji)
    reaction_games[ctx.author.id] = {"opponent": opponent, "message": msg, "choices": {}}
    reaction_games[opponent.id] = reaction_games[ctx.author.id]

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    game = reaction_games.get(user.id)
    if not game:
        return
    if reaction.message.id != game["message"].id:
        return
    game["choices"][user.id] = reaction.emoji
    if len(game["choices"]) == 2:
        p1, p2 = list(game["choices"].keys())
        choice1, choice2 = game["choices"][p1], game["choices"][p2]
        winner_text = None
        if choice1 == choice2:
            winner_text = "It's a draw!"
        elif (choice1=="✊" and choice2=="✌️") or (choice1=="✋" and choice2=="✊") or (choice1=="✌️" and choice2=="✋"):
            winner_text = f"{bot.get_user(p1).mention} wins!"
        else:
            winner_text = f"{bot.get_user(p2).mention} wins!"
        await reaction.message.channel.send(winner_text)
        for uid in [p1, p2]:
            del reaction_games[uid]
        await log_action(reaction.message.guild, f"RPS game finished: {winner_text}")

# ----------------- DAILY COMMAND WITH 24H COOLDOWN -----------------
@bot.command()
async def daily(ctx):
    now = datetime.utcnow()
    last_claimed = daily_claimed.get(ctx.author.id)
    if last_claimed and now - last_claimed < timedelta(hours=24):
        await ctx.send("You already claimed daily coins today!")
        return
    coins = random.randint(50,200)
    money_data[ctx.author.id] = money_data.get(ctx.author.id,0) + coins
    daily_claimed[ctx.author.id] = now
    await ctx.send(f"{ctx.author} collected {coins} daily coins!")
    await log_action(ctx.guild, f"{ctx.author} collected {coins} coins from daily.")

# ----------------- MONEY SET COMMAND (OWNER ONLY) -----------------
@bot.command()
async def setbalance(ctx, member: discord.Member, amount: int):
    if not is_owner_or_co(ctx):
        await ctx.send("You cannot use this command.")
        return
    money_data[member.id] = amount
    await ctx.send(f"{member}'s balance set to {amount}.")
    await log_action(ctx.guild, f"{ctx.author} set {member}'s balance to {amount}.")
    
# ----------------- LEADERBOARD -----------------
@bot.command()
async def leaderboard(ctx, top: int = 10):
    """Shows the top users by coins."""
    sorted_balances = sorted(money_data.items(), key=lambda x: x[1], reverse=True)
    embed = discord.Embed(title=f"Top {top} Richest Users", color=discord.Color.gold())
    for i, (user_id, balance) in enumerate(sorted_balances[:top], start=1):
        member = ctx.guild.get_member(user_id)
        if member:
            embed.add_field(name=f"{i}. {member}", value=f"{balance} coins", inline=False)
    await ctx.send(embed=embed)
    await log_action(ctx.guild, f"{ctx.author} viewed the leaderboard.")

# ----------------- FUN COMMANDS -----------------
@bot.command()
async def coinflip(ctx):
    """Flip a coin."""
    result = random.choice(["Heads", "Tails"])
    await ctx.send(f"🪙 {ctx.author.mention} flipped {result}.")
    await log_action(ctx.guild, f"{ctx.author} flipped a coin: {result}")

@bot.command()
async def roll(ctx, sides: int = 6):
    """Roll a dice with N sides."""
    result = random.randint(1, sides)
    await ctx.send(f"{ctx.author.mention} rolled a {sides}-sided dice: {result}")
    await log_action(ctx.guild, f"{ctx.author} rolled a {sides}-sided dice: {result}")

@bot.command()
async def hug(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"{ctx.author.mention} hugs {member.mention} 🤗")
    await log_action(ctx.guild, f"{ctx.author} hugged {member}.")

@bot.command()
async def kiss(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"{ctx.author.mention} kisses {member.mention} 😘")
    await log_action(ctx.guild, f"{ctx.author} kissed {member}.")

@bot.command()
async def slap(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"{ctx.author.mention} slaps {member.mention} 👋")
    await log_action(ctx.guild, f"{ctx.author} slapped {member}.")

@bot.command()
async def say(ctx, *, text):
    """Bot repeats a message."""
    await ctx.send(text)
    await log_action(ctx.guild, f"{ctx.author} used say command: {text}")

@bot.command()
async def avatar(ctx, member: discord.Member = None):
    """Shows the avatar of a user."""
    member = member or ctx.author
    await ctx.send(member.display_avatar.url)
    await log_action(ctx.guild, f"{ctx.author} checked avatar of {member}.")

# ----------------- SERVER & USER INFO -----------------
@bot.command()
async def serverinfo(ctx):
    g = ctx.guild
    embed = discord.Embed(title=f"{g.name}", color=discord.Color.blue())
    embed.add_field(name="Owner", value=g.owner)
    embed.add_field(name="Members", value=g.member_count)
    embed.add_field(name="Text Channels", value=len(g.text_channels))
    embed.add_field(name="Voice Channels", value=len(g.voice_channels))
    embed.add_field(name="Roles", value=len(g.roles))
    embed.add_field(name="Created At", value=g.created_at.strftime("%Y-%m-%d %H:%M:%S"))
    await ctx.send(embed=embed)
    await log_action(ctx.guild, f"{ctx.author} checked server info.")

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    """Shows info about a user."""
    member = member or ctx.author
    embed = discord.Embed(title=f"{member}", color=discord.Color.green())
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Bot?", value=member.bot)
    embed.add_field(name="Created At", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"))
    embed.add_field(name="Joined At", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"))
    # Example placeholder for country info (requires geo API or database)
    embed.add_field(name="Country", value="Unknown")
    await ctx.send(embed=embed)
    await log_action(ctx.guild, f"{ctx.author} checked info of {member}.")
    
check_scheduled_messages.start()
giveaway_loop.start()
bot.run(TOKEN)
