import discord
import aiohttp
import asyncio
import json
import os
import random
import base64
from discord.ext import commands
from datetime import datetime, timedelta

# Environment variables'dan oku
TOKEN = os.getenv('TOKEN') or os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions'

# Bot sahibi ID'si
OWNER_ID = 1482762948106784951

# Sunucu adı
SERVER_NAME = "Estanya"

# Port ayarı (Render için en iyi port)
PORT = int(os.getenv('PORT', 10000))

if not TOKEN:
    raise ValueError("❌ TOKEN environment variable'ı bulunamadı!")
if not GROQ_API_KEY:
    raise ValueError("❌ GROQ_API_KEY environment variable'ı bulunamadı!")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Kullanıcı mesaj geçmişi (son 50 mesaj)
user_history = {}
MAX_HISTORY = 50

# Resim oluşturma limiti (günlük 5 resim)
image_limits = {}
DAILY_IMAGE_LIMIT = 5

# Ücretsiz resim API'si (Pollinations.ai - tamamen ücretsiz)
IMAGE_API_URL = "https://image.pollinations.ai/prompt/"

# Botun cevap vermesi gereken kelimeler (trigger keywords)
TRIGGER_WORDS = ["estanya", "bot", "yardım", "merhaba", "hello", "hi", "selam"]

@bot.event
async def on_ready():
    print(f'✅ /estanya bot olarak giriş yapıldı!')
    print(f'📊 Bot ID: {bot.user.id}')
    print(f'🏠 Sunucu: {SERVER_NAME}')
    print(f'👑 Sahip ID: {OWNER_ID}')
    print(f'🌐 Port: {PORT}')
    print(f'🎨 Resim API: Pollinations.ai (ücretsiz)')
    
    # Botun bulunduğu sunucuları listele
    for guild in bot.guilds:
        print(f'📌 Sunucu: {guild.name} (ID: {guild.id})')
    
    # HTTP sunucusunu başlat (Render için)
    asyncio.create_task(run_http_server())

async def run_http_server():
    """Render'da botun çalıştığını göstermek için HTTP sunucusu"""
    try:
        from aiohttp import web
        
        async def health_check(request):
            return web.Response(text=f"✅ /estanya bot çalışıyor! Sunucu: {SERVER_NAME}")
        
        async def info(request):
            return web.json_response({
                "status": "online",
                "bot_name": "estanya",
                "server": SERVER_NAME,
                "owner_id": OWNER_ID,
                "guilds": [guild.name for guild in bot.guilds],
                "image_api": "Pollinations.ai (ücretsiz)",
                "daily_image_limit": DAILY_IMAGE_LIMIT
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
    # Botun kendi mesajlarını yoksay
    if message.author.bot:
        return
    
    # Kullanıcı mesaj geçmişini güncelle
    user_id = message.author.id
    if user_id not in user_history:
        user_history[user_id] = []
    
    user_history[user_id].append(message.content)
    if len(user_history[user_id]) > MAX_HISTORY:
        user_history[user_id].pop(0)
    
    # Bot etiketlendiğinde, DM'de veya trigger kelimelerle yanıt ver
    should_respond = (
        bot.user in message.mentions or 
        isinstance(message.channel, discord.DMChannel) or
        any(word in message.content.lower() for word in TRIGGER_WORDS)
    )
    
    if should_respond:
        # Mesajı temizle (bot etiketini kaldır)
        content = message.content
        if bot.user in message.mentions:
            for mention in message.mentions:
                content = content.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
        content = content.strip()
        
        # Eğer sadece trigger kelime varsa ve başka içerik yoksa
        if not content or content.lower() in TRIGGER_WORDS:
            await message.channel.send(f"👋 Merhaba! Ben /estanya bot. Yardım için `!help_ai` yazabilirsiniz. DM'den de konuşabiliriz!")
            return
        
        # Resim yapma komutu kontrolü
        if "/resim" in content.lower() or "resim yap" in content.lower() or "draw" in content.lower():
            await handle_image_request(message, content)
            return
        
        # Bot sahibi kontrolü
        is_owner = (message.author.id == OWNER_ID)
        
        # Normal AI yanıtı
        async with message.channel.typing():
            try:
                # Kullanıcının son mesajlarını al
                history = user_history.get(user_id, [])[-5:]
                context = "\n".join(history) if history else ""
                
                # Botun adını ve özelliklerini sistem mesajına ekle
                system_message = f"""Sen /estanya botusun. {SERVER_NAME} sunucusunda yardımcı bir asistansın.
                Kullanıcının son mesajları: {context}
                Bot sahibi: <@{OWNER_ID}>
                Özelliklerin: DM'de konuşabilirsin, mesaj geçmişini hatırlarsın, /resim ile ücretsiz resim yapabilirsin (Pollinations.ai).
                Eğer kullanıcı İngilizce bir şey isterse, "Lütfen Türkçe yazın / Please write in Turkish" diyerek Türkçe yazmasını iste.
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
                            
                            # Eğer İngilizce tespit edilirse uyarı ekle
                            if any(char in reply for char in "abcdefghijklmnopqrstuvwxyz") and len(reply) > 10:
                                if not any(char in reply for char in "çğıöşü"):
                                    reply += "\n\n💡 Lütfen Türkçe yazın / Please write in Turkish"
                            
                            if len(reply) > 2000:
                                for i in range(0, len(reply), 1900):
                                    await message.channel.send(reply[i:i+1900])
                            else:
                                await message.channel.send(reply)
                        else:
                            await message.channel.send(f'❌ API hatası: {response.status}')
                            
            except Exception as e:
                await message.channel.send(f'❌ Hata: {str(e)}')
    
    await bot.process_commands(message)

async def handle_image_request(message, content):
    """Resim oluşturma isteğini işler"""
    user_id = message.author.id
    
    # Günlük limit kontrolü
    today = datetime.now().date()
    if user_id not in image_limits:
        image_limits[user_id] = {"count": 0, "date": today}
    
    if image_limits[user_id]["date"] != today:
        image_limits[user_id] = {"count": 0, "date": today}
    
    if image_limits[user_id]["count"] >= DAILY_IMAGE_LIMIT:
        await message.channel.send(f"⚠️ Günlük resim limitine ulaştınız! ({DAILY_IMAGE_LIMIT} resim/gün). Yarın tekrar deneyin.")
        return
    
    # Resim prompt'unu çıkar
    prompt = content.lower().replace("/resim", "").replace("resim yap", "").replace("draw", "").strip()
    if not prompt:
        await message.channel.send("❌ Ne çizmem gerektiğini yazın! Örnek: `/resim kedi`")
        return
    
    # Prompt'u İngilizce'ye çevir (Pollinations.ai İngilizce anlıyor)
    english_prompt = prompt  # Basit tutalım, kullanıcı İngilizce yazarsa daha iyi olur
    
    async with message.channel.typing():
        try:
            # Pollinations.ai API'si (ücretsiz)
            image_url = f"{IMAGE_API_URL}{english_prompt.replace(' ', '%20')}?width=512&height=512&nologo=true"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        # Resmi indir
                        image_data = await response.read()
                        
                        # Discord'a resim gönder
                        file = discord.File(io.BytesIO(image_data), filename="resim.png")
                        await message.channel.send(
                            f"🎨 **İşte resmin!**\nPrompt: `{prompt}`\nAPI: Pollinations.ai (ücretsiz)",
                            file=file
                        )
                        
                        # Limiti güncelle
                        image_limits[user_id]["count"] += 1
                        kalan = DAILY_IMAGE_LIMIT - image_limits[user_id]["count"]
                        await message.channel.send(f"📊 Bugün kalan resim hakkınız: {kalan}")
                    else:
                        await message.channel.send(f"❌ Resim oluşturulamadı! Hata: {response.status}")
                        
        except Exception as e:
            await message.channel.send(f"❌ Resim hatası: {str(e)}")

@bot.command(name='resim')
async def image_command(ctx, *, prompt):
    """Resim oluşturur: !resim kedi"""
    await handle_image_request(ctx.message, f"/resim {prompt}")

@bot.command(name='limit')
async def check_limit(ctx):
    """Kalan resim hakkını gösterir"""
    user_id = ctx.author.id
    today = datetime.now().date()
    
    if user_id not in image_limits or image_limits[user_id]["date"] != today:
        kalan = DAILY_IMAGE_LIMIT
    else:
        kalan = DAILY_IMAGE_LIMIT - image_limits[user_id]["count"]
    
    await ctx.send(f"📊 **Kalan resim hakkınız:** {kalan} / {DAILY_IMAGE_LIMIT} (günlük)")

@bot.command(name='history')
async def show_history(ctx):
    """Kendi mesaj geçmişini gösterir"""
    user_id = ctx.author.id
    history = user_history.get(user_id, [])
    if not history:
        await ctx.send("📭 Henüz hiç mesaj geçmişiniz yok!")
    else:
        history_text = "\n".join([f"{i+1}. {msg}" for i, msg in enumerate(history[-10:])])
        await ctx.send(f"📜 **Son {len(history)} mesajınız:**\n{history_text[:1900]}")

@bot.command(name='clear_history')
async def clear_history(ctx):
    """Mesaj geçmişini temizler"""
    user_id = ctx.author.id
    if user_id in user_history:
        user_history[user_id] = []
        await ctx.send("🧹 Mesaj geçmişiniz temizlendi!")
    else:
        await ctx.send("📭 Zaten hiç mesaj geçmişiniz yok!")

@bot.command(name='server')
async def server_info(ctx):
    """Sunucu bilgisini gösterir"""
    if ctx.guild:
        await ctx.send(f"🏠 **Sunucu:** {ctx.guild.name}\n👥 **Üye Sayısı:** {ctx.guild.member_count}\n👑 **Sahibim:** <@{OWNER_ID}>")
    else:
        await ctx.send("Bu komut sadece sunucularda kullanılabilir!")

@bot.command(name='owner')
async def owner_info(ctx):
    """Bot sahibi bilgisini gösterir"""
    await ctx.send(f"👑 **Bot Sahibi:** <@{OWNER_ID}> (ID: {OWNER_ID})")

@bot.command(name='ping')
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f'🏓 Pong! Gecikme: {latency}ms')

@bot.command(name='help_ai')
async def help_command(ctx):
    help_text = f"""
🤖 **/estanya Bot - {SERVER_NAME}**

**👑 Bot Sahibi:** <@{OWNER_ID}>

**📝 Özellikler:**
• 📜 **Mesaj Geçmişi:** Son 50 mesajınızı hatırlar
• 💬 **DM Desteği:** Özel mesajlarda da konuşabilirsiniz
• 🎨 **Resim Oluşturma:** `/resim` ile ücretsiz resim yapar (Pollinations.ai)
• 📊 **Günlük Limit:** {DAILY_IMAGE_LIMIT} resim/gün
• 🌐 **Bağlam:** Son 5 mesajınızı hatırlar
• 🇹🇷 **Türkçe Zorunluluğu:** İngilizce yazarsanız uyarır

**Kullanım:**
1. **Etiketleme:** Botu etiketleyip soru sorun
   Örnek: `@estanya Nasıl yapabilirim?`
2. **Trigger Kelimeler:** "estanya", "bot", "yardım" gibi kelimelerle çağırın
3. **Özel Mesaj:** Bota doğrudan DM gönderin
4. **Resim Yapma:** `/resim kedi` veya `!resim kedi`

**Komutlar:**
• `!resim <açıklama>` - Resim oluşturur
• `!limit` - Kalan resim hakkını gösterir
• `!history` - Son 10 mesajınızı gösterir
• `!clear_history` - Mesaj geçmişinizi temizler
• `!server` - Sunucu bilgisini gösterir
• `!owner` - Bot sahibini gösterir
• `!ping` - Bot gecikmesini gösterir
• `!help_ai` - Bu yardım mesajını gösterir

**Sunucu:** {SERVER_NAME}
**Port:** {PORT}
**Resim API:** Pollinations.ai (ücretsiz)
    """
    await ctx.send(help_text)

if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Token hatası! Lütfen token'ınızı kontrol edin.")
    except Exception as e:
        print(f"❌ Bot başlatılamadı: {e}")
