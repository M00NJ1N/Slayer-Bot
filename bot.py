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

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# ----------------- DATABASE SIMULATION -----------------
# For XP, economy, warnings
xp_data = {}
money_data = {}
warn_data = {}

# ----------------- EVENTS -----------------
@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    if not giveaway_loop.is_running():
        giveaway_loop.start()

@bot.event
async def on_member_join(member):
    role = discord.utils.get(member.guild.roles, name=DEFAULT_ROLE_NAME)
    if role:
        try:
            await member.add_roles(role)
            print(f"Added role {DEFAULT_ROLE_NAME} to {member}")
        except discord.Forbidden:
            print(f"Cannot add role to {member}, missing permissions.")
    xp_data[member.id] = 0
    money_data[member.id] = 100
    warn_data[member.id] = 0

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    # XP system
    xp_data[message.author.id] = xp_data.get(message.author.id, 0) + random.randint(5, 15)
    await bot.process_commands(message)

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
        await ctx.send("I cannot kick that member.")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int, *, reason=None):
    try:
        until = datetime.utcnow() + timedelta(minutes=minutes)
        await member.timeout(until, reason=reason)
        await ctx.send(f"{member} timed out for {minutes} minutes. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send("I cannot timeout that member.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, limit: int):
    deleted = await ctx.channel.purge(limit=limit)
    await ctx.send(f"Deleted {len(deleted)} messages.", delete_after=5)

@bot.command()
@commands.has_permissions(ban_members=True)
async def softban(ctx, member: discord.Member, *, reason=None):
    try:
        await member.ban(reason=reason, delete_message_days=7)
        await member.unban(reason="Softban completed")
        await ctx.send(f"{member} was softbanned.")
    except discord.Forbidden:
        await ctx.send("Cannot softban this member.")

@bot.command()
@commands.has_permissions(administrator=True)
async def warn(ctx, member: discord.Member, *, reason=None):
    warn_data[member.id] = warn_data.get(member.id, 0) + 1
    await ctx.send(f"{member} warned. Total warns: {warn_data[member.id]} Reason: {reason}")

@bot.command()
@commands.has_permissions(administrator=True)
async def resetwarns(ctx, member: discord.Member):
    warn_data[member.id] = 0
    await ctx.send(f"{member}'s warnings have been reset.")

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

@bot.command()
@commands.has_permissions(administrator=True)
async def deldms(ctx):
    await ctx.send("Cannot delete other users' DMs due to Discord API restrictions.")

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

# ----------------- ECONOMY -----------------
@bot.command()
async def balance(ctx, member: discord.Member = None):
    member = member or ctx.author
    bal = money_data.get(member.id, 0)
    await ctx.send(f"{member} has {bal} coins.")

@bot.command()
async def daily(ctx):
    user = ctx.author
    coins = random.randint(50, 200)
    money_data[user.id] = money_data.get(user.id, 0) + coins
    await ctx.send(f"{user} collected {coins} coins today!")

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
@commands.has_permissions(administrator=True)
async def setbalance(ctx, member: discord.Member, amount: int):
    money_data[member.id] = amount
    await ctx.send(f"{member}'s balance set to {amount} coins.")

@bot.command()
async def leaderboard(ctx):
    top_users = sorted(money_data.items(), key=lambda x: x[1], reverse=True)[:10]
    msg = "**Leaderboard:**\n"
    for i, (user_id, bal) in enumerate(top_users, 1):
        user = ctx.guild.get_member(user_id)
        if user:
            msg += f"{i}. {user.display_name} - {bal} coins\n"
    await ctx.send(msg)

# ----------------- LEVELS -----------------
@bot.command()
async def level(ctx, member: discord.Member = None):
    member = member or ctx.author
    xp = xp_data.get(member.id, 0)
    lvl = xp // 100
    await ctx.send(f"{member} is level {lvl} with {xp} XP.")

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
async def kiss(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"{ctx.author.mention} kisses {member.mention} 😘")

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

@bot.command()
async def joke(ctx):
    jokes = [
        "Why did the chicken cross the road? To get to the other side!",
        "I told my computer I needed a break, and it said: 'No problem, I'll go to sleep.'"
    ]
    await ctx.send(random.choice(jokes))

@bot.command()
async def meme(ctx):
    memes = ["https://i.imgflip.com/1bij.jpg", "https://i.imgflip.com/26am.jpg"]
    await ctx.send(random.choice(memes))

@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! Latency: {round(bot.latency * 1000)}ms")

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

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"{member}", color=discord.Color.green())
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Bot?", value=member.bot)
    embed.add_field(name="Created At", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"))
    embed.add_field(name="Joined At", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"))
    await ctx.send(embed=embed)

# ----------------- RUN BOT -----------------
bot.run(TOKEN)
