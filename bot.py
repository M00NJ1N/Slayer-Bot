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
OWNER_IDS = [1169273992289456341, 958273785037983754]  # bot owner IDs

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# ----------------- DATABASE SIMULATION -----------------
xp_data = {}
money_data = {}
warn_data = {}
disabled_users = set()
giveaways = {}

# ----------------- LOGGING -----------------
async def log_event(message):
    log_channel = discord.utils.get(message.guild.text_channels, name="bot-logs")
    if not log_channel:
        log_channel = await message.guild.create_text_channel("bot-logs")
    await log_channel.send(f"[{datetime.utcnow()}] {message.author} used: {message.content}")

async def log_action(guild, description):
    log_channel = discord.utils.get(guild.text_channels, name="bot-logs")
    if not log_channel:
        log_channel = await guild.create_text_channel("bot-logs")
    await log_channel.send(f"[{datetime.utcnow()}] {description}")

# ----------------- EVENTS -----------------
@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    if not giveaway_loop.is_running():
        giveaway_loop.start()

@bot.event
async def on_member_join(member):
    # autorole
    role = discord.utils.get(member.guild.roles, name=DEFAULT_ROLE_NAME)
    if role:
        try:
            await member.add_roles(role)
            await log_action(member.guild, f"Autorole: Added {DEFAULT_ROLE_NAME} to {member}")
        except discord.Forbidden:
            pass
    # initialize xp and money
    xp_data[member.id] = 0
    money_data[member.id] = 100
    warn_data[member.id] = 0

@bot.event
async def on_message(message):
    if message.author.bot or message.author.id in disabled_users:
        return
    xp_data[message.author.id] = xp_data.get(message.author.id, 0) + random.randint(5, 15)
    await log_event(message)
    await bot.process_commands(message)

# ----------------- MODERATION -----------------
@bot.command()
@commands.has_permissions(administrator=True)
async def autorole(ctx, role: discord.Role = None):
    global DEFAULT_ROLE_NAME
    DEFAULT_ROLE_NAME = role.name if role else DEFAULT_ROLE_NAME
    await ctx.send(f"Autorole set to: {DEFAULT_ROLE_NAME}")

@bot.command()
@commands.has_permissions(administrator=True)
async def roleall(ctx, role: discord.Role):
    success = 0
    for member in ctx.guild.members:
        if not member.bot:
            try:
                await member.add_roles(role)
                success += 1
            except:
                pass
    await ctx.send(f"Added {role} to {success} members")
    await log_action(ctx.guild, f"RoleAll: {ctx.author} added {role} to {success} members")

@bot.command()
@commands.has_permissions(administrator=True)
async def lock(ctx):
    for channel in ctx.guild.text_channels:
        await channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("Server channels locked.")
    await log_action(ctx.guild, f"{ctx.author} locked all channels")

@bot.command()
@commands.has_permissions(administrator=True)
async def unlock(ctx):
    for channel in ctx.guild.text_channels:
        await channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send("Server channels unlocked.")
    await log_action(ctx.guild, f"{ctx.author} unlocked all channels")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, days: int = 0, *, reason=None):
    try:
        await member.ban(reason=reason, delete_message_days=days)
        await ctx.send(f"{member} banned. Reason: {reason}")
        await log_action(ctx.guild, f"{ctx.author} banned {member} (reason: {reason}, days: {days})")
    except discord.Forbidden:
        await ctx.send("Cannot ban member.")

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"{member} kicked. Reason: {reason}")
        await log_action(ctx.guild, f"{ctx.author} kicked {member} (reason: {reason})")
    except discord.Forbidden:
        await ctx.send("Cannot kick member.")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int, *, reason=None):
    until = datetime.utcnow() + timedelta(minutes=minutes)
    try:
        await member.timeout(until, reason=reason)
        await ctx.send(f"{member} timed out for {minutes} minutes")
        await log_action(ctx.guild, f"{ctx.author} timed out {member} for {minutes} minutes (reason: {reason})")
    except discord.Forbidden:
        await ctx.send("Cannot timeout member.")

@bot.command()
@commands.has_permissions(administrator=True)
async def warn(ctx, member: discord.Member, *, reason=None):
    warn_data[member.id] = warn_data.get(member.id, 0) + 1
    await ctx.send(f"{member} warned. Total warns: {warn_data[member.id]}")
    await log_action(ctx.guild, f"{ctx.author} warned {member} (reason: {reason})")

# ----------------- OWNER ONLY -----------------
def is_owner(ctx):
    return ctx.author.id in OWNER_IDS

@bot.command()
@commands.check(is_owner)
async def disablebot(ctx, member: discord.Member):
    if ctx.author.id == 958273785037983754 and member.id == 1169273992289456341:
        await ctx.send("You cannot disable the bot for the main owner.")
        return
    disabled_users.add(member.id)
    await ctx.send(f"{member} disabled from using the bot")
    await log_action(ctx.guild, f"{ctx.author} disabled bot for {member}")

@bot.command()
@commands.check(is_owner)
async def enablebot(ctx, member: discord.Member):
    disabled_users.discard(member.id)
    await ctx.send(f"{member} can now use the bot")
    await log_action(ctx.guild, f"{ctx.author} enabled bot for {member}")

@bot.command()
@commands.check(is_owner)
async def shutdown(ctx):
    await ctx.send("Shutting down bot...")
    await log_action(ctx.guild, f"{ctx.author} shut down the bot")
    await bot.close()

@bot.command()
@commands.check(is_owner)
async def broadcast(ctx, *, message):
    for guild in bot.guilds:
        try:
            await guild.system_channel.send(message)
        except:
            pass
    await ctx.send("Broadcast sent to all servers.")
    await log_action(ctx.guild, f"{ctx.author} broadcasted: {message}")

# ----------------- ECONOMY -----------------
@bot.command()
async def balance(ctx, member: discord.Member = None):
    member = member or ctx.author
    bal = money_data.get(member.id, 0)
    await ctx.send(f"{member} has {bal} coins")

@bot.command()
@commands.check(is_owner)
async def setbalance(ctx, member: discord.Member, amount: int):
    money_data[member.id] = amount
    await ctx.send(f"{member}'s balance set to {amount}")
    await log_action(ctx.guild, f"{ctx.author} set {member}'s balance to {amount}")

# ----------------- XP & LEVELS -----------------
@bot.command()
async def level(ctx, member: discord.Member = None):
    member = member or ctx.author
    xp = xp_data.get(member.id, 0)
    lvl = xp // 100
    await ctx.send(f"{member} is level {lvl} with {xp} XP")

# ----------------- GIVEAWAYS -----------------
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

# ----------------- FUN COMMANDS -----------------
@bot.command()
async def coinflip(ctx):
    await ctx.send(f"🪙 {ctx.author.mention} flipped {random.choice(['Heads','Tails'])}")

@bot.command()
async def roll(ctx, sides: int = 6):
    await ctx.send(f"{ctx.author.mention} rolled a {sides}-sided dice: {random.randint(1, sides)}")

@bot.command()
async def hug(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"{ctx.author.mention} hugs {member.mention} 🤗")

@bot.command()
async def say(ctx, *, text):
    await ctx.send(text)

# ----------------- CLIP COMMAND -----------------
@bot.command()
async def clip(ctx, message: discord.Message):
    info = f"Author: {message.author}\nTime: {message.created_at}\nContent: {message.content}"
    await ctx.author.send(f"Clipped message:\n{info}")
    await ctx.send("Message clipped and sent to your DMs.")

# ----------------- RUN BOT -----------------
bot.run(TOKEN)
