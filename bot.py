import discord
from discord.ext import commands, tasks
import os
import random
import datetime

# ---------------- CONFIG ----------------
TOKEN = os.getenv("TOKEN")  # safe way to keep your token secret
GIVEAWAY_CHANNEL_NAME = "giveaways"
AUTOROLE_NAME = "Member"

# ---------------- INTENTS ----------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- EVENTS ----------------
@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    giveaway_loop.start()  # start giveaway task

@bot.event
async def on_member_join(member):
    """Give autorole when a new member joins"""
    role = discord.utils.get(member.guild.roles, name=AUTOROLE_NAME)
    if role:
        try:
            await member.add_roles(role)
        except:
            print(f"Cannot add role to {member}")

# ---------------- MODERATION COMMANDS ----------------
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    try:
        await member.ban(reason=reason)
        await ctx.send(f"{member} has been banned.")
    except discord.Forbidden:
        await ctx.send("I cannot ban this member.")

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"{member} has been kicked.")
    except discord.Forbidden:
        await ctx.send("I cannot kick this member.")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int):
    try:
        await member.timeout(discord.utils.utcnow() + datetime.timedelta(minutes=minutes))
        await ctx.send(f"{member} has been timed out for {minutes} minutes.")
    except discord.Forbidden:
        await ctx.send("I cannot timeout this member.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    if amount < 1:
        await ctx.send("You must delete at least 1 message.")
        return
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f"🗑️ Deleted {len(deleted)} messages.", delete_after=5)

# ---------------- FUN COMMANDS ----------------
@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

@bot.command()
async def coinflip(ctx):
    await ctx.send(random.choice(["Heads", "Tails"]))

@bot.command()
async def roll(ctx, sides: int = 6):
    await ctx.send(f"You rolled a {random.randint(1, sides)}!")

@bot.command()
async def joke(ctx):
    jokes = [
        "Why did the chicken join Discord? To get some cluckin’ friends!",
        "I would tell you a UDP joke, but you might not get it.",
        "Why do programmers prefer dark mode? Because light attracts bugs!"
    ]
    await ctx.send(random.choice(jokes))

@bot.command()
async def rps(ctx, choice: str):
    options = ["rock", "paper", "scissors"]
    bot_choice = random.choice(options)
    if choice.lower() not in options:
        await ctx.send("Choose rock, paper, or scissors!")
        return
    result = "Draw!"
    if (choice.lower() == "rock" and bot_choice == "scissors") or \
       (choice.lower() == "paper" and bot_choice == "rock") or \
       (choice.lower() == "scissors" and bot_choice == "paper"):
        result = "You win!"
    elif choice.lower() != bot_choice:
        result = "You lose!"
    await ctx.send(f"You chose {choice.lower()}, I chose {bot_choice}. {result}")

# ---------------- UTILITY COMMANDS ----------------
@bot.command()
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=f"{guild.name} Info", color=discord.Color.blue())
    embed.add_field(name="Members", value=guild.member_count)
    embed.add_field(name="Owner", value=guild.owner)
    embed.add_field(name="Created At", value=guild.created_at.strftime("%Y-%m-%d"))
    embed.add_field(name="Roles", value=len(guild.roles))
    await ctx.send(embed=embed)

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"{member} Info", color=discord.Color.green())
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d"))
    embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d"))
    await ctx.send(embed=embed)

@bot.command()
async def roles(ctx):
    roles = [role.name for role in ctx.guild.roles if role.name != "@everyone"]
    await ctx.send(", ".join(roles))

@bot.command()
async def botinfo(ctx):
    embed = discord.Embed(title="Bot Info", color=discord.Color.purple())
    embed.add_field(name="Bot", value=bot.user)
    embed.add_field(name="Servers", value=len(bot.guilds))
    await ctx.send(embed=embed)

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
    await ctx.send(f"DM sent to {count} members.")

# ---------------- GIVEAWAYS ----------------
active_giveaways = {}

@bot.command()
@commands.has_permissions(administrator=True)
async def giveaway(ctx, duration: int, *, prize: str):
    channel = discord.utils.get(ctx.guild.text_channels, name=GIVEAWAY_CHANNEL_NAME)
    if not channel:
        channel = ctx.channel
    end_time = discord.utils.utcnow() + datetime.timedelta(seconds=duration)
    embed = discord.Embed(
        title="🎉 Giveaway! 🎉",
        description=f"Prize: {prize}\nReact with 🎉 to enter!\nEnds in {duration} seconds",
        color=discord.Color.green()
    )
    message = await channel.send(embed=embed)
    await message.add_reaction("🎉")
    active_giveaways[message.id] = {"prize": prize, "end_time": end_time, "message": message}

@giveaway_loop := tasks.loop(seconds=10)
async def giveaway_loop():
    now = discord.utils.utcnow()
    to_remove = []
    for msg_id, g in active_giveaways.items():
        if now >= g["end_time"]:
            message = g["message"]
            message = await message.channel.fetch_message(message.id)
            users = []
            for reaction in message.reactions:
                if str(reaction.emoji) == "🎉":
                    async for user in reaction.users():
                        if not user.bot:
                            users.append(user)
            if users:
                winner = random.choice(users)
                await message.channel.send(f"🎊 Congratulations {winner.mention}! You won **{g['prize']}**!")
            else:
                await message.channel.send("No one entered the giveaway.")
            to_remove.append(msg_id)
    for msg_id in to_remove:
        del active_giveaways[msg_id]

# ---------------- RUN BOT ----------------
bot.run(TOKEN)
