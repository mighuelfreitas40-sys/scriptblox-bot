import discord
import aiohttp
import asyncio
import os
from discord.ext import commands
from discord import app_commands

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = 1252758938693144696
PREFIX = "!"
SCRIPTBLOX_SEARCH = "https://scriptblox.com/api/script/search"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

configured_channels = {}

async def search_scriptblox(query: str, max_results: int = 5):
    params = {
        "q": query,
        "max": max_results,
        "mode": "free",
        "patched": "0",
        "sortBy": "views",
        "order": "desc"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(SCRIPTBLOX_SEARCH, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return None, f"Erro API: {resp.status}"
            data = await resp.json()
            scripts = data.get("result", {}).get("scripts", [])
            if not scripts:
                return None, "Nenhum script encontrado."
            return scripts, None

def format_embed(script: dict) -> discord.Embed:
    game = script.get("game", {})
    embed = discord.Embed(
        title=f"📜 {script.get('title', 'Sem título')}",
        description=f"**Jogo:** {game.get('name', 'Universal')}\n"
                    f"**👁️ Views:** {script.get('views', 0):,}\n"
                    f"**❤️ Likes:** {script.get('likeCount', 0):,}\n"
                    f"**✅ Verificado:** {'Sim' if script.get('verified') else 'Não'}\n"
                    f"**🔒 Key:** {'Sim' if script.get('key') else 'Não'}",
        color=0x00FF00 if not script.get("isPatched") else 0xFF0000
    )
    code = script.get("script", "Não disponível")
    if len(code) > 1000:
        code = code[:997] + "..."
    embed.add_field(name="📝 Script", value=f"```lua\n{code}\n```", inline=False)
    slug = script.get("slug", "")
    if slug:
        embed.add_field(name="🔗 Link", value=f"https://scriptblox.com/script/{slug}", inline=False)
    if game.get("imageUrl"):
        embed.set_thumbnail(url=game["imageUrl"])
    embed.set_footer(text="ScriptBlox.com")
    return embed

@bot.event
async def on_ready():
    print(f"✅ {bot.user} online!")
    try:
        synced = await bot.tree.sync()
        print(f"🔄 {len(synced)} slash commands")
    except Exception as e:
        print(f"Erro sync: {e}")

@bot.command(name="addchannel")
async def addchannel(ctx, channel: discord.TextChannel = None):
    if ctx.author.id != OWNER_ID:
        return await ctx.reply("❌ Sem permissão!", delete_after=5)
    channel = channel or ctx.channel
    configured_channels[ctx.guild.id] = channel.id
    await ctx.reply(f"✅ Canal definido: {channel.mention}")

@bot.command(name="script", aliases=["s", "sc"])
async def script_cmd(ctx, *, game: str):
    if ctx.guild and ctx.guild.id in configured_channels:
        if ctx.channel.id != configured_channels[ctx.guild.id]:
            return
    async with ctx.typing():
        scripts, err = await search_scriptblox(game)
        if err:
            return await ctx.reply(f"❌ {err}")
        await ctx.reply(embed=format_embed(scripts[0]))

@bot.command(name="scriptlist", aliases=["sl", "lista"])
async def scriptlist_cmd(ctx, *, game: str):
    if ctx.guild and ctx.guild.id in configured_channels:
        if ctx.channel.id != configured_channels[ctx.guild.id]:
            return
    async with ctx.typing():
        scripts, err = await search_scriptblox(game, 10)
        if err:
            return await ctx.reply(f"❌ {err}")
        embed = discord.Embed(title=f"🔍 {game}", description="Reaja com o número:", color=0x3498db)
        emojis = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        for i, s in enumerate(scripts[:10], 1):
            g = s.get("game", {}).get("name", "Universal")
            t = s.get("title", "Sem título")[:40]
            v = s.get("views", 0)
            p = "🟢" if not s.get("isPatched") else "🔴"
            k = "🔒" if s.get("key") else "🔓"
            embed.add_field(name=f"{emojis[i-1]} {p}{k} {t}", value=f"{g} | {v:,} views", inline=False)
        msg = await ctx.reply(embed=embed)
        for i in range(min(len(scripts), 10)):
            await msg.add_reaction(emojis[i])
        def check(r, u):
            return u == ctx.author and r.message.id == msg.id
        try:
            r, _ = await bot.wait_for("reaction_add", timeout=60.0, check=check)
            for i, e in enumerate(emojis):
                if str(r) == e and i < len(scripts):
                    await ctx.send(embed=format_embed(scripts[i]))
                    break
        except asyncio.TimeoutError:
            await ctx.send("⏰ Tempo esgotado!")

@bot.tree.command(name="script", description="Busca script para um jogo")
@app_commands.describe(game="Nome do jogo")
async def slash_script(interaction: discord.Interaction, game: str):
    if interaction.guild and interaction.guild.id in configured_channels:
        if interaction.channel.id != configured_channels[interaction.guild.id]:
            return await interaction.response.send_message("Canal errado!", ephemeral=True)
    await interaction.response.defer()
    scripts, err = await search_scriptblox(game)
    if err:
        return await interaction.followup.send(f"❌ {err}")
    await interaction.followup.send(embed=format_embed(scripts[0]))

@bot.tree.command(name="addchannel", description="Define canal do bot")
@app_commands.describe(channel="Canal")
async def slash_addchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ Sem permissão!", ephemeral=True)
    configured_channels[interaction.guild.id] = channel.id
    await interaction.response.send_message(f"✅ {channel.mention}")

bot.run(DISCORD_TOKEN)
