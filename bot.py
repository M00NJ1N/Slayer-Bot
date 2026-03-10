import os
import discord
from discord.ext import commands, tasks
import random
from datetime import datetime, timedelta

# ---------------- CONFIG ----------------
TOKEN = os.getenv("TOKEN") or "YOUR_TOKEN_HERE"
PREFIX = "!"

OWNER_ID = 1169273992289456341
CO_OWNER_ID = 958273785037983754
DEFAULT_ROLE_NAME = "Member"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ---------------- DATABASE ----------------
money_data = {}
daily_claimed = {}
blackjack_games = {}
warn_data = {}
disabled_users = set()
scheduled_messages = []

# ---------------- HELPERS ----------------
def is_owner_or_co(ctx):
    return ctx.author.id in [OWNER_ID, CO_OWNER_ID]

# ---------------- GLOBAL CHECK ----------------
@bot.check
async def disabled_check(ctx):
    if ctx.author.id in disabled_users:
        await ctx.send("❌ You are disabled from using bot commands.")
        return False
    return True

# ---------------- EVENTS ----------------
@bot.event
async def on_ready():
    print(f"✅ Bot online as {bot.user}")
    if not check_scheduled_messages.is_running():
        check_scheduled_messages.start()

@bot.event
async def on_member_join(member):
    role = discord.utils.get(member.guild.roles, name=DEFAULT_ROLE_NAME)
    if role:
        try:
            await member.add_roles(role)
        except:
            pass
import os
import discord
from discord.ext import commands, tasks
import random
from datetime import datetime, timedelta

# ---------------- CONFIG ----------------
TOKEN = os.getenv("TOKEN") or "YOUR_TOKEN_HERE"
PREFIX = "!"

OWNER_ID = 1169273992289456341
CO_OWNER_ID = 958273785037983754
DEFAULT_ROLE_NAME = "Member"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ---------------- DATABASE ----------------
money_data = {}
daily_claimed = {}
blackjack_games = {}
warn_data = {}
disabled_users = set()
scheduled_messages = []

# ---------------- HELPERS ----------------
def is_owner_or_co(ctx):
    return ctx.author.id in [OWNER_ID, CO_OWNER_ID]

# ---------------- GLOBAL CHECK ----------------
@bot.check
async def disabled_check(ctx):
    if ctx.author.id in disabled_users:
        await ctx.send("❌ You are disabled from using bot commands.")
        return False
    return True

# ---------------- EVENTS ----------------
@bot.event
async def on_ready():
    print(f"✅ Bot online as {bot.user}")
    if not check_scheduled_messages.is_running():
        check_scheduled_messages.start()

@bot.event
async def on_member_join(member):
    role = discord.utils.get(member.guild.roles, name=DEFAULT_ROLE_NAME)
    if role:
        try:
            await member.add_roles(role)
        except:
            pass
# ---------------- ECONOMY ----------------

@bot.command()
async def balance(ctx, member: discord.Member=None):
    member = member or ctx.author
    bal = money_data.get(member.id,0)

    embed = discord.Embed(
        title="💰 Balance",
        description=f"{member.mention} has **{bal} coins**",
        color=discord.Color.gold()
    )

    await ctx.send(embed=embed)

@bot.command()
async def daily(ctx):
    now = datetime.utcnow()
    last = daily_claimed.get(ctx.author.id)

    if last and now-last < timedelta(hours=24):
        await ctx.send("❌ You already claimed your daily reward.")
        return

    coins = random.randint(50,200)

    money_data[ctx.author.id] = money_data.get(ctx.author.id,0)+coins
    daily_claimed[ctx.author.id] = now

    await ctx.send(f"💰 You received **{coins} coins**!")

@bot.command()
async def pay(ctx, member: discord.Member, amount:int):

    if money_data.get(ctx.author.id,0) < amount:
        await ctx.send("❌ Not enough coins.")
        return

    money_data[ctx.author.id] -= amount
    money_data[member.id] = money_data.get(member.id,0)+amount

    await ctx.send(f"💸 {ctx.author.mention} paid {member.mention} **{amount} coins**")

# ---------------- FUN ----------------

@bot.command()
async def coinflip(ctx):
    result=random.choice(["Heads","Tails"])
    await ctx.send(f"🪙 Result: **{result}**")

@bot.command()
async def roll(ctx,sides:int=6):
    num=random.randint(1,sides)
    await ctx.send(f"🎲 You rolled **{num}**")

@bot.command()
async def hug(ctx, member: discord.Member=None):
    member=member or ctx.author
    await ctx.send(f"🤗 {ctx.author.mention} hugs {member.mention}")

@bot.command()
async def slap(ctx, member: discord.Member=None):
    member=member or ctx.author
    await ctx.send(f"👋 {ctx.author.mention} slaps {member.mention}")

# ---------------- INFO ----------------

@bot.command()
async def userinfo(ctx, member: discord.Member=None):

    member=member or ctx.author

    embed=discord.Embed(
        title="User Info",
        color=discord.Color.blue()
    )

    embed.add_field(name="Name",value=member.name)
    embed.add_field(name="ID",value=member.id)
    embed.add_field(name="Joined",value=member.joined_at.strftime("%Y-%m-%d"))

    embed.set_thumbnail(url=member.avatar)

    await ctx.send(embed=embed)

@bot.command()
async def serverinfo(ctx):

    guild=ctx.guild

    embed=discord.Embed(
        title="Server Info",
        color=discord.Color.green()
    )

    embed.add_field(name="Name",value=guild.name)
    embed.add_field(name="Members",value=guild.member_count)
    embed.add_field(name="Owner",value=guild.owner)

    await ctx.send(embed=embed)

# ---------------- SCHEDULE ----------------

@bot.command()
async def schedule(ctx, minutes:int, *, message):

    send_time=datetime.utcnow()+timedelta(minutes=minutes)

    scheduled_messages.append({
        "channel":ctx.channel,
        "message":message,
        "time":send_time
    })

    await ctx.send(f"⏰ Message scheduled in {minutes} minutes.")

@tasks.loop(seconds=10)
async def check_scheduled_messages():

    now=datetime.utcnow()

    for msg in scheduled_messages[:]:

        if now>=msg["time"]:
            await msg["channel"].send(msg["message"])
            scheduled_messages.remove(msg)

# ---------------- RUN BOT ----------------
bot.run(TOKEN)
