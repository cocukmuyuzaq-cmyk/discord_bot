import discord
import aiohttp
import asyncio
import json
import os
import random
import io
import re
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

# Port
PORT = int(os.getenv('PORT', 10000))

if not TOKEN:
    raise ValueError("❌ TOKEN environment variable'ı bulunamadı!")
if not GROQ_API_KEY:
    raise ValueError("❌ GROQ_API_KEY environment variable'ı bulunamadı!")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Kullanıcı mesaj geçmişi
user_history = {}
MAX_HISTORY = 50

# Resim oluşturma limiti
image_limits = {}
DAILY_IMAGE_LIMIT = 5

# Abonelik sistemi
subscriptions = {}  # {user_id: {"type": "gold"/"premium"/"free", "expiry": timestamp}}

# Resim API'si
IMAGE_API_URL = "https://image.pollinations.ai/prompt/"

# Botun cevap vermesi gereken kelimeler
TRIGGER_WORDS = ["estanya", "bot", "yardım", "merhaba", "hello", "hi", "selam"]

# Kullanıcı konuşma durumu
user_chat_mode = {}

async def translate_to_english(text):
    """Google Translate API ile Türkçe'yi İngilizce'ye çevirir"""
    try:
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
    
    for guild in bot.guilds:
        print(f'📌 Sunucu: {guild.name} (ID: {guild.id})')
    
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
                "guilds": [guild.name for guild in bot.guilds]
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
    
    # Kullanıcı mesaj geçmişini güncelle
    user_id = message.author.id
    if user_id not in user_history:
        user_history[user_id] = []
    
    user_history[user_id].append(message.content)
    if len(user_history[user_id]) > MAX_HISTORY:
        user_history[user_id].pop(0)
    
    # DM veya özel konuşma modu
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_chat_mode = user_chat_mode.get(user_id, False)
    
    # /resim komutu
    if message.content.startswith('/resim') or message.content.startswith('!resim'):
        await handle_image_request(message, message.content)
        return
    
    # /konuşma komutu
    if message.content.startswith('/konuşma') or message.content.startswith('!konuşma'):
        user_chat_mode[user_id] = True
        await message.channel.send("💬 **Sohbet modu aktif!** Artık her mesajına cevap vereceğim. Kapatmak için `/kapat` yaz.")
        return
    
    if message.content.startswith('/kapat') or message.content.startswith('!kapat'):
        user_chat_mode[user_id] = False
        await message.channel.send("🔇 **Sohbet modu kapatıldı!** Artık sadece etiketlendiğimde cevap vereceğim.")
        return
    
    # /abonelik komutu
    if message.content.startswith('/abonelik') or message.content.startswith('!abonelik'):
        await handle_subscription(message)
        return
    
    # Yanıt verme koşulları
    should_respond = (
        is_chat_mode or
        is_dm or
        bot.user in message.mentions or
        any(word in message.content.lower() for word in TRIGGER_WORDS)
    )
    
    if should_respond and not message.content.startswith('!'):
        content = message.content
        if bot.user in message.mentions:
            for mention in message.mentions:
                content = content.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
        content = content.strip()
        
        if not content:
            await message.channel.send('💭 Bir şey sormak ister misiniz?')
            return
        
        is_owner = (message.author.id == OWNER_ID)
        
        async with message.channel.typing():
            try:
                history = user_history.get(user_id, [])[-5:]
                context = "\n".join(history) if history else ""
                
                system_message = f"""Sen Estanya botusun. {SERVER_NAME} sunucusunda yardımcı bir asistansın.
                Kullanıcının son mesajları: {context}
                Bot sahibi: <@{OWNER_ID}>
                Özelliklerin: DM'de konuşabilirsin, mesaj geçmişini hatırlarsın, resim yapabilirsin.
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

async def handle_image_request(message, content):
    """Resim oluşturma isteğini işler - 5 dakika timeout ile"""
    user_id = message.author.id
    
    # Abonelik kontrolü
    sub_info = subscriptions.get(user_id, {"type": "free", "expiry": None})
    if sub_info["type"] == "free":
        # Free kullanıcılar için limit
        today = datetime.now().date()
        if user_id not in image_limits:
            image_limits[user_id] = {"count": 0, "date": today}
        
        if image_limits[user_id]["date"] != today:
            image_limits[user_id] = {"count": 0, "date": today}
        
        if image_limits[user_id]["count"] >= DAILY_IMAGE_LIMIT:
            await message.channel.send(f"⚠️ Günlük resim limitine ulaştınız! ({DAILY_IMAGE_LIMIT} resim/gün).\n📌 Daha fazla resim için `/abonelik` yazın.")
            return
    elif sub_info["type"] == "premium":
        # Premium kullanıcılar için limit yok
        pass
    elif sub_info["type"] == "gold":
        # Gold kullanıcılar için limit yok + özel kalite
        pass
    
    # Resim prompt'unu çıkar
    prompt = content.replace('/resim', '').replace('!resim', '').strip()
    if not prompt:
        await message.channel.send("❌ Ne çizmem gerektiğini yazın! Örnek: `/resim siyah araba`")
        return
    
    # "Resminiz Hazırlanıyor..." mesajı
    status_msg = await message.channel.send("🎨 **Resminiz Hazırlanıyor...**\n⏳ Bu işlem birkaç saniye sürebilir...")
    
    try:
        # 5 dakika timeout ile resim oluştur
        async with asyncio.timeout(300):  # 5 dakika
            # Google Translate ile Türkçe'yi İngilizce'ye çevir
            english_prompt = await translate_to_english(prompt)
            
            # URL encode yap
            encoded_prompt = english_prompt.replace(' ', '%20')
            image_url = f"{IMAGE_API_URL}{encoded_prompt}?width=512&height=512&nologo=true"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        
                        file = discord.File(io.BytesIO(image_data), filename="resim.png")
                        
                        # Abonelik tipine göre embed rengi
                        if sub_info["type"] == "gold":
                            color = discord.Color.gold()
                            sub_text = "👑 Gold Üye"
                        elif sub_info["type"] == "premium":
                            color = discord.Color.purple()
                            sub_text = "💎 Premium Üye"
                        else:
                            color = discord.Color.blue()
                            sub_text = "📌 Free Üye"
                        
                        embed = discord.Embed(
                            title="🎨 Estanya Resim Oluşturdu!",
                            description=f"**İstediğin:** `{prompt}`\n**Abonelik:** {sub_text}",
                            color=color
                        )
                        embed.set_image(url="attachment://resim.png")
                        
                        # Kalan hak
                        if sub_info["type"] == "free":
                            kalan = DAILY_IMAGE_LIMIT - image_limits[user_id]["count"] - 1
                            embed.set_footer(text=f"Kalan hak: {kalan} / {DAILY_IMAGE_LIMIT} (günlük)")
                        else:
                            embed.set_footer(text="🌟 Sınırsız resim hakkı!")
                        
                        # Hazırlanıyor mesajını sil ve resmi gönder
                        await status_msg.delete()
                        await message.channel.send(embed=embed, file=file)
                        
                        # Limiti güncelle (sadece free kullanıcılar için)
                        if sub_info["type"] == "free":
                            image_limits[user_id]["count"] += 1
                    else:
                        await status_msg.edit(content="❌ Resim oluşturulamadı, lütfen tekrar deneyin.")
                        
    except asyncio.TimeoutError:
        # 5 dakika geçtiyse iptal et
        await status_msg.edit(content="⏰ **Resim oluşturma iptal edildi!**\n5 dakikadan uzun sürdüğü için işlem iptal edildi. Lütfen tekrar deneyin.")
    except discord.Forbidden:
        await status_msg.edit(content="❌ **Yetki hatası!** Botun resim gönderme izni yok.")
    except Exception as e:
        await status_msg.edit(content=f"❌ Resim oluşturulamadı, lütfen tekrar deneyin.")

async def handle_subscription(message):
    """Abonelik sistemi - Yakında gelecek mesajı"""
    user_id = message.author.id
    sub_info = subscriptions.get(user_id, {"type": "free", "expiry": None})
    
    embed = discord.Embed(
        title="📋 Estanya Abonelik Sistemi",
        description="**Yakında!** 🚀",
        color=discord.Color.gold()
    )
    embed.add_field(
        name="📌 Mevcut Planınız",
        value=f"**{sub_info['type'].upper()}**",
        inline=False
    )
    embed.add_field(
        name="🌟 Yakında Gelecek Özellikler",
        value="• Sınırsız resim oluşturma\n• Özel kalite seçenekleri\n• Öncelikli işlem\n• Özel destek",
        inline=False
    )
    embed.add_field(
        name="📅 Tarih",
        value="**Yakında duyurulacak!**",
        inline=False
    )
    embed.set_footer(text="Estanya Bot | Abonelik sistemi hazırlanıyor...")
    
    await message.channel.send(embed=embed)

# ----- KOMUTLAR -----

@bot.command(name='resim')
async def image_command(ctx, *, prompt):
    """Resim oluşturur: !resim siyah araba"""
    await handle_image_request(ctx.message, f"!resim {prompt}")

@bot.command(name='konuşma')
async def chat_mode_command(ctx):
    """Sohbet modunu açar"""
    user_chat_mode[ctx.author.id] = True
    await ctx.send("💬 **Sohbet modu aktif!** Artık her mesajına cevap vereceğim. Kapatmak için `!kapat` yaz.")

@bot.command(name='kapat')
async def close_chat_mode(ctx):
    """Sohbet modunu kapatır"""
    user_chat_mode[ctx.author.id] = False
    await ctx.send("🔇 **Sohbet modu kapatıldı!** Artık sadece etiketlendiğimde cevap vereceğim.")

@bot.command(name='abonelik')
async def subscription_command(ctx):
    """Abonelik bilgilerini gösterir"""
    await handle_subscription(ctx.message)

@bot.command(name='limit')
async def check_limit(ctx):
    """Kalan resim hakkını gösterir"""
    user_id = ctx.author.id
    sub_info = subscriptions.get(user_id, {"type": "free", "expiry": None})
    
    if sub_info["type"] != "free":
        await ctx.send(f"🌟 **{sub_info['type'].upper()}** üyesisiniz! Sınırsız resim hakkınız var!")
        return
    
    today = datetime.now().date()
    if user_id not in image_limits or image_limits[user_id]["date"] != today:
        kalan = DAILY_IMAGE_LIMIT
    else:
        kalan = DAILY_IMAGE_LIMIT - image_limits[user_id]["count"]
    
    await ctx.send(f"📊 **Kalan resim hakkınız:** {kalan} / {DAILY_IMAGE_LIMIT} (günlük)\n📌 Daha fazla için `/abonelik` yazın.")

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
🤖 **Estanya Bot**

**👑 Bot Sahibi:** <@{OWNER_ID}>

**📝 Özellikler:**
• 📜 **Mesaj Geçmişi:** Son 50 mesajınızı hatırlar
• 💬 **Sohbet Modu:** Sürekli sohbet modu (aç/kapat)
• 🎨 **Resim Oluşturma:** Ücretsiz resim yapar
• 📊 **Günlük Limit:** {DAILY_IMAGE_LIMIT} resim/gün (Free)
• 🌐 **Otomatik Çeviri:** Türkçe prompt'ları İngilizce'ye çevirir
• ⏰ **5 Dakika Timeout:** Uzun süren işlemler iptal edilir
• 📋 **Abonelik Sistemi:** Yakında!

**Kullanım:**
• `/konuşma` - Sohbet modunu açar
• `/kapat` - Sohbet modunu kapatır
• `/resim <açıklama>` - Resim oluşturur
• `/abonelik` - Abonelik bilgilerini gösterir
• `@Estanya` - Botu etiketleyip soru sorun

**Komutlar:**
• `/konuşma` veya `!konuşma` - Sohbet modunu açar
• `/kapat` veya `!kapat` - Sohbet modunu kapatır
• `/resim <açıklama>` veya `!resim <açıklama>` - Resim oluşturur
• `/abonelik` veya `!abonelik` - Abonelik bilgilerini gösterir
• `!limit` - Kalan resim hakkını gösterir
• `!history` - Son 10 mesajınızı gösterir
• `!clear_history` - Mesaj geçmişinizi temizler
• `!server` - Sunucu bilgisini gösterir
• `!owner` - Bot sahibini gösterir
• `!ping` - Bot gecikmesini gösterir
• `!help_ai` - Bu yardım mesajını gösterir

**Sunucu:** {SERVER_NAME}
    """
    await ctx.send(help_text)

if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Token hatası! Lütfen token'ınızı kontrol edin.")
    except Exception as e:
        print(f"❌ Bot başlatılamadı: {e}")
