import discord
import aiohttp
import asyncio
import json
import os
import random
from discord.ext import commands

# Environment variables'dan oku
TOKEN = os.getenv('TOKEN') or os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions'

# Bot sahibi ID'si (değiştirin!)
OWNER_ID = 75  # Buraya kendi Discord ID'nizi yazın (sayısal)

# Sunucu adı
SERVER_NAME = "Estanya"

if not TOKEN:
    raise ValueError("❌ TOKEN environment variable'ı bulunamadı!")
if not GROQ_API_KEY:
    raise ValueError("❌ GROQ_API_KEY environment variable'ı bulunamadı!")

intents = discord.Intents.all()  # Tüm intent'leri aç (mesaj geçmişi için)
bot = commands.Bot(command_prefix='!', intents=intents)

# Kullanıcı mesaj geçmişi (son 50 mesaj)
user_history = {}
MAX_HISTORY = 50

# Eğlenceli cevaplar
funny_responses = [
    "🤣 Bu soruyu sorduğuna göre çok eğleniyorsun!",
    "😄 Harika bir soru! Cevabı: 42 (her şeyin cevabı)",
    "🤪 Ben bir botum ama sen benden daha bot davranıyorsun!",
    "😂 Bu soruyu cevaplamak için kahve molası veriyorum...",
    "😅 Bak şimdi, bu soru beni aştı! Ama deneyelim..."
]

# Küfürlü mod cevapları (sadece bot sahibine özel)
curse_responses = [
    "Sana bunun cevabını mı versem? 😏",
    "Yok artık! Bu soruya cevap vermek çok zor! 🤬",
    "Küfür mü edelim? Ben yapmam, ama sen edebilirsin! 😈",
    "Bak bu soruya cevap vermek için 'sihirli kelime' lazım! 🧙"
]

@bot.event
async def on_ready():
    print(f'✅ {bot.user} olarak giriş yapıldı!')
    print(f'📊 Bot ID: {bot.user.id}')
    print(f'🏠 Sunucu: {SERVER_NAME}')
    print(f'👑 Sahip ID: {OWNER_ID}')
    print(f'🔑 Groq API: {"✓" if GROQ_API_KEY else "✗"}')
    
    # Botun bulunduğu sunucuları listele
    for guild in bot.guilds:
        print(f'📌 Sunucu: {guild.name} (ID: {guild.id})')

@bot.event
async def on_message(message):
    # Botun kendi mesajlarını yoksay
    if message.author.bot:
        return
    
    # Sadece "Estanya" sunucusunda çalış (isteğe bağlı)
    if message.guild and message.guild.name != SERVER_NAME:
        # Eğer özel mesaj ise veya farklı sunucuda çalışmasını istiyorsanız bu kısmı yorum satırı yapın
        # await bot.process_commands(message)
        # return
        pass  # Şimdilik tüm sunucularda çalışsın
    
    # Kullanıcı mesaj geçmişini güncelle
    user_id = message.author.id
    if user_id not in user_history:
        user_history[user_id] = []
    
    user_history[user_id].append(message.content)
    if len(user_history[user_id]) > MAX_HISTORY:
        user_history[user_id].pop(0)
    
    # Bot etiketlendiğinde veya özel mesajda yanıt ver
    if bot.user in message.mentions or isinstance(message.channel, discord.DMChannel):
        # Mesajı temizle (bot etiketini kaldır)
        content = message.content
        if bot.user in message.mentions:
            for mention in message.mentions:
                content = content.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
        content = content.strip()
        
        if not content:
            await message.channel.send('💭 Bir şey sormak ister misiniz?')
            return
        
        # Bot sahibi kontrolü
        is_owner = (message.author.id == OWNER_ID)
        
        # Eğlenceli mod (rastgele cevap)
        if random.random() < 0.2:  # %20 şans
            await message.channel.send(random.choice(funny_responses))
            return
        
        # Küfürlü mod (sadece bot sahibi)
        if is_owner and random.random() < 0.3:  # %30 şans
            await message.channel.send(random.choice(curse_responses))
            return
        
        # Normal AI yanıtı
        async with message.channel.typing():
            try:
                # Kullanıcının son mesajlarını al
                history = user_history.get(user_id, [])[-5:]  # Son 5 mesaj
                context = "\n".join(history) if history else ""
                
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "model": "openai/gpt-oss-120b",
                        "messages": [
                            {"role": "system", "content": f"Sen {SERVER_NAME} sunucusunda yardımcı bir asistan olarak cevap ver. Kullanıcının son mesajları: {context}"},
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
                            error_text = await response.text()
                            await message.channel.send(f'❌ API hatası: {response.status}')
                            
            except aiohttp.ClientError as e:
                await message.channel.send(f'❌ Bağlantı hatası: {str(e)}')
            except Exception as e:
                await message.channel.send(f'❌ Hata: {str(e)}')
    
    await bot.process_commands(message)

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

@bot.command(name='fun')
async def fun_mode(ctx):
    """Eğlenceli modu açar/kapatır"""
    await ctx.send("🎉 Eğlenceli mod aktif! Rastgele komik cevaplar verilecek!")

@bot.command(name='curse')
async def curse_mode(ctx):
    """Küfürlü modu açar (sadece bot sahibi)"""
    if ctx.author.id == OWNER_ID:
        await ctx.send("😈 Küfürlü mod aktif! (Sadece senin için)")
    else:
        await ctx.send("❌ Bu komutu sadece bot sahibi kullanabilir!")

@bot.command(name='server')
async def server_info(ctx):
    """Sunucu bilgisini gösterir"""
    if ctx.guild:
        await ctx.send(f"🏠 **Sunucu:** {ctx.guild.name}\n👥 **Üye Sayısı:** {ctx.guild.member_count}\n👑 **Sahibim:** <@{OWNER_ID}>")
    else:
        await ctx.send("Bu komut sadece sunucularda kullanılabilir!")

@bot.command(name='ping')
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f'🏓 Pong! Gecikme: {latency}ms')

@bot.command(name='help_ai')
async def help_command(ctx):
    help_text = f"""
🤖 **AI Sohbet Botu - {SERVER_NAME}**

**👑 Bot Sahibi:** <@{OWNER_ID}>

**📝 Özellikler:**
• 📜 **Mesaj Geçmişi:** Son 50 mesajınızı hatırlar
• 🎉 **Eğlenceli Mod:** Rastgele komik cevaplar (%20 şans)
• 😈 **Küfürlü Mod:** Bot sahibine özel komik küfürler (%30 şans)
• 💬 **Bağlam:** Son 5 mesajınızı hatırlar

**Kullanım:**
1. **Etiketleme:** Botu etiketleyip soru sorun
   Örnek: `@bot_adı Nasıl yapabilirim?`
2. **Özel Mesaj:** Bota doğrudan DM gönderin

**Komutlar:**
• `!history` - Son 10 mesajınızı gösterir
• `!clear_history` - Mesaj geçmişinizi temizler
• `!fun` - Eğlenceli modu açar
• `!curse` - Küfürlü modu açar (sadece sahip)
• `!server` - Sunucu bilgisini gösterir
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
