import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
from datetime import datetime, timedelta

TOKEN = os.getenv("TOKEN") or "YOUR_TOKEN_HERE"
COMMAND_PREFIX = "!"

OWNER_ID = 1169273992289456341
CO_OWNER_ID = 958273785037983754

intents = discord.Intents.all()

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)
tree = bot.tree

# ---------------- DATABASE ----------------
money_data = {}
daily_claimed = {}
warn_data = {}
blackjack_games = {}

levels = {}
xp = {}

disabled_users = set()

autorole_id = None

scheduled_messages = []
giveaways = {}

# ---------------- PERMISSION CHECKS ----------------

def is_owner_or_co(user):
    return user.id in [OWNER_ID, CO_OWNER_ID]


async def check_disabled(interaction_or_ctx):
    user = interaction_or_ctx.user if hasattr(interaction_or_ctx, "user") else interaction_or_ctx.author
    if user.id in disabled_users:
        return False
    return True


# ---------------- EVENTS ----------------

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot online as {bot.user}")

    if not check_scheduled_messages.is_running():
        check_scheduled_messages.start()


@bot.event
async def on_member_join(member):

    if autorole_id:
        role = member.guild.get_role(autorole_id)
        if role:
            await member.add_roles(role)


@bot.event
async def on_message(message):

    if message.author.bot:
        return

    user = message.author.id

    xp[user] = xp.get(user, 0) + random.randint(5, 15)

    level = levels.get(user, 0)

    if xp[user] >= (level + 1) * 100:
        levels[user] = level + 1
        await message.channel.send(
            f"🎉 {message.author.mention} leveled up to **Level {levels[user]}**!"
        )

    await bot.process_commands(message)

# ---------------- PING ----------------

@bot.command()
async def ping(ctx):
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latency: **{round(bot.latency*1000)}ms**",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


@tree.command(name="ping")
async def ping_slash(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"🏓 Pong! {round(bot.latency*1000)}ms"
    )


# ---------------- OWNER COMMANDS ----------------

@bot.command()
async def shutdown(ctx):
    if not is_owner_or_co(ctx.author):
        return
    await ctx.send("Bot shutting down.")
    await bot.close()


@bot.command()
async def disableuser(ctx, member: discord.Member):
    if not is_owner_or_co(ctx.author):
        return
    disabled_users.add(member.id)
    await ctx.send(f"{member} disabled from using bot commands.")


@bot.command()
async def enableuser(ctx, member: discord.Member):
    if not is_owner_or_co(ctx.author):
        return
    disabled_users.discard(member.id)
    await ctx.send(f"{member} can use bot commands again.")


# ---------------- MODERATION ----------------

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    await member.ban(reason=reason)
    await ctx.send(f"🔨 {member} banned.")


@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    await member.kick(reason=reason)
    await ctx.send(f"👢 {member} kicked.")


@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f"Deleted {len(deleted)} messages.", delete_after=5)


@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int):

    until = discord.utils.utcnow() + timedelta(minutes=minutes)
    await member.timeout(until)

    await ctx.send(f"{member} timed out for {minutes} minutes.")


@bot.command()
async def warn(ctx, member: discord.Member, *, reason=None):

    warn_data[member.id] = warn_data.get(member.id, 0) + 1

    await ctx.send(
        f"{member} warned.\nTotal warns: **{warn_data[member.id]}**"
    )


# ---------------- AUTOROLE ----------------

@bot.command()
async def autorole(ctx, role: discord.Role):

    global autorole_id

    if not ctx.author.guild_permissions.administrator:
        return

    autorole_id = role.id

    await ctx.send(f"Autorole set to {role.name}")

# ---------------- ECONOMY ----------------

@bot.command()
async def balance(ctx, member: discord.Member = None):

    member = member or ctx.author
    bal = money_data.get(member.id, 0)

    await ctx.send(f"💰 {member} has **{bal} coins**")


@bot.command()
async def daily(ctx):

    now = datetime.utcnow()
    last = daily_claimed.get(ctx.author.id)

    if last and now - last < timedelta(hours=24):
        await ctx.send("You already claimed daily.")
        return

    coins = random.randint(50, 200)

    money_data[ctx.author.id] = money_data.get(ctx.author.id, 0) + coins
    daily_claimed[ctx.author.id] = now

    await ctx.send(f"You received **{coins} coins**")


# ---------------- BLACKJACK ----------------

@bot.command()
async def blackjack(ctx):

    deck = [2,3,4,5,6,7,8,9,10,10,10,10,11]*4
    random.shuffle(deck)

    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]

    blackjack_games[ctx.author.id] = {
        "player": player,
        "dealer": dealer,
        "deck": deck
    }

    await ctx.send(f"Your hand: {player}\nDealer shows: {dealer[0]}")


@bot.command()
async def hit(ctx):

    game = blackjack_games.get(ctx.author.id)

    if not game:
        return

    game["player"].append(game["deck"].pop())

    total = sum(game["player"])

    await ctx.send(f"Hand: {game['player']} = {total}")

    if total > 21:
        await ctx.send("Bust!")
        del blackjack_games[ctx.author.id]


# ---------------- FUN ----------------

@bot.command()
async def coinflip(ctx):
    await ctx.send(random.choice(["Heads", "Tails"]))


@bot.command()
async def roll(ctx, sides: int = 6):
    await ctx.send(random.randint(1, sides))


@bot.command()
async def avatar(ctx, member: discord.Member = None):

    member = member or ctx.author

    embed = discord.Embed(title=f"{member}'s Avatar")
    embed.set_image(url=member.display_avatar.url)

    await ctx.send(embed=embed)


# ---------------- GIVEAWAYS ----------------

@bot.command()
async def giveaway(ctx, minutes: int, *, prize):

    embed = discord.Embed(
        title="🎉 GIVEAWAY",
        description=f"Prize: **{prize}**\nReact with 🎉 to enter!",
        color=discord.Color.gold()
    )

    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎉")

    giveaways[msg.id] = {
        "end": datetime.utcnow() + timedelta(minutes=minutes),
        "prize": prize,
        "channel": ctx.channel
    }


@tasks.loop(seconds=15)
async def check_scheduled_messages():

    now = datetime.utcnow()

    for gid in list(giveaways):

        data = giveaways[gid]

        if now >= data["end"]:

            channel = data["channel"]
            msg = await channel.fetch_message(gid)

            users = [u async for u in msg.reactions[0].users() if not u.bot]

            if users:
                winner = random.choice(users)
                await channel.send(f"🎉 Winner: {winner} | Prize: {data['prize']}")

            else:
                await channel.send("No giveaway entries.")

            del giveaways[gid]


# ---------------- RUN BOT ----------------

bot.run(TOKEN)
