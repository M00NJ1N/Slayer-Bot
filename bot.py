import discord
from discord.ext import commands, tasks
import random
import json
import asyncio
import datetime

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

OWNER_ID = 1169273992289456341

economy = {}
autorole_id = None

# ---------------- ECONOMY HELPERS ---------------- #

def get_balance(user):
    return economy.get(str(user), 0)

def add_balance(user, amount):
    economy[str(user)] = get_balance(user) + amount

def remove_balance(user, amount):
    economy[str(user)] = max(0, get_balance(user) - amount)

# ---------------- READY ---------------- #

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# ---------------- JOIN EVENT ---------------- #

@bot.event
async def on_member_join(member):
    if autorole_id:
        role = member.guild.get_role(autorole_id)
        if role:
            await member.add_roles(role)

# ---------------- BASIC COMMANDS ---------------- #

@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! {round(bot.latency*1000)}ms")

@bot.command()
async def avatar(ctx, member: discord.Member=None):
    member = member or ctx.author
    await ctx.send(member.avatar.url)

@bot.command()
async def say(ctx, *, message):
    await ctx.send(message)

# ---------------- USER INFO ---------------- #

@bot.command()
async def userinfo(ctx, member: discord.Member=None):
    member = member or ctx.author

    embed = discord.Embed(title="User Info")
    embed.add_field(name="Name", value=member.name)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Joined", value=member.joined_at)
    embed.set_thumbnail(url=member.avatar.url)

    await ctx.send(embed=embed)

# ---------------- SERVER INFO ---------------- #

@bot.command()
async def serverinfo(ctx):
    g = ctx.guild

    embed = discord.Embed(title=g.name)
    embed.add_field(name="Members", value=g.member_count)
    embed.add_field(name="Channels", value=len(g.channels))
    embed.add_field(name="Created", value=g.created_at)

    await ctx.send(embed=embed)

# ---------------- ECONOMY ---------------- #

@bot.command()
async def balance(ctx, member: discord.Member=None):
    member = member or ctx.author
    await ctx.send(f"{member.name} has {get_balance(member.id)} coins")

@bot.command()
async def daily(ctx):
    amount = random.randint(100,300)
    add_balance(ctx.author.id, amount)
    await ctx.send(f"You got {amount} coins!")

@bot.command()
async def pay(ctx, member: discord.Member, amount:int):
    if get_balance(ctx.author.id) < amount:
        return await ctx.send("Not enough money")

    remove_balance(ctx.author.id, amount)
    add_balance(member.id, amount)

    await ctx.send("Payment complete")

@bot.command()
async def leaderboard(ctx):

    board = sorted(economy.items(), key=lambda x: x[1], reverse=True)

    text = ""
    for i, data in enumerate(board[:10]):
        user = bot.get_user(int(data[0]))
        text += f"{i+1}. {user} - {data[1]}\n"

    await ctx.send(f"```{text}```")

# ---------------- ADMIN ECONOMY ---------------- #

@bot.command()
@commands.has_permissions(administrator=True)
async def setbalance(ctx, member: discord.Member, amount:int):
    economy[str(member.id)] = amount
    await ctx.send("Balance updated")

# ---------------- FUN ---------------- #

@bot.command()
async def coinflip(ctx):
    await ctx.send(random.choice(["Heads","Tails"]))

@bot.command()
async def roll(ctx, sides:int=6):
    await ctx.send(random.randint(1,sides))

@bot.command()
async def hug(ctx, member: discord.Member):
    await ctx.send(f"{ctx.author.mention} hugs {member.mention}")

@bot.command()
async def slap(ctx, member: discord.Member):
    await ctx.send(f"{ctx.author.mention} slaps {member.mention}")

# ---------------- RPG ---------------- #

@bot.command()
async def crime(ctx):

    success = random.choice([True,False])

    if success:
        money = random.randint(50,200)
        add_balance(ctx.author.id, money)
        await ctx.send(f"Crime success! +{money} coins")
    else:
        fine = random.randint(20,100)
        remove_balance(ctx.author.id, fine)
        await ctx.send(f"You got caught! -{fine}")

@bot.command()
async def loot(ctx):

    items = ["Sword","Shield","Potion","Gold","Gem"]
    item = random.choice(items)

    await ctx.send(f"You opened a crate and found {item}")

@bot.command()
async def quest(ctx):

    reward = random.randint(200,500)
    add_balance(ctx.author.id, reward)

    await ctx.send(f"Quest complete! +{reward} coins")

# ---------------- DUEL ---------------- #

@bot.command()
async def duel(ctx, opponent: discord.Member):

    if opponent.bot:
        return await ctx.send("Can't duel bots")

    msg = await ctx.send(f"{opponent.mention} react ⚔️ to accept duel")
    await msg.add_reaction("⚔️")

    def check(reaction,user):
        return user == opponent and str(reaction.emoji) == "⚔️"

    try:
        await bot.wait_for("reaction_add", timeout=30, check=check)
    except:
        return await ctx.send("Duel expired")

    winner = random.choice([ctx.author,opponent])

    reward = random.randint(50,150)
    add_balance(winner.id, reward)

    await ctx.send(f"{winner.mention} won the duel! +{reward}")

# ---------------- BLACKJACK ---------------- #

@bot.command()
async def blackjack(ctx):

    player = random.randint(15,21)
    dealer = random.randint(15,21)

    if player > dealer:
        win = random.randint(50,200)
        add_balance(ctx.author.id, win)
        await ctx.send(f"You win! {player} vs {dealer} (+{win})")
    else:
        await ctx.send(f"You lose {player} vs {dealer}")

# ---------------- TRIVIA ---------------- #

questions = [
("What planet is closest to the sun?","mercury"),
("How many continents are there?","7"),
("What is 5+7?","12")
]

@bot.command()
async def trivia(ctx):

    q,a = random.choice(questions)

    await ctx.send(q)

    def check(m):
        return m.channel == ctx.channel

    try:
        msg = await bot.wait_for("message",timeout=20,check=check)
    except:
        return await ctx.send("Time up")

    if msg.content.lower() == a:
        add_balance(msg.author.id,100)
        await ctx.send("Correct +100 coins")
    else:
        await ctx.send("Wrong")

# ---------------- MODERATION ---------------- #

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member:discord.Member, *, reason=None):
    await member.kick(reason=reason)
    await ctx.send("User kicked")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member:discord.Member, *, reason=None):
    await member.ban(reason=reason)
    await ctx.send("User banned")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount:int):
    await ctx.channel.purge(limit=amount+1)

# ---------------- LOCK / UNLOCK ---------------- #

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx):

    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("Channel locked")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):

    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send("Channel unlocked")

# ---------------- ROLE SYSTEM ---------------- #

@bot.command()
@commands.has_permissions(administrator=True)
async def autorole(ctx, role: discord.Role):
    global autorole_id
    autorole_id = role.id
    await ctx.send("Autorole set")

@bot.command()
@commands.has_permissions(administrator=True)
async def roleall(ctx, role: discord.Role):

    for member in ctx.guild.members:
        try:
            await member.add_roles(role)
        except:
            pass

    await ctx.send("Role added to everyone")

# ---------------- CLIP ---------------- #

@bot.command()
async def clip(ctx):

    if not ctx.message.reference:
        return await ctx.send("Reply to a message")

    msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)

    embed = discord.Embed(title="Clipped Message")
    embed.add_field(name="Author",value=msg.author)
    embed.add_field(name="Time",value=msg.created_at)
    embed.add_field(name="Message",value=msg.content)

    await ctx.author.send(embed=embed)

    await ctx.send("Sent to your DM")

# ---------------- SCHEDULE ---------------- #

@bot.command()
@commands.has_permissions(administrator=True)
async def schedule(ctx, seconds:int, *, message):

    msg = await ctx.send(f"||{message}||")

    await asyncio.sleep(seconds)

    await msg.edit(content=message)

# ---------------- OWNER COMMANDS ---------------- #

def owner(ctx):
    return ctx.author.id == OWNER_ID

@bot.command()
@commands.check(owner)
async def shutdown(ctx):
    await ctx.send("Shutting down")
    await bot.close()

@bot.command()
@commands.check(owner)
async def broadcast(ctx, *, message):

    for guild in bot.guilds:
        for channel in guild.text_channels:
            try:
                await channel.send(message)
                break
            except:
                pass

# ---------------- RUN BOT ---------------- #

bot.run("TOKEN")
