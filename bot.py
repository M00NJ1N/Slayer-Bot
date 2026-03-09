import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import random
from datetime import datetime, timedelta

# ----------------- CONFIG -----------------
OWNER_IDS = {1169273992289456341, 958273785037983754}  # Owner IDs
MY_ID = 1169273992289456341  # Your ID for special privileges
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("No bot token found! Set the TOKEN environment variable!")

COMMAND_PREFIX = "!"
DEFAULT_ROLE_NAME = "Member"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)
tree = bot.tree  # For slash commands

# ----------------- DATABASE SIMULATION -----------------
xp_data = {}
money_data = {}
warn_data = {}
disabled_users = set()
scheduled_messages = []

# ----------------- HELP COMMAND -----------------
@bot.command()
async def help(ctx):
    embed = discord.Embed(title="Help - Command List", color=discord.Color.blue())
    embed.add_field(name="Moderation",
                    value="ban, kick, timeout, softban, warn, purge, lock, unlock, roleall", inline=False)
    embed.add_field(name="Economy",
                    value="balance, setbalance, pay, daily, leaderboard", inline=False)
    embed.add_field(name="Fun/Games",
                    value="coinflip, roll, hug, slap, kiss, crime, loot, quest, duel, catch, blackjack, trivia", inline=False)
    embed.add_field(name="Utility",
                    value="userinfo, serverinfo, avatar, say, ping, clip, schedule", inline=False)
    embed.add_field(name="Giveaways",
                    value="giveaway", inline=False)
    embed.add_field(name="Owner Only",
                    value="shutdown, disablebot, broadcast", inline=False)
    await ctx.send(embed=embed)

# ----------------- EVENTS -----------------
@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    if not giveaway_loop.is_running():
        giveaway_loop.start()
    try:
        await tree.sync()
    except:
        print("Slash commands failed to sync.")

@bot.event
async def on_member_join(member):
    # Auto-role
    role = discord.utils.get(member.guild.roles, name=DEFAULT_ROLE_NAME)
    if role:
        try:
            await member.add_roles(role)
        except:
            pass
    # Initialize stats
    xp_data[member.id] = 0
    money_data[member.id] = 100
    warn_data[member.id] = 0

@bot.event
async def on_message(message):
    if message.author.bot or message.author.id in disabled_users:
        return
    # XP
    xp_data[message.author.id] = xp_data.get(message.author.id, 0) + random.randint(5, 15)
    await bot.process_commands(message)

# ----------------- MODERATION -----------------
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, days: int = 0, *, reason=None):
    try:
        await member.ban(delete_message_days=days, reason=reason)
        await ctx.send(f"{member} banned. Reason: {reason}")
    except:
        await ctx.send("Cannot ban this member.")

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"{member} kicked. Reason: {reason}")
    except:
        await ctx.send("Cannot kick this member.")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int, *, reason=None):
    try:
        until = datetime.utcnow() + timedelta(minutes=minutes)
        await member.timeout(until, reason=reason)
        await ctx.send(f"{member} timed out for {minutes} minutes. Reason: {reason}")
    except:
        await ctx.send("Cannot timeout this member.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, limit: int):
    deleted = await ctx.channel.purge(limit=limit)
    await ctx.send(f"Deleted {len(deleted)} messages.", delete_after=5)

@bot.command()
@commands.has_permissions(administrator=True)
async def warn(ctx, member: discord.Member, *, reason=None):
    warn_data[member.id] = warn_data.get(member.id, 0) + 1
    await ctx.send(f"{member} warned. Total warns: {warn_data[member.id]} Reason: {reason}")

@bot.command()
@commands.has_permissions(administrator=True)
async def lock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(f"{channel.mention} is now locked.")

@bot.command()
@commands.has_permissions(administrator=True)
async def unlock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(f"{channel.mention} is now unlocked.")

@bot.command()
@commands.has_permissions(administrator=True)
async def roleall(ctx, role: discord.Role):
    count = 0
    for member in ctx.guild.members:
        if not role in member.roles:
            try:
                await member.add_roles(role)
                count += 1
            except:
                pass
    await ctx.send(f"Added {role} to {count} members.")

# ----------------- OWNER ONLY -----------------
def is_owner(ctx):
    return ctx.author.id in OWNER_IDS

@bot.command()
async def shutdown(ctx):
    if not is_owner(ctx) or ctx.author.id == MY_ID:
        await ctx.send("You cannot shutdown the bot.")
        return
    await ctx.send("Shutting down...")
    await bot.close()

@bot.command()
async def disablebot(ctx, member: discord.Member):
    if not is_owner(ctx) or member.id == MY_ID:
        await ctx.send("Cannot disable bot for this user.")
        return
    disabled_users.add(member.id)
    await ctx.send(f"{member} is now disabled from using the bot.")

@bot.command()
async def broadcast(ctx, *, message):
    if not is_owner(ctx):
        return
    sent = 0
    for guild in bot.guilds:
        try:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    await channel.send(message)
                    sent += 1
                    break
        except:
            continue
    await ctx.send(f"Message broadcasted to {sent} channels.")

# ----------------- AUTOROLE COMMAND -----------------
@bot.command()
@commands.has_permissions(administrator=True)
async def setautorole(ctx, role: discord.Role):
    global DEFAULT_ROLE_NAME
    DEFAULT_ROLE_NAME = role.name
    await ctx.send(f"Auto-role set to {role.name}.")

# ----------------- ECONOMY -----------------
@bot.command()
async def balance(ctx, member: discord.Member = None):
    member = member or ctx.author
    bal = money_data.get(member.id, 0)
    await ctx.send(f"{member} has {bal} coins.")

@bot.command()
@commands.has_permissions(administrator=True)
async def setbalance(ctx, member: discord.Member, amount: int):
    money_data[member.id] = amount
    await ctx.send(f"{member}'s balance set to {amount} coins.")

@bot.command()
async def pay(ctx, member: discord.Member, amount: int):
    sender = ctx.author
    if money_data.get(sender.id, 0) < amount:
        await ctx.send("Not enough coins!")
        return
    money_data[sender.id] -= amount
    money_data[member.id] = money_data.get(member.id, 0) + amount
    await ctx.send(f"{sender} paid {member} {amount} coins.")

@bot.command()
async def daily(ctx):
    user = ctx.author
    coins = random.randint(50, 200)
    money_data[user.id] = money_data.get(user.id, 0) + coins
    await ctx.send(f"{user} collected {coins} coins today!")

@bot.command()
async def leaderboard(ctx):
    sorted_users = sorted(money_data.items(), key=lambda x: x[1], reverse=True)
    desc = "\n".join([f"<@{uid}> - {bal} coins" for uid, bal in sorted_users[:10]])
    await ctx.send(f"**Leaderboard**\n{desc}")

# ----------------- FUN -----------------
@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! {round(bot.latency*1000)}ms")

@bot.command()
async def coinflip(ctx):
    await ctx.send(random.choice([f"{ctx.author.mention} flipped Heads!", f"{ctx.author.mention} flipped Tails!"]))

@bot.command()
async def roll(ctx, sides: int = 6):
    await ctx.send(f"{ctx.author.mention} rolled a {random.randint(1, sides)}")

@bot.command()
async def hug(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"{ctx.author.mention} hugs {member.mention} 🤗")

@bot.command()
async def slap(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"{ctx.author.mention} slaps {member.mention} 👋")

@bot.command()
async def say(ctx, *, text):
    await ctx.send(text)

@bot.command()
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(member.display_avatar.url)

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

@tasks.loop(seconds=30)
async def giveaway_loop():
    to_remove = []
    for guild_id, data in giveaways.items():
        if datetime.utcnow() >= data["end"]:
            channel = data["channel"]
            if data["entries"]:
                winner = random.choice(list(data["entries"]))
                await channel.send(f"🎉 Giveaway for **{data['prize']}** ended! Winner: {winner.mention}")
            else:
                await channel.send(f"Giveaway for **{data['prize']}** ended with no entries.")
            to_remove.append(guild_id)
    for guild_id in to_remove:
        giveaways.pop(guild_id, None)

@bot.event
async def on_reaction_add(reaction, user):
    if reaction.emoji == "🎉" and not user.bot:
        for data in giveaways.values():
            if data["channel"].id == reaction.message.channel.id:
                data["entries"].add(user)

# ----------------- RUN BOT -----------------
bot.run(TOKEN)
