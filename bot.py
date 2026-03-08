import discord
from discord.ext import commands, tasks
import os
import random
import asyncio
from datetime import datetime, timedelta

# -----------------------------
# Environment Token
# -----------------------------
TOKEN = os.getenv("TOKEN")
if TOKEN is None:
    raise ValueError("No bot token found! Set the TOKEN environment variable.")

# -----------------------------
# Bot setup
# -----------------------------
intents = discord.Intents.all()  # necessary for members, messages, reactions
bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command("help")  # we will add a custom help command

# -----------------------------
# Events
# -----------------------------
@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")

@bot.event
async def on_member_join(member):
    # Autorole
    role = discord.utils.get(member.guild.roles, name="Member")
    if role:
        try:
            await member.add_roles(role)
            print(f"Added Member role to {member}")
        except:
            print(f"Cannot add role to {member}")

# -----------------------------
# Moderation Commands
# -----------------------------
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, duration: int = None, *, reason=None):
    """Ban a member. Optionally unban after duration (minutes)."""
    await member.ban(reason=reason)
    await ctx.send(f"{member} has been banned.")
    if duration:
        await asyncio.sleep(duration*60)
        try:
            await ctx.guild.unban(member)
            await ctx.send(f"{member} has been unbanned after {duration} minutes.")
        except:
            pass

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    await member.kick(reason=reason)
    await ctx.send(f"{member} has been kicked.")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int):
    duration = minutes * 60
    await member.timeout(discord.utils.utcnow() + timedelta(seconds=duration))
    await ctx.send(f"{member} timed out for {minutes} minutes.")

@bot.command()
@commands.has_permissions(administrator=True)
async def dmall(ctx, *, message):
    """Send a DM to all members (non-bots)."""
    count = 0
    for member in ctx.guild.members:
        if not member.bot:
            try:
                await member.send(message)
                count += 1
            except:
                continue
    await ctx.send(f"Sent DM to {count} members.")

@bot.command()
@commands.has_permissions(administrator=True)
async def delete_dm(ctx, user: discord.User, limit: int = 100):
    """Delete recent DMs the bot sent to a user."""
    try:
        channel = await user.create_dm()
        async for msg in channel.history(limit=limit):
            if msg.author == bot.user:
                await msg.delete()
        await ctx.send(f"Deleted last {limit} DMs sent to {user}.")
    except Exception as e:
        await ctx.send(f"Failed to delete DMs: {e}")

# -----------------------------
# Fun Commands
# -----------------------------
@bot.command()
async def roll(ctx, dice: str):
    """Roll dice in NdN format (e.g., 2d6)."""
    try:
        rolls, limit = map(int, dice.lower().split("d"))
        results = [random.randint(1, limit) for _ in range(rolls)]
        await ctx.send(f"{ctx.author.mention} rolled {results} = {sum(results)}")
    except:
        await ctx.send("Format has to be NdN (e.g., 2d6)")

@bot.command()
async def coin(ctx):
    await ctx.send(f"{ctx.author.mention} flipped a coin and got **{random.choice(['Heads','Tails'])}**")

@bot.command()
async def say(ctx, *, message):
    await ctx.send(message)

# -----------------------------
# Utility Commands
# -----------------------------
@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! Latency: {round(bot.latency*1000)}ms")

@bot.command()
async def serverinfo(ctx):
    embed = discord.Embed(title=f"{ctx.guild.name} Info", color=discord.Color.blue())
    embed.add_field(name="Owner", value=ctx.guild.owner)
    embed.add_field(name="Members", value=ctx.guild.member_count)
    embed.add_field(name="Roles", value=len(ctx.guild.roles))
    embed.add_field(name="Text Channels", value=len(ctx.guild.text_channels))
    embed.add_field(name="Voice Channels", value=len(ctx.guild.voice_channels))
    embed.set_footer(text=f"Server ID: {ctx.guild.id}")
    await ctx.send(embed=embed)

# -----------------------------
# Giveaways System
# -----------------------------
giveaways = {}  # {message_id: {"prize": str, "end": datetime, "users": set()}}

@bot.command()
async def giveaway(ctx, duration: int, *, prize):
    """Start a giveaway in minutes."""
    end_time = datetime.utcnow() + timedelta(minutes=duration)
    msg = await ctx.send(f"🎉 **GIVEAWAY** 🎉\nPrize: {prize}\nReact with 🎉 to enter!\nEnds at {end_time} UTC")
    await msg.add_reaction("🎉")
    giveaways[msg.id] = {"prize": prize, "end": end_time, "users": set()}
    
    while datetime.utcnow() < end_time:
        await asyncio.sleep(5)
    
    msg = await ctx.fetch_message(msg.id)
    users = set()
    for reaction in msg.reactions:
        if reaction.emoji == "🎉":
            async for user in reaction.users():
                if not user.bot:
                    users.add(user)
    if users:
        winner = random.choice(list(users))
        await ctx.send(f"🎉 Congratulations {winner.mention}! You won **{prize}**")
    else:
        await ctx.send(f"No participants for **{prize}**.")

# -----------------------------
# Custom Help
# -----------------------------
@bot.command()
async def help(ctx):
    commands_list = [
        "ping", "say", "coin", "roll", "serverinfo", "ban", "kick", "timeout",
        "dmall", "delete_dm", "giveaway"
    ]
    await ctx.send(f"Available commands: {', '.join(commands_list)}")

# -----------------------------
# Run bot
# -----------------------------
bot.run(TOKEN)
