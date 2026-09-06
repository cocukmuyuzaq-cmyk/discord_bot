import discord
import aiohttp
import asyncio
import json
import os
import random
import io
import base64
from discord.ext import commands
from datetime import datetime, timedelta
from discord import app_commands

# Environment variables'dan oku
TOKEN = os.getenv('TOKEN') or os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions'

# DeAPI API Bilgileri - ENVIRONMENT'DAN OKU
DEAPI_API_KEY = os.getenv('DEAPI_API_KEY')
DEAPI_API_URL = "https://api.deapi.ai/api/v2/images/generations"

# Bot sahibi ID'si
OWNER_ID = 1482762948106784951

# Sunucu adı
SERVER_NAME = "Estanya"

# Port
PORT = int(os.getenv('PORT', 10000))

if not TOKEN:
    raise ValueError("❌ TOKEN environment variable'ı bulunamadı!")
if not GROQ_API_KEY:
    raise ValueError("❌ GROQ_API_KEY environment variable'ı bulunamadı!")
if not DEAPI_API_KEY:
    raise ValueError("❌ DEAPI_API_KEY environment variable'ı bulunamadı! Render'a eklemeyi unutma!")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Kullanıcı mesaj geçmişi
user_history = {}
MAX_HISTORY = 50

# Resim oluşturma limiti (günlük)
image_limits = {}
DAILY_IMAGE_LIMIT = 20

# Abonelik sistemi
subscriptions = {}

# Botun cevap vermesi gereken kelimeler
TRIGGER_WORDS = ["estanya", "bot", "yardım", "merhaba", "hello", "hi", "selam"]

# Kullanıcı konuşma durumu
user_chat_mode = {}

# Kullanıcı profilleri
user_profiles = {}

# Eğlence cevapları
fun_responses = [
    "😄 Bunu mu sordun? Vay be!",
    "🤔 Hmm, ilginç bir soru!",
    "😂 Tamam, bu soruyu beğendim!",
    "😎 Estanya bu soruyu çözer!",
    "🎉 Harika bir soru!",
    "💪 Bu soru Estanya'ya göre!",
    "🤗 Sorunun cevabı burada!",
    "🌟 Estanya her zaman yardımcı!",
    "🔥 Bu soru ateşli!",
    "🎯 Tam isabet!"
]

async def translate_to_english(text):
    """Google Translate API ile Türkçe'yi İngilizce'ye çevirir"""
    try:
        text = text.strip()
        if not text:
            return text
        
        translate_url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=tr&tl=en&dt=t&q={text.replace(' ', '%20')}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(translate_url) as response:
                if response.status == 200:
                    data = await response.json()
                    translated = data[0][0][0]
                    return translated
                else:
                    return text
    except:
        return text

@bot.event
async def on_ready():
    print(f'✅ Estanya Bot olarak giriş yapıldı!')
    print(f'📊 Bot ID: {bot.user.id}')
    print(f'👑 Sahip ID: {OWNER_ID}')
    print(f'🌐 Port: {PORT}')
    print(f'🏠 Sunucu: {SERVER_NAME}')
    print(f'🎨 Resim Motoru: DeAPI - Flux_2_Klein_4B_BF16')
    print(f'🔑 DeAPI Key: {"✅ Var" if DEAPI_API_KEY else "❌ Yok"}')
    
    for guild in bot.guilds:
        print(f'📌 Sunucu: {guild.name} (ID: {guild.id})')
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} slash komut senkronize edildi!")
    except Exception as e:
        print(f"⚠️ Slash komut senkronizasyon hatası: {e}")
    
    asyncio.create_task(run_http_server())

async def run_http_server():
    try:
        from aiohttp import web
        
        async def health_check(request):
            return web.Response(text=f"✅ Estanya Bot çalışıyor! Sunucu: {SERVER_NAME}")
        
        async def info(request):
            return web.json_response({
                "status": "online",
                "bot_name": "Estanya",
                "server": SERVER_NAME,
                "owner_id": OWNER_ID,
                "guilds": [guild.name for guild in bot.guilds],
                "image_engine": "DeAPI - Flux_2_Klein_4B_BF16"
            })
        
        app = web.Application()
        app.router.add_get('/', health_check)
        app.router.add_get('/health', health_check)
        app.router.add_get('/info', info)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host='0.0.0.0', port=PORT)
        await site.start()
        print(f"✅ HTTP sunucusu başlatıldı: http://0.0.0.0:{PORT}")
        await asyncio.Event().wait()
    except Exception as e:
        print(f"⚠️ HTTP sunucusu hatası: {e}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    user_id = message.author.id
    
    if user_id not in user_history:
        user_history[user_id] = []
    
    user_history[user_id].append(message.content)
    if len(user_history[user_id]) > MAX_HISTORY:
        user_history[user_id].pop(0)
    
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_chat_mode = user_chat_mode.get(user_id, {}).get("active", False)
    
    should_respond = (
        is_chat_mode or
        is_dm or
        bot.user in message.mentions or
        any(word in message.content.lower() for word in TRIGGER_WORDS)
    )
    
    if should_respond and not message.content.startswith('/') and not message.content.startswith('!'):
        content = message.content
        if bot.user in message.mentions:
            for mention in message.mentions:
                content = content.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
        content = content.strip()
        
        if not content:
            await message.channel.send('💭 Bir şey sormak ister misiniz?')
            return
        
        is_owner = (message.author.id == OWNER_ID)
        
        if random.random() < 0.1:
            await message.channel.send(random.choice(fun_responses))
            return
        
        async with message.channel.typing():
            try:
                history = user_history.get(user_id, [])[-5:]
                context = "\n".join(history) if history else ""
                
                system_message = f"""Sen Estanya botusun. {SERVER_NAME} sunucusunda yardımcı bir asistansın.
                Kullanıcının son mesajları: {context}
                Bot sahibi: <@{OWNER_ID}>
                """
                
                if is_owner:
                    system_message += " (Bot sahibisin, özel yetkilerin var!)"
                
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "model": "openai/gpt-oss-120b",
                        "messages": [
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": content}
                        ],
                        "temperature": 0.7,
                        "max_tokens": 1000
                    }
                    
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {GROQ_API_KEY}"
                    }
                    
                    async with session.post(GROQ_API_URL, json=payload, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            reply = data['choices'][0]['message']['content']
                            
                            if len(reply) > 2000:
                                for i in range(0, len(reply), 1900):
                                    await message.channel.send(reply[i:i+1900])
                            else:
                                await message.channel.send(reply)
                        else:
                            await message.channel.send(f'❌ Hata oluştu, lütfen tekrar deneyin.')
                            
            except Exception as e:
                await message.channel.send(f'❌ Bir hata oluştu, lütfen tekrar deneyin.')
    
    await bot.process_commands(message)

async def handle_image_request(interaction, prompt):
    """DeAPI ile resim oluşturur"""
    user_id = interaction.user.id
    
    # Günlük limit kontrolü
    today = datetime.now().date()
    if user_id not in image_limits:
        image_limits[user_id] = {"count": 0, "date": today}
    
    if image_limits[user_id]["date"] != today:
        image_limits[user_id] = {"count": 0, "date": today}
    
    if image_limits[user_id]["count"] >= DAILY_IMAGE_LIMIT:
        await interaction.followup.send(f"⚠️ Günlük resim limitine ulaştınız! ({DAILY_IMAGE_LIMIT} resim/gün).")
        return
    
    prompt = prompt.strip()
    if len(prompt) < 2:
        await interaction.followup.send("❌ Lütfen daha açıklayıcı bir şey yazın! Örnek: `/resim siyah spor araba`")
        return
    
    # Hazırlanıyor mesajı
    await interaction.followup.send("🎨 **Resminiz Hazırlanıyor...**\n⏳ DeAPI ile oluşturuluyor...")
    
    try:
        async with asyncio.timeout(60):
            # Türkçe'yi İngilizce'ye çevir
            english_prompt = await translate_to_english(prompt)
            
            if not english_prompt or english_prompt == prompt:
                english_prompt = prompt
            
            # DeAPI'ye istek
            headers = {
                "accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {DEAPI_API_KEY}"
            }
            
            payload = {
                "prompt": english_prompt,
                "model": "Flux_2_Klein_4B_BF16",
                "width": 1024,
                "height": 1024,
                "steps": 4,
                "seed": random.randint(1, 999999999)
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(DEAPI_API_URL, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if "data" in data and len(data["data"]) > 0:
                            image_data_b64 = data["data"][0].get("b64_json")
                            if image_data_b64:
                                image_bytes = base64.b64decode(image_data_b64)
                                file = discord.File(io.BytesIO(image_bytes), filename="resim.png")
                                
                                embed = discord.Embed(
                                    title="🎨 Estanya Resim Oluşturdu!",
                                    description=f"**İstediğin:** `{prompt}`\n**Motor:** Flux_2_Klein_4B_BF16 (DeAPI)",
                                    color=discord.Color.gold()
                                )
                                embed.set_image(url="attachment://resim.png")
                                embed.set_footer(text=f"Kalan hak: {DAILY_IMAGE_LIMIT - image_limits[user_id]['count'] - 1} / {DAILY_IMAGE_LIMIT} (günlük)")
                                
                                await interaction.edit_original_response(content=None, embed=embed, attachments=[file])
                                
                                image_limits[user_id]["count"] += 1
                                return
                            else:
                                image_url = data["data"][0].get("url")
                                if image_url:
                                    async with session.get(image_url) as img_response:
                                        if img_response.status == 200:
                                            image_data = await img_response.read()
                                            file = discord.File(io.BytesIO(image_data), filename="resim.png")
                                            
                                            embed = discord.Embed(
                                                title="🎨 Estanya Resim Oluşturdu!",
                                                description=f"**İstediğin:** `{prompt}`\n**Motor:** Flux_2_Klein_4B_BF16 (DeAPI)",
                                                color=discord.Color.gold()
                                            )
                                            embed.set_image(url="attachment://resim.png")
                                            embed.set_footer(text=f"Kalan hak: {DAILY_IMAGE_LIMIT - image_limits[user_id]['count'] - 1} / {DAILY_IMAGE_LIMIT} (günlük)")
                                            
                                            await interaction.edit_original_response(content=None, embed=embed, attachments=[file])
                                            
                                            image_limits[user_id]["count"] += 1
                                            return
                        
                        await interaction.edit_original_response(content="❌ Resim verisi alınamadı, lütfen tekrar deneyin.")
                    else:
                        error_text = await response.text()
                        await interaction.edit_original_response(content=f"❌ API hatası: {response.status}")
                        
    except asyncio.TimeoutError:
        await interaction.edit_original_response(content="⏰ **Zaman aşımı!** 60 saniye doldu, lütfen tekrar deneyin.")
    except Exception as e:
        await interaction.edit_original_response(content=f"❌ Resim oluşturulamadı, lütfen tekrar deneyin.")

# ----- SLASH KOMUTLAR -----

@bot.tree.command(name="resim", description="AI ile resim oluşturur (DeAPI)")
@app_commands.describe(prompt="Ne çizmesini istediğinizi yazın")
async def slash_resim(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    await handle_image_request(interaction, prompt)

@bot.tree.command(name="konuşma", description="Sohbet modunu açar/kapatır")
async def slash_konusma(interaction: discord.Interaction):
    user_id = interaction.user.id
    
    if user_id not in user_chat_mode:
        user_chat_mode[user_id] = {"active": False, "channel_id": None}
    
    current_mode = user_chat_mode[user_id]["active"]
    
    if current_mode:
        user_chat_mode[user_id] = {"active": False, "channel_id": None}
        embed = discord.Embed(title="🔇 Sohbet Modu Kapatıldı", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)
    else:
        user_chat_mode[user_id] = {"active": True, "channel_id": interaction.channel_id}
        embed = discord.Embed(
            title="💬 Sohbet Modu Aktif!",
            description="Artık her mesajına cevap vereceğim! Kapatmak için `/konuşma` yaz.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="limit", description="Kalan resim hakkını gösterir")
async def slash_limit(interaction: discord.Interaction):
    user_id = interaction.user.id
    today = datetime.now().date()
    
    if user_id not in image_limits or image_limits[user_id]["date"] != today:
        kalan = DAILY_IMAGE_LIMIT
    else:
        kalan = DAILY_IMAGE_LIMIT - image_limits[user_id]["count"]
    
    embed = discord.Embed(
        title="📊 Resim Hakkınız",
        description=f"**Kalan:** {kalan} / {DAILY_IMAGE_LIMIT} (günlık)\n**Motor:** Flux_2_Klein_4B_BF16",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Yardım mesajını gösterir")
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Estanya Bot",
        description=f"**👑 Bot Sahibi:** <@{OWNER_ID}>\n**🏠 Sunucu:** {SERVER_NAME}",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="📝 Özellikler",
        value="• 🎨 **Flux_2_Klein_4B_BF16** ile resim (DeAPI)\n• 💬 Sohbet modu\n• 📜 Mesaj geçmişi\n• 📊 Günlük 20 resim limiti\n• 🌐 Otomatik çeviri",
        inline=False
    )
    embed.add_field(
        name="🔧 Slash Komutlar",
        value="`/resim` - Resim oluşturur\n`/konuşma` - Sohbet modu\n`/limit` - Kalan hak\n`/help` - Yardım",
        inline=False
    )
    embed.set_footer(text="Estanya Bot | DeAPI ile güçlendirildi!")
    await interaction.response.send_message(embed=embed)

# ----- NORMAL KOMUTLAR -----

@bot.command(name='resim')
async def image_command(ctx, *, prompt):
    class FakeInteraction:
        def __init__(self, user, channel):
            self.user = user
            self.channel = channel
        
        async def defer(self):
            pass
        
        async def followup(self):
            return self
        
        async def edit_original_response(self, content=None, embed=None, attachments=None):
            if embed and attachments:
                await self.channel.send(embed=embed, file=attachments[0])
            elif content:
                await self.channel.send(content)
    
    fake_interaction = FakeInteraction(ctx.author, ctx.channel)
    await handle_image_request(fake_interaction, prompt)

@bot.command(name='konuşma')
async def chat_mode_command(ctx):
    user_id = ctx.author.id
    if user_id not in user_chat_mode:
        user_chat_mode[user_id] = {"active": False, "channel_id": None}
    
    current_mode = user_chat_mode[user_id]["active"]
    if current_mode:
        user_chat_mode[user_id] = {"active": False, "channel_id": None}
        await ctx.send("🔇 Sohbet modu kapatıldı!")
    else:
        user_chat_mode[user_id] = {"active": True, "channel_id": ctx.channel.id}
        await ctx.send("💬 Sohbet modu aktif! Kapatmak için `!kapat` yaz.")

@bot.command(name='kapat')
async def close_chat_mode(ctx):
    user_id = ctx.author.id
    user_chat_mode[user_id] = {"active": False, "channel_id": None}
    await ctx.send("🔇 Sohbet modu kapatıldı!")

@bot.command(name='limit')
async def check_limit(ctx):
    user_id = ctx.author.id
    today = datetime.now().date()
    
    if user_id not in image_limits or image_limits[user_id]["date"] != today:
        kalan = DAILY_IMAGE_LIMIT
    else:
        kalan = DAILY_IMAGE_LIMIT - image_limits[user_id]["count"]
    
    await ctx.send(f"📊 **Kalan resim hakkınız:** {kalan} / {DAILY_IMAGE_LIMIT} (günlük)")

@bot.command(name='help_ai')
async def help_command(ctx):
    embed = discord.Embed(
        title="🤖 Estanya Bot",
        description=f"**👑 Bot Sahibi:** <@{OWNER_ID}>",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="📝 Özellikler",
        value="• 🎨 **Flux_2_Klein_4B_BF16** ile resim\n• 💬 Sohbet modu\n• 📜 Mesaj geçmişi\n• 📊 Günlük 20 resim limiti",
        inline=False
    )
    embed.add_field(
        name="🔧 Komutlar",
        value="`/resim` - Resim oluşturur\n`/konuşma` - Sohbet modu\n`/limit` - Kalan hak\n`/help` - Yardım",
        inline=False
    )
    await ctx.send(embed=embed)

if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Token hatası!")
    except Exception as e:
        print(f"❌ Bot başlatılamadı: {e}")