import discord
from discord.ext import commands, tasks
import os
import random
import asyncio
import datetime

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

warnings = {}
economy = {}
reminders = []

# ---------------- READY EVENT ----------------

@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")

# ---------------- AUTOROLE ----------------

@bot.event
async def on_member_join(member):
    role = discord.utils.get(member.guild.roles, name="Member")
    if role:
        try:
            await member.add_roles(role)
        except:
            pass

# ---------------- BASIC COMMANDS ----------------

@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! {round(bot.latency*1000)}ms")

@bot.command()
async def coinflip(ctx):
    await ctx.send(random.choice(["Heads", "Tails"]))

@bot.command()
async def roll(ctx, sides: int = 6):
    await ctx.send(f"You rolled {random.randint(1,sides)}")

# ---------------- SERVER INFO ----------------

@bot.command()
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=guild.name)
    embed.add_field(name="Members", value=guild.member_count)
    embed.add_field(name="Roles", value=len(guild.roles))
    embed.add_field(name="Owner", value=guild.owner)
    await ctx.send(embed=embed)

@bot.command()
async def userinfo(ctx, member: discord.Member=None):
    member = member or ctx.author
    embed = discord.Embed(title=str(member))
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Joined", value=member.joined_at)
    embed.add_field(name="Top Role", value=member.top_role)
    await ctx.send(embed=embed)

# ---------------- PURGE ----------------

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    await ctx.channel.purge(limit=amount)
    await ctx.send(f"Deleted {amount} messages", delete_after=3)

# ---------------- WARN SYSTEM ----------------

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No reason"):
    if member.id not in warnings:
        warnings[member.id] = []

    warnings[member.id].append(reason)

    await ctx.send(f"{member} warned: {reason}")

@bot.command()
async def warnings(ctx, member: discord.Member):
    if member.id not in warnings:
        await ctx.send("No warnings")
        return

    warn_list = warnings[member.id]
    text = "\n".join(warn_list)

    await ctx.send(f"Warnings for {member}:\n{text}")

@bot.command()
@commands.has_permissions(administrator=True)
async def clearwarnings(ctx, member: discord.Member):
    warnings[member.id] = []
    await ctx.send("Warnings cleared")

# ---------------- MODERATION ----------------

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason"):
    await member.kick(reason=reason)
    await ctx.send(f"{member} kicked")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason"):
    await member.ban(reason=reason)
    await ctx.send(f"{member} banned")

# ---------------- TEMP BAN ----------------

@bot.command()
@commands.has_permissions(ban_members=True)
async def tempban(ctx, member: discord.Member, minutes: int, *, reason="No reason"):
    await member.ban(reason=reason)
    await ctx.send(f"{member} banned for {minutes} minutes")

    await asyncio.sleep(minutes * 60)

    await ctx.guild.unban(member)
    await ctx.send(f"{member} unbanned")

# ---------------- TIMEOUT ----------------

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int):
    until = discord.utils.utcnow() + datetime.timedelta(minutes=minutes)
    await member.timeout(until)
    await ctx.send(f"{member} timed out for {minutes} minutes")

# ---------------- ECONOMY ----------------

def get_balance(user):
    if user not in economy:
        economy[user] = 100
    return economy[user]

@bot.command()
async def balance(ctx):
    bal = get_balance(ctx.author.id)
    await ctx.send(f"💰 Balance: {bal}")

@bot.command()
async def daily(ctx):
    money = random.randint(50,200)
    economy[ctx.author.id] = get_balance(ctx.author.id) + money
    await ctx.send(f"You got {money} coins")

@bot.command()
async def give(ctx, member: discord.Member, amount:int):
    if get_balance(ctx.author.id) < amount:
        await ctx.send("Not enough money")
        return

    economy[ctx.author.id] -= amount
    economy[member.id] = get_balance(member.id) + amount

    await ctx.send("Money sent")

# ---------------- BET GAME ----------------

@bot.command()
async def coinflipbet(ctx, amount:int):
    if get_balance(ctx.author.id) < amount:
        await ctx.send("Not enough money")
        return

    result = random.choice(["win","lose"])

    if result == "win":
        economy[ctx.author.id] += amount
        await ctx.send("You won!")
    else:
        economy[ctx.author.id] -= amount
        await ctx.send("You lost")

# ---------------- GAMES ----------------

@bot.command()
async def rps(ctx, choice):
    options = ["rock","paper","scissors"]
    bot_choice = random.choice(options)

    if choice == bot_choice:
        result = "Tie"
    elif (choice=="rock" and bot_choice=="scissors") or (choice=="paper" and bot_choice=="rock") or (choice=="scissors" and bot_choice=="paper"):
        result="You win"
    else:
        result="You lose"

    await ctx.send(f"I chose {bot_choice}. {result}")

@bot.command()
async def guess(ctx):
    number = random.randint(1,10)
    await ctx.send("Guess 1-10")

    def check(m):
        return m.author == ctx.author

    msg = await bot.wait_for("message", check=check)

    if int(msg.content) == number:
        await ctx.send("Correct!")
    else:
        await ctx.send(f"Wrong. Number was {number}")

# ---------------- QUOTE ----------------

quotes = []

@bot.command()
async def addquote(ctx, *, text):
    quotes.append(text)
    await ctx.send("Quote added")

@bot.command()
async def quote(ctx):
    if not quotes:
        await ctx.send("No quotes yet")
    else:
        await ctx.send(random.choice(quotes))

# ---------------- REMINDER ----------------

@bot.command()
async def remind(ctx, minutes:int, *, message):
    await ctx.send(f"I will remind you in {minutes} minutes")

    await asyncio.sleep(minutes*60)

    await ctx.send(f"{ctx.author.mention} reminder: {message}")

# ---------------- DM ALL ----------------

@bot.command()
@commands.has_permissions(administrator=True)
async def dmall(ctx, *, message):
    count = 0

    for member in ctx.guild.members:
        if not member.bot:
            try:
                await member.send(message)
                count += 1
            except:
                pass

    await ctx.send(f"Sent to {count} users")

bot.run(TOKEN)
