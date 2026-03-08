import discord
from discord.ext import commands, tasks
import random
import asyncio
import json
import datetime

# ---------------- CONFIG ----------------
with open("config.json") as f:
    config = json.load(f)

intents = discord.Intents.all()  # All intents for members, messages, DMs
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- EVENTS ----------------
@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")

@bot.event
async def on_member_join(member):
    # Autorole: assign "Member" role if exists
    role = discord.utils.get(member.guild.roles, name="Member")
    if role:
        try:
            await member.add_roles(role)
        except discord.Forbidden:
            print(f"Cannot add role to {member}. Check role hierarchy.")
    print(f"{member} joined. Autorole attempted.")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    # Basic automod
    bad_words = ["badword1", "badword2"]
    if any(word in message.content.lower() for word in bad_words):
        try:
            await message.delete()
            await message.channel.send(f"{message.author.mention} watch your language.", delete_after=5)
        except:
            pass
    await bot.process_commands(message)

# ---------------- UTILITY ----------------
@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

@bot.command()
async def serverinfo(ctx):
    embed = discord.Embed(title=f"{ctx.guild.name} Info", color=discord.Color.blue())
    embed.add_field(name="Members", value=ctx.guild.member_count)
    embed.add_field(name="Owner", value=ctx.guild.owner)
    embed.add_field(name="Created At", value=ctx.guild.created_at.strftime("%Y-%m-%d %H:%M:%S"))
    embed.add_field(name="Roles", value=len(ctx.guild.roles))
    await ctx.send(embed=embed)

@bot.command()
async def whois(ctx, member: discord.Member):
    embed = discord.Embed(title=f"{member}", color=discord.Color.purple())
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Joined", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"))
    embed.add_field(name="Created", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"))
    await ctx.send(embed=embed)

# ---------------- MODERATION ----------------
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    try:
        await member.ban(reason=reason)
        await ctx.send(f"{member} has been banned.")
    except discord.Forbidden:
        await ctx.send("I cannot ban this member. Check my role position and permissions.")

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"{member} has been kicked.")
    except discord.Forbidden:
        await ctx.send("I cannot kick this member. Check my role position and permissions.")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int):
    try:
        duration = minutes * 60
        await member.timeout(discord.utils.utcnow() + datetime.timedelta(seconds=duration))
        await ctx.send(f"{member} timed out for {minutes} minutes.")
    except discord.Forbidden:
        await ctx.send("I cannot timeout this member. Check my role position and permissions.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f"Deleted {len(deleted)} messages.", delete_after=3)

# ---------------- ROLE MANAGEMENT ----------------
@bot.command()
@commands.has_permissions(manage_roles=True)
async def addrole(ctx, member: discord.Member, *, role_name):
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if role:
        try:
            await member.add_roles(role)
            await ctx.send(f"{role.name} role added to {member.mention}.")
        except discord.Forbidden:
            await ctx.send("Cannot add this role. Check role hierarchy and permissions.")
    else:
        await ctx.send("Role not found.")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def removerole(ctx, member: discord.Member, *, role_name):
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if role:
        try:
            await member.remove_roles(role)
            await ctx.send(f"{role.name} role removed from {member.mention}.")
        except discord.Forbidden:
            await ctx.send("Cannot remove this role. Check role hierarchy and permissions.")
    else:
        await ctx.send("Role not found.")

# ---------------- GIVEAWAYS ----------------
@bot.command()
async def giveaway(ctx, seconds: int, *, prize):
    embed = discord.Embed(
        title="🎉 Giveaway!",
        description=f"Prize: {prize}\nReact with 🎉",
        color=discord.Color.green()
    )
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎉")
    await asyncio.sleep(seconds)
    msg = await ctx.channel.fetch_message(msg.id)
    users = []
    for reaction in msg.reactions:
        if reaction.emoji == "🎉":
            async for user in reaction.users():
                if not user.bot:
                    users.append(user)
    if users:
        winner = random.choice(users)
        await ctx.send(f"Winner: {winner.mention}")
    else:
        await ctx.send("No one participated.")

# ---------------- SAFE DM COMMAND ----------------
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
    await ctx.send(f"Sent DMs to {count} members.")

# ---------------- FUN COMMANDS ----------------
@bot.command()
async def coinflip(ctx):
    await ctx.send(random.choice(["Heads", "Tails"]))

@bot.command()
async def roll(ctx, dice: str):
    try:
        rolls, limit = map(int, dice.lower().split("d"))
    except:
        await ctx.send("Format has to be NdN, e.g., 2d6")
        return
    result = [random.randint(1, limit) for _ in range(rolls)]
    await ctx.send(f"🎲 {result} Total: {sum(result)}")

@bot.command()
async def say(ctx, *, message):
    await ctx.send(message)

# ---------------- RUN BOT ----------------
bot.run(config["token"])