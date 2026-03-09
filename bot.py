import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import random
from datetime import datetime, timedelta

# ----------------- CONFIG -----------------
TOKEN = os.getenv("TOKEN")  # Railway: add TOKEN as an environment variable
OWNER_ID = 1169273992289456341
COMMAND_PREFIX = "!"
DEFAULT_ROLE_NAME = "Member"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)
tree = bot.tree  # For slash commands

# ----------------- DATABASE SIMULATION -----------------
xp_data = {}
money_data = {}
warn_data = {}
disabled_users = set()  # Users disabled from bot commands

# ----------------- UTILITIES -----------------
def is_owner(user):
    return user.id == OWNER_ID

def is_disabled(user):
    return user.id in disabled_users

async def check_disabled(ctx):
    if is_disabled(ctx.author):
        await ctx.send("You are blocked from using this bot!")
        return True
    return False

# ----------------- EVENTS -----------------
@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    if not giveaway_loop.is_running():
        giveaway_loop.start()
    try:
        synced = await tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Slash command sync error: {e}")

@bot.event
async def on_member_join(member):
    # Autorole
    role = discord.utils.get(member.guild.roles, name=DEFAULT_ROLE_NAME)
    if role:
        try:
            await member.add_roles(role)
        except discord.Forbidden:
            pass
    # Initialize economy/xp/warns
    xp_data[member.id] = 0
    money_data[member.id] = 100
    warn_data[member.id] = 0

@bot.event
async def on_message(message):
    if message.author.bot or is_disabled(message.author):
        return
    # XP gain
    xp_data[message.author.id] = xp_data.get(message.author.id, 0) + random.randint(5, 15)
    await bot.process_commands(message)

# ----------------- MODERATION -----------------
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, days: int = 0, *, reason=None):
    if await check_disabled(ctx): return
    try:
        await member.ban(reason=reason, delete_message_days=days)
        await ctx.send(f"{member} was banned. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send("I do not have permission to ban that member.")

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    if await check_disabled(ctx): return
    try:
        await member.kick(reason=reason)
        await ctx.send(f"{member} was kicked. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send("I cannot kick that member.")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int, *, reason=None):
    if await check_disabled(ctx): return
    try:
        until = datetime.utcnow() + timedelta(minutes=minutes)
        await member.timeout(until, reason=reason)
        await ctx.send(f"{member} timed out for {minutes} minutes. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send("I cannot timeout that member.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, limit: int):
    if await check_disabled(ctx): return
    deleted = await ctx.channel.purge(limit=limit)
    await ctx.send(f"Deleted {len(deleted)} messages.", delete_after=5)

@bot.command()
@commands.has_permissions(ban_members=True)
async def softban(ctx, member: discord.Member, *, reason=None):
    if await check_disabled(ctx): return
    try:
        await member.ban(reason=reason, delete_message_days=7)
        await member.unban(reason="Softban completed")
        await ctx.send(f"{member} was softbanned.")
    except discord.Forbidden:
        await ctx.send("Cannot softban this member.")

@bot.command()
@commands.has_permissions(administrator=True)
async def warn(ctx, member: discord.Member, *, reason=None):
    if await check_disabled(ctx): return
    warn_data[member.id] = warn_data.get(member.id, 0) + 1
    await ctx.send(f"{member} warned. Total warns: {warn_data[member.id]} Reason: {reason}")

@bot.command()
@commands.has_permissions(administrator=True)
async def roleall(ctx, role: discord.Role):
    if await check_disabled(ctx): return
    success = 0
    for member in ctx.guild.members:
        try:
            await member.add_roles(role)
            success += 1
        except:
            pass
    await ctx.send(f"Added role {role.name} to {success} members.")

@bot.command()
@commands.has_permissions(administrator=True)
async def lock(ctx, channel: discord.TextChannel = None):
    if await check_disabled(ctx): return
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(f"{channel.mention} has been locked.")

@bot.command()
@commands.has_permissions(administrator=True)
async def unlock(ctx, channel: discord.TextChannel = None):
    if await check_disabled(ctx): return
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(f"{channel.mention} has been unlocked.")

# ----------------- OWNER ONLY COMMANDS -----------------
@bot.command()
async def disablebot(ctx, member: discord.Member):
    if ctx.author.id != OWNER_ID: return
    disabled_users.add(member.id)
    await ctx.send(f"{member} is now blocked from using the bot.")

@bot.command()
async def enablebot(ctx, member: discord.Member):
    if ctx.author.id != OWNER_ID: return
    disabled_users.discard(member.id)
    await ctx.send(f"{member} can now use the bot again.")

@bot.command()
async def shutdown(ctx):
    if ctx.author.id != OWNER_ID: return
    await ctx.send("Shutting down...")
    await bot.close()

@bot.command()
async def broadcast(ctx, *, message):
    if ctx.author.id != OWNER_ID: return
    for guild in bot.guilds:
        for channel in guild.text_channels:
            try:
                await channel.send(message)
            except:
                continue
    await ctx.send("Broadcast complete.")

# ----------------- ECONOMY -----------------
@bot.command()
async def balance(ctx, member: discord.Member = None):
    if await check_disabled(ctx): return
    member = member or ctx.author
    bal = money_data.get(member.id, 0)
    await ctx.send(f"{member} has {bal} coins.")

@bot.command()
async def daily(ctx):
    if await check_disabled(ctx): return
    user = ctx.author
    coins = random.randint(50, 200)
    money_data[user.id] = money_data.get(user.id, 0) + coins
    await ctx.send(f"{user} collected {coins} coins today!")

@bot.command()
async def pay(ctx, member: discord.Member, amount: int):
    if await check_disabled(ctx): return
    sender = ctx.author
    if money_data.get(sender.id, 0) < amount:
        await ctx.send("Not enough coins!")
        return
    money_data[sender.id] -= amount
    money_data[member.id] = money_data.get(member.id, 0) + amount
    await ctx.send(f"{sender} paid {member} {amount} coins.")

@bot.command()
@commands.has_permissions(administrator=True)
async def setbalance(ctx, member: discord.Member, amount: int):
    if await check_disabled(ctx): return
    money_data[member.id] = amount
    await ctx.send(f"{member}'s balance is now set to {amount} coins.")

# ----------------- FUN COMMANDS -----------------
@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! {round(bot.latency*1000)}ms")

@bot.command()
async def coinflip(ctx):
    if await check_disabled(ctx): return
    await ctx.send(f"🪙 {ctx.author.mention} flipped {random.choice(['Heads','Tails'])}")

@bot.command()
async def roll(ctx, sides: int = 6):
    if await check_disabled(ctx): return
    await ctx.send(f"{ctx.author.mention} rolled a {sides}-sided dice: {random.randint(1, sides)}")

@bot.command()
async def hug(ctx, member: discord.Member = None):
    if await check_disabled(ctx): return
    member = member or ctx.author
    await ctx.send(f"{ctx.author.mention} hugs {member.mention} 🤗")

# ----------------- RUN BOT -----------------
bot.run(TOKEN)
