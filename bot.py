import os
import discord
from discord.ext import commands, tasks
import random
from datetime import datetime, timedelta

# ----------------- CONFIG -----------------
TOKEN = os.getenv("TOKEN") or "YOUR_TOKEN_HERE"
COMMAND_PREFIX = "!"
OWNER_ID = 1169273992289456341
CO_OWNER_ID = 958273785037983754
DEFAULT_ROLE_NAME = "Member"
WELCOME_CHANNEL_NAME = "arrivals"
LOGS_CHANNEL_NAME = "bot-logs"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

# ----------------- DATABASES / VARIABLES -----------------
# XP and levels
xp = {}
levels = {}

# Economy
money_data = {}
daily_claimed = {}

# Moderation
warn_data = {}
disabled_users = set()
member_disabled = {}

# Autorole
autorole_id = None

# Invites tracking
invite_cache = {}  # cached invites per guild
invite_data = {}   # total invites per user

# Giveaways
giveaways = {}

# Scheduled messages
scheduled_messages = []

# Mini-games
blackjack_games = {}
tictactoe_games = {}
reaction_games = {}

# ----------------- HELPER FUNCTIONS -----------------
def is_owner(user):
    return user.id == OWNER_ID

def is_owner_or_co(user):
    return user.id in [OWNER_ID, CO_OWNER_ID]

def add_xp(user_id):
    xp[user_id] = xp.get(user_id, 0) + random.randint(5, 15)

def get_level(user_id):
    return xp.get(user_id, 0) // 100  # Example: 100 XP = 1 level
# ---------------- EVENTS ----------------

@bot.event
async def on_ready():

    print(f"Bot online as {bot.user}")

    for guild in bot.guilds:
        invites = await guild.invites()
        invite_cache[guild.id] = {invite.code: invite.uses for invite in invites}

    if not check_giveaways.is_running():
        check_giveaways.start()


# ---------------- LEVEL SYSTEM ----------------

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if message.author.id in disabled_users:
        return

    leveled_up = add_xp(message.author.id)

    if leveled_up:
        await message.channel.send(
            f"🎉 {message.author.mention} leveled up to **Level {levels[message.author.id]}**!"
        )

    await bot.process_commands(message)


# ---------------- MEMBER JOIN / INVITE TRACKING ----------------

@bot.event
async def on_member_join(member):

    guild = member.guild

    inviter = None

    new_invites = await guild.invites()
    old_invites = invite_cache.get(guild.id, {})

    for invite in new_invites:
        if invite.code in old_invites and invite.uses > old_invites[invite.code]:
            inviter = invite.inviter
            invite_data[inviter.id] = invite_data.get(inviter.id, 0) + 1
            break

    invite_cache[guild.id] = {invite.code: invite.uses for invite in new_invites}

    # Autorole
    if autorole_id:
        role = guild.get_role(autorole_id)
        if role:
            await member.add_roles(role)

    # Welcome message
    arrivals = discord.utils.get(guild.text_channels, name=ARRIVAL_CHANNEL_NAME)

    if arrivals:

        embed = discord.Embed(
            title="New Member Joined",
            color=discord.Color.green()
        )

        embed.add_field(name="User", value=member.mention, inline=False)
        embed.add_field(name="Account Created", value=str(member.created_at.date()), inline=False)

        if inviter:
            embed.add_field(name="Invited By", value=inviter.mention, inline=False)

        embed.set_thumbnail(url=member.display_avatar.url)

        await arrivals.send(embed=embed)


# ---------------- MEMBER LEAVE ----------------

@bot.event
async def on_member_remove(member):

    arrivals = discord.utils.get(member.guild.text_channels, name=ARRIVAL_CHANNEL_NAME)

    if arrivals:

        embed = discord.Embed(
            title="Member Left",
            description=f"{member} left the server.",
            color=discord.Color.red()
        )

        await arrivals.send(embed=embed)
        
# ----------------- OWNER / CO-OWNER COMMANDS -----------------
@bot.command()
async def ping(ctx):
    """Check bot latency."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("You cannot use this command.")
        return
    await ctx.send(f"Pong! Latency: {round(bot.latency*1000)}ms")

@bot.command()
async def shutdown(ctx):
    """Shutdown the bot (Owner/Co-owner)."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("You cannot use this command.")
        return
    await ctx.send("Shutting down...")
    await bot.close()

@bot.command()
async def disable_user(ctx, member: discord.Member):
    """Disable a user from using bot commands."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("You cannot use this command.")
        return
    disabled_users.add(member.id)
    await ctx.send(f"{member} has been disabled from using commands.")

@bot.command()
async def enable_user(ctx, member: discord.Member):
    """Re-enable a previously disabled user."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("You cannot use this command.")
        return
    disabled_users.discard(member.id)
    await ctx.send(f"{member} can now use the bot again.")

@bot.command()
async def broadcast(ctx, *, message):
    """Broadcast a message to all servers (Owner/Co-owner)."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("You cannot use this command.")
        return
    count = 0
    for guild in bot.guilds:
        for channel in guild.text_channels:
            try:
                await channel.send(message)
                count += 1
                break
            except:
                continue
    await ctx.send(f"Broadcast sent to {count} channels.")

@bot.command()
async def lock(ctx, channel: discord.TextChannel = None):
    """Lock a channel (Owner/Co-owner)."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("You cannot use this command.")
        return
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(f"{channel.mention} has been locked 🔒")

@bot.command()
async def unlock(ctx, channel: discord.TextChannel = None):
    """Unlock a channel (Owner/Co-owner)."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("You cannot use this command.")
        return
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(f"{channel.mention} has been unlocked 🔓")

@bot.command()
async def setbalance(ctx, member: discord.Member, amount: int):
    """Set a user's coins (Owner/Co-owner)."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("You cannot use this command.")
        return
    money_data[member.id] = amount
    await ctx.send(f"{member}'s balance set to {amount} coins.")

@bot.command()
async def dmall(ctx, *, message):
    """Send a DM to everyone in the server."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("You cannot use this command.")
        return
    sent = 0
    for member in ctx.guild.members:
        if not member.bot:
            try:
                await member.send(message)
                sent += 1
            except:
                continue
    await ctx.send(f"DM sent to {sent} members.")

@bot.command()
async def reroll_giveaway(ctx, guild_id: int):
    """Reroll the winner of a giveaway (Owner/Co-owner)."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("You cannot use this command.")
        return
    if guild_id not in giveaways:
        await ctx.send("No giveaway found for this server.")
        return
    data = giveaways[guild_id]
    if not data['entries']:
        await ctx.send("No entries to reroll.")
        return
    winner = random.choice(list(data['entries']))
    await data['channel'].send(f"🎉 New winner: {winner.mention}")
    await ctx.send("Giveaway rerolled successfully.")

@bot.command()
async def set_autorole(ctx, role: discord.Role):
    """Set the role given to new members automatically."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("You cannot use this command.")
        return
    global autorole_id
    autorole_id = role.id
    await ctx.send(f"Autorole set to {role.name}")

@bot.command()
async def invite_leaderboard(ctx):
    """Show invite leaderboard (Owner/Co-owner)."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("You cannot use this command.")
        return
    leaderboard = sorted(invite_data.items(), key=lambda x: x[1], reverse=True)[:10]
    embed = discord.Embed(title="Top Inviters", color=discord.Color.purple())
    for i, (user_id, count) in enumerate(leaderboard, 1):
        member = ctx.guild.get_member(user_id)
        if member:
            embed.add_field(name=f"{i}. {member}", value=f"Invites: {count}", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def clean_messages(ctx, keyword: str = None, limit: int = 100):
    """Advanced purge: delete messages containing keyword."""
    if not is_owner_or_co(ctx.author):
        await ctx.send("You cannot use this command.")
        return
    def check(m):
        return keyword.lower() in m.content.lower() if keyword else True
    deleted = await ctx.channel.purge(limit=limit, check=check)
    await ctx.send(f"Deleted {len(deleted)} messages.")
# ---------------- DM ALL COMMAND ----------------

@bot.command()
async def dmall(ctx, *, message):

    if not is_owner_or_co(ctx.author):
        await ctx.send("You cannot use this command.")
        return

    success = 0
    fail = 0

    for member in ctx.guild.members:

        if member.bot:
            continue

        try:
            await member.send(message)
            success += 1
        except:
            fail += 1

    await ctx.send(f"DM sent to {success} members. Failed: {fail}")


# ---------------- CHANNEL LOCK SYSTEM ----------------

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx, channel: discord.TextChannel = None):

    channel = channel or ctx.channel

    await channel.set_permissions(ctx.guild.default_role, send_messages=False)

    await ctx.send(f"🔒 {channel.mention} locked.")


@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, channel: discord.TextChannel = None):

    channel = channel or ctx.channel

    await channel.set_permissions(ctx.guild.default_role, send_messages=True)

    await ctx.send(f"🔓 {channel.mention} unlocked.")


# ---------------- BASIC UTILITY ----------------

@bot.command()
async def ping(ctx):

    latency = round(bot.latency * 1000)

    embed = discord.Embed(
        title="Pong!",
        description=f"Latency: **{latency}ms**",
        color=discord.Color.blue()
    )

    await ctx.send(embed=embed)


@bot.command()
async def avatar(ctx, member: discord.Member = None):

    member = member or ctx.author

    embed = discord.Embed(title=f"{member}'s Avatar")
    embed.set_image(url=member.display_avatar.url)

    await ctx.send(embed=embed)


# ---------------- SERVER INFO ----------------

@bot.command()
async def serverinfo(ctx):

    guild = ctx.guild

    embed = discord.Embed(
        title=guild.name,
        color=discord.Color.blurple()
    )

    embed.add_field(name="Members", value=guild.member_count)
    embed.add_field(name="Owner", value=guild.owner)
    embed.add_field(name="Created", value=guild.created_at.date())
    embed.add_field(name="Channels", value=len(guild.channels))

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    await ctx.send(embed=embed)


# ---------------- USER INFO ----------------

@bot.command()
async def userinfo(ctx, member: discord.Member = None):

    member = member or ctx.author

    embed = discord.Embed(
        title=f"User Info - {member}",
        color=discord.Color.green()
    )

    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Joined Server", value=member.joined_at.date())
    embed.add_field(name="Account Created", value=member.created_at.date())

    embed.set_thumbnail(url=member.display_avatar.url)

    await ctx.send(embed=embed)


# ---------------- MODERATION COMMANDS ----------------

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):

    try:
        await member.ban(reason=reason)

        await ctx.send(f"{member} has been banned.")

    except discord.Forbidden:
        await ctx.send("I cannot ban that member.")


@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):

    try:
        await member.kick(reason=reason)

        await ctx.send(f"{member} has been kicked.")

    except discord.Forbidden:
        await ctx.send("I cannot kick that member.")


@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):

    deleted = await ctx.channel.purge(limit=amount)

    await ctx.send(f"Deleted {len(deleted)} messages.", delete_after=5)


# ---------------- WARN SYSTEM ----------------

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No reason"):

    warn_data[member.id] = warn_data.get(member.id, 0) + 1

    await ctx.send(
        f"{member} warned.\nReason: {reason}\nTotal warns: {warn_data[member.id]}"
    )


@bot.command()
async def warns(ctx, member: discord.Member):

    count = warn_data.get(member.id, 0)

    await ctx.send(f"{member} has {count} warnings.")


# ---------------- TIMEOUT COMMAND ----------------

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int):

    until = discord.utils.utcnow() + timedelta(minutes=minutes)

    await member.timeout(until)

    await ctx.send(f"{member} timed out for {minutes} minutes.")


# ---------------- AUTOROLE COMMAND ----------------

@bot.command()
@commands.has_permissions(administrator=True)
async def autorole(ctx, role: discord.Role):

    global autorole_id

    autorole_id = role.id

    await ctx.send(f"Autorole set to {role.name}")
    
# ---------------- ECONOMY SYSTEM ----------------

@bot.command()
async def balance(ctx, member: discord.Member = None):

    member = member or ctx.author

    bal = money_data.get(member.id, 0)

    embed = discord.Embed(
        title="Balance",
        description=f"{member.mention} has **{bal} coins**",
        color=discord.Color.gold()
    )

    await ctx.send(embed=embed)


@bot.command()
async def daily(ctx):

    now = datetime.utcnow()

    last = daily_claimed.get(ctx.author.id)

    if last and now - last < timedelta(hours=24):

        remaining = timedelta(hours=24) - (now - last)

        await ctx.send(f"You already claimed daily.\nCome back in {remaining}.")
        return

    reward = random.randint(100, 300)

    money_data[ctx.author.id] = money_data.get(ctx.author.id, 0) + reward

    daily_claimed[ctx.author.id] = now

    await ctx.send(f"You received **{reward} coins**.")


@bot.command()
async def pay(ctx, member: discord.Member, amount: int):

    if amount <= 0:
        return

    sender_balance = money_data.get(ctx.author.id, 0)

    if sender_balance < amount:
        await ctx.send("You don't have enough coins.")
        return

    money_data[ctx.author.id] -= amount
    money_data[member.id] = money_data.get(member.id, 0) + amount

    await ctx.send(f"{ctx.author.mention} paid {member.mention} **{amount} coins**.")


# ---------------- LEADERBOARD ----------------

@bot.command()
async def leaderboard(ctx):

    top = sorted(money_data.items(), key=lambda x: x[1], reverse=True)[:10]

    embed = discord.Embed(
        title="💰 Richest Users",
        color=discord.Color.gold()
    )

    for i, (user_id, money) in enumerate(top, start=1):

        user = bot.get_user(user_id)

        if user:
            embed.add_field(name=f"{i}. {user}", value=f"{money} coins", inline=False)

    await ctx.send(embed=embed)


# ---------------- LEVEL COMMANDS ----------------

@bot.command()
async def rank(ctx, member: discord.Member = None):

    member = member or ctx.author

    user_xp = xp.get(member.id, 0)
    level = levels.get(member.id, 0)

    embed = discord.Embed(
        title=f"{member}'s Rank",
        color=discord.Color.blue()
    )

    embed.add_field(name="Level", value=level)
    embed.add_field(name="XP", value=user_xp)

    await ctx.send(embed=embed)


@bot.command()
async def levels(ctx):

    top = sorted(levels.items(), key=lambda x: x[1], reverse=True)[:10]

    embed = discord.Embed(
        title="🏆 Level Leaderboard",
        color=discord.Color.green()
    )

    for i, (user_id, lvl) in enumerate(top, start=1):

        user = bot.get_user(user_id)

        if user:
            embed.add_field(name=f"{i}. {user}", value=f"Level {lvl}", inline=False)

    await ctx.send(embed=embed)


# ---------------- INVITE LEADERBOARD ----------------

@bot.command()
async def invites(ctx, member: discord.Member = None):

    member = member or ctx.author

    count = invite_data.get(member.id, 0)

    await ctx.send(f"{member.mention} has **{count} invites**.")


@bot.command()
async def inviteleaderboard(ctx):

    top = sorted(invite_data.items(), key=lambda x: x[1], reverse=True)[:10]

    embed = discord.Embed(
        title="📨 Invite Leaderboard",
        color=discord.Color.orange()
    )

    for i, (user_id, count) in enumerate(top, start=1):

        user = bot.get_user(user_id)

        if user:
            embed.add_field(name=f"{i}. {user}", value=f"{count} invites", inline=False)

    await ctx.send(embed=embed)


# ---------------- GAMBLING COMMANDS ----------------

@bot.command()
async def coinflip(ctx, bet: int):

    if bet <= 0:
        return

    balance = money_data.get(ctx.author.id, 0)

    if balance < bet:
        await ctx.send("You don't have enough coins.")
        return

    result = random.choice(["win", "lose"])

    if result == "win":

        money_data[ctx.author.id] += bet

        await ctx.send(f"🪙 You won **{bet} coins**!")

    else:

        money_data[ctx.author.id] -= bet

        await ctx.send(f"You lost **{bet} coins**.")


@bot.command()
async def dice(ctx, bet: int):

    if bet <= 0:
        return

    balance = money_data.get(ctx.author.id, 0)

    if balance < bet:
        await ctx.send("Not enough coins.")
        return

    roll = random.randint(1, 6)

    if roll >= 4:

        winnings = bet * 2

        money_data[ctx.author.id] += winnings

        await ctx.send(f"🎲 You rolled **{roll}** and won **{winnings} coins**!")

    else:

        money_data[ctx.author.id] -= bet

        await ctx.send(f"You rolled **{roll}** and lost **{bet} coins**.")


# ---------------- ROB COMMAND ----------------

@bot.command()
async def rob(ctx, member: discord.Member):

    if member.id == ctx.author.id:
        return

    target_balance = money_data.get(member.id, 0)

    if target_balance <= 0:
        await ctx.send("That user has no money.")
        return

    success = random.choice([True, False])

    if success:

        amount = random.randint(10, min(200, target_balance))

        money_data[member.id] -= amount
        money_data[ctx.author.id] = money_data.get(ctx.author.id, 0) + amount

        await ctx.send(f"💰 You stole **{amount} coins** from {member.mention}!")

    else:

        penalty = random.randint(10, 100)

        money_data[ctx.author.id] = max(0, money_data.get(ctx.author.id, 0) - penalty)

        await ctx.send(f"You got caught and lost **{penalty} coins**.")


# ---------------- BLACKJACK SYSTEM ----------------

def calculate_hand(hand):

    total = sum(hand)

    while total > 21 and 11 in hand:
        hand[hand.index(11)] = 1
        total = sum(hand)

    return total


@bot.command()
async def blackjack(ctx, bet: int):

    if ctx.author.id in blackjack_games:
        await ctx.send("You are already playing blackjack.")
        return

    balance = money_data.get(ctx.author.id, 0)

    if balance < bet:
        await ctx.send("Not enough coins.")
        return

    deck = [2,3,4,5,6,7,8,9,10,10,10,10,11]*4
    random.shuffle(deck)

    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]

    blackjack_games[ctx.author.id] = {
        "deck": deck,
        "player": player,
        "dealer": dealer,
        "bet": bet
    }

    await ctx.send(
        f"🃏 Blackjack started!\nYour hand: {player} (Total {calculate_hand(player)})\nDealer shows: {dealer[0]}"
    )


@bot.command()
async def hit(ctx):

    game = blackjack_games.get(ctx.author.id)

    if not game:
        await ctx.send("You are not playing blackjack.")
        return

    card = game["deck"].pop()
    game["player"].append(card)

    total = calculate_hand(game["player"])

    if total > 21:

        money_data[ctx.author.id] -= game["bet"]

        del blackjack_games[ctx.author.id]

        await ctx.send(f"You drew {card}. Bust! You lost {game['bet']} coins.")

    else:

        await ctx.send(f"You drew {card}. Total is now {total}.")


@bot.command()
async def stand(ctx):

    game = blackjack_games.get(ctx.author.id)

    if not game:
        await ctx.send("You are not playing blackjack.")
        return

    dealer = game["dealer"]
    deck = game["deck"]

    while calculate_hand(dealer) < 17:
        dealer.append(deck.pop())

    player_total = calculate_hand(game["player"])
    dealer_total = calculate_hand(dealer)

    bet = game["bet"]

    if dealer_total > 21 or player_total > dealer_total:

        money_data[ctx.author.id] += bet

        result = "You win!"

    elif dealer_total == player_total:

        result = "It's a tie."

    else:

        money_data[ctx.author.id] -= bet

        result = "You lose."

    del blackjack_games[ctx.author.id]

    await ctx.send(
        f"Dealer hand: {dealer} ({dealer_total})\nYour hand: {game['player']} ({player_total})\n{result}"
    )
    
# ---------------- GIVEAWAY SYSTEM ----------------

@bot.command()
@commands.has_permissions(manage_guild=True)
async def giveaway(ctx, minutes: int, *, prize):

    embed = discord.Embed(
        title="🎉 GIVEAWAY",
        description=f"Prize: **{prize}**\nReact with 🎉 to enter!\nEnds in **{minutes} minutes**",
        color=discord.Color.gold()
    )

    message = await ctx.send(embed=embed)
    await message.add_reaction("🎉")

    giveaways[message.id] = {
        "prize": prize,
        "end": datetime.utcnow() + timedelta(minutes=minutes),
        "channel": ctx.channel.id
    }


@bot.command()
@commands.has_permissions(manage_guild=True)
async def reroll(ctx, message_id: int):

    try:
        message = await ctx.channel.fetch_message(message_id)
    except:
        await ctx.send("Giveaway message not found.")
        return

    reaction = discord.utils.get(message.reactions, emoji="🎉")

    if not reaction:
        await ctx.send("No entries found.")
        return

    users = [user async for user in reaction.users() if not user.bot]

    if not users:
        await ctx.send("No valid participants.")
        return

    winner = random.choice(users)

    await ctx.send(f"🎉 New winner: {winner.mention}!")


# ---------------- POLL COMMAND ----------------

@bot.command()
async def poll(ctx, question, option1, option2):

    embed = discord.Embed(
        title="📊 Poll",
        description=question,
        color=discord.Color.blue()
    )

    embed.add_field(name="👍 Option 1", value=option1)
    embed.add_field(name="👎 Option 2", value=option2)

    message = await ctx.send(embed=embed)

    await message.add_reaction("👍")
    await message.add_reaction("👎")


# ---------------- SAY COMMAND ----------------

@bot.command()
@commands.has_permissions(manage_messages=True)
async def say(ctx, *, message):

    await ctx.message.delete()

    await ctx.send(message)


# ---------------- CLIP COMMAND ----------------

@bot.command()
async def clip(ctx, message_id: int):

    try:
        message = await ctx.channel.fetch_message(message_id)
    except:
        await ctx.send("Message not found.")
        return

    embed = discord.Embed(
        title="📌 Message Clip",
        description=message.content,
        color=discord.Color.orange()
    )

    embed.add_field(name="Author", value=message.author)
    embed.add_field(name="Time", value=message.created_at)

    await ctx.author.send(embed=embed)

    await ctx.send("Message clipped to your DMs.")


# ---------------- TICKET SYSTEM ----------------

tickets = {}

@bot.command()
async def ticket(ctx):

    category = discord.utils.get(ctx.guild.categories, name="Tickets")

    if not category:

        category = await ctx.guild.create_category("Tickets")

    overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        ctx.author: discord.PermissionOverwrite(read_messages=True)
    }

    channel = await ctx.guild.create_text_channel(
        name=f"ticket-{ctx.author.name}",
        category=category,
        overwrites=overwrites
    )

    tickets[channel.id] = ctx.author.id

    await channel.send(f"{ctx.author.mention} your ticket has been created.")
    await ctx.send(f"Ticket created: {channel.mention}")


@bot.command()
async def closeticket(ctx):

    if ctx.channel.id not in tickets:
        return

    await ctx.send("Closing ticket...")

    await ctx.channel.delete()


# ---------------- REACTION ROLES ----------------

reaction_roles = {}

@bot.command()
@commands.has_permissions(manage_roles=True)
async def reactionrole(ctx, message_id: int, emoji, role: discord.Role):

    try:
        message = await ctx.channel.fetch_message(message_id)
    except:
        await ctx.send("Message not found.")
        return

    await message.add_reaction(emoji)

    reaction_roles[(message.id, emoji)] = role.id

    await ctx.send("Reaction role added.")


@bot.event
async def on_raw_reaction_add(payload):

    key = (payload.message_id, str(payload.emoji))

    if key not in reaction_roles:
        return

    guild = bot.get_guild(payload.guild_id)
    role = guild.get_role(reaction_roles[key])
    member = guild.get_member(payload.user_id)

    if member and role:
        await member.add_roles(role)


@bot.event
async def on_raw_reaction_remove(payload):

    key = (payload.message_id, str(payload.emoji))

    if key not in reaction_roles:
        return

    guild = bot.get_guild(payload.guild_id)
    role = guild.get_role(reaction_roles[key])
    member = guild.get_member(payload.user_id)

    if member and role:
        await member.remove_roles(role)


# ---------------- FUN COMMANDS ----------------

@bot.command()
async def hug(ctx, member: discord.Member):

    await ctx.send(f"{ctx.author.mention} hugs {member.mention} 🤗")


@bot.command()
async def slap(ctx, member: discord.Member):

    await ctx.send(f"{ctx.author.mention} slaps {member.mention} 👋")


@bot.command()
async def joke(ctx):

    jokes = [
        "Why did the computer go to therapy? Too many bytes of trauma.",
        "Why don't programmers like nature? Too many bugs.",
        "Why did the bot cross the road? To process the other side."
    ]

    await ctx.send(random.choice(jokes))
    
# ---------------- GIVEAWAY CHECKER ----------------

@tasks.loop(seconds=30)
async def check_giveaways():

    now = datetime.utcnow()

    finished = []

    for message_id, data in giveaways.items():

        if now >= data["end"]:

            channel = bot.get_channel(data["channel"])

            try:
                message = await channel.fetch_message(message_id)
            except:
                finished.append(message_id)
                continue

            reaction = discord.utils.get(message.reactions, emoji="🎉")

            if not reaction:
                await channel.send("No one entered the giveaway.")
                finished.append(message_id)
                continue

            users = [user async for user in reaction.users() if not user.bot]

            if not users:
                await channel.send("No valid participants.")
                finished.append(message_id)
                continue

            winner = random.choice(users)

            await channel.send(
                f"🎉 Giveaway ended!\nPrize: **{data['prize']}**\nWinner: {winner.mention}"
            )

            finished.append(message_id)

    for m in finished:
        giveaways.pop(m, None)


# ---------------- SCHEDULED MESSAGE SYSTEM ----------------

@bot.command()
@commands.has_permissions(manage_guild=True)
async def schedule(ctx, minutes: int, *, message):

    send_time = datetime.utcnow() + timedelta(minutes=minutes)

    scheduled_messages.append({
        "channel": ctx.channel.id,
        "time": send_time,
        "message": message
    })

    await ctx.send(f"Message scheduled in **{minutes} minutes**.")


@tasks.loop(seconds=20)
async def check_scheduled_messages():

    now = datetime.utcnow()

    for msg in scheduled_messages[:]:

        if now >= msg["time"]:

            channel = bot.get_channel(msg["channel"])

            if channel:
                await channel.send(msg["message"])

            scheduled_messages.remove(msg)


# ---------------- SERVER STATS ----------------

@bot.command()
async def serverstats(ctx):

    guild = ctx.guild

    humans = len([m for m in guild.members if not m.bot])
    bots = len([m for m in guild.members if m.bot])

    embed = discord.Embed(
        title="Server Statistics",
        color=discord.Color.blue()
    )

    embed.add_field(name="Total Members", value=guild.member_count)
    embed.add_field(name="Humans", value=humans)
    embed.add_field(name="Bots", value=bots)
    embed.add_field(name="Channels", value=len(guild.channels))
    embed.add_field(name="Roles", value=len(guild.roles))

    await ctx.send(embed=embed)


# ---------------- HELP COMMAND ----------------

@bot.command()
async def help(ctx):

    embed = discord.Embed(
        title="Bot Commands",
        description="List of available commands",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="Moderation",
        value="ban, kick, purge, warn, timeout, lock, unlock",
        inline=False
    )

    embed.add_field(
        name="Economy",
        value="balance, daily, pay, leaderboard, rob",
        inline=False
    )

    embed.add_field(
        name="Games",
        value="blackjack, hit, stand, coinflip, dice",
        inline=False
    )

    embed.add_field(
        name="Levels",
        value="rank, levels",
        inline=False
    )

    embed.add_field(
        name="Invites",
        value="invites, inviteleaderboard",
        inline=False
    )

    embed.add_field(
        name="Server",
        value="serverinfo, userinfo, serverstats, autorole",
        inline=False
    )

    embed.add_field(
        name="Fun",
        value="hug, slap, joke, poll",
        inline=False
    )

    embed.add_field(
        name="Utilities",
        value="say, clip, avatar, ping",
        inline=False
    )

    embed.add_field(
        name="Giveaways",
        value="giveaway, reroll",
        inline=False
    )

    embed.add_field(
        name="Tickets",
        value="ticket, closeticket",
        inline=False
    )

    await ctx.send(embed=embed)


# ---------------- INVITE REFRESH ----------------

@tasks.loop(minutes=5)
async def refresh_invites():

    for guild in bot.guilds:

        invites = await guild.invites()

        invite_cache[guild.id] = {invite.code: invite.uses for invite in invites}


# ---------------- STARTUP ----------------

@bot.event
async def setup_hook():

    check_scheduled_messages.start()
    refresh_invites.start()


# ---------------- ERROR HANDLER ----------------

@bot.event
async def on_command_error(ctx, error):

    if isinstance(error, commands.MissingPermissions):

        await ctx.send("You do not have permission to use this command.")

    elif isinstance(error, commands.MissingRequiredArgument):

        await ctx.send("Missing arguments for this command.")

    else:
        print(error)


# ---------------- BOT RUN ----------------

bot.run(TOKEN)
