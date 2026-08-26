import discord
import aiohttp
import asyncio
import json
import os
from discord.ext import commands

# Environment variables'dan oku
TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions'

# Token'lar kontrol
if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN environment variable'ı ayarlanmamış!")
if not GROQ_API_KEY:
    raise ValueError("❌ GROQ_API_KEY environment variable'ı ayarlanmamış!")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ {bot.user} olarak giriş yapıldı!')
    print(f'📊 Bot ID: {bot.user.id}')
    print(f'🔑 Groq API: {"✓" if GROQ_API_KEY else "✗"}')

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    if bot.user in message.mentions or isinstance(message.channel, discord.DMChannel):
        content = message.content
        if bot.user in message.mentions:
            for mention in message.mentions:
                content = content.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
        content = content.strip()
        
        if not content:
            await message.channel.send('💭 Bir şey sormak ister misiniz?')
            return
        
        async with message.channel.typing():
            try:
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "model": "openai/gpt-oss-120b",
                        "messages": [
                            {"role": "system", "content": "Sen yardımcı bir asistan olarak cevap ver."},
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

@bot.command(name='ping')
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f'🏓 Pong! Gecikme: {latency}ms')

@bot.command(name='groq')
async def groq_command(ctx, *, question):
    async with ctx.typing():
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": "openai/gpt-oss-120b",
                    "messages": [
                        {"role": "system", "content": "Sen yardımcı bir asistan olarak cevap ver."},
                        {"role": "user", "content": question}
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
                        await ctx.send(reply[:2000])
                    else:
                        await ctx.send(f'❌ API hatası: {response.status}')
        except Exception as e:
            await ctx.send(f'❌ Hata: {str(e)}')

@bot.command(name='help_ai')
async def help_command(ctx):
    help_text = """
🤖 **AI Sohbet Botu Kullanımı**

**Kullanım Şekilleri:**
1. **Etiketleme:** Botu etiketleyip soru sorun
   Örnek: `@bot_adı Nasıl yapabilirim?`

2. **Özel Mesaj:** Bota doğrudan DM gönderin

3. **Komutlar:**
   • `!groq sorunuz` - Groq API'ye direkt soru sorar
   • `!ping` - Bot gecikmesini gösterir
   • `!help_ai` - Bu yardım mesajını gösterir

**Özellikler:**
• Hızlı yanıt süresi
• 2000 karakter sınırı (uzun mesajlar otomatik bölünür)
• Yazıyor durumu gösterimi
• Hata yönetimi

**Not:** Bot etiketlendiğinde veya DM'de otomatik yanıt verir.
    """
    await ctx.send(help_text)

if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Token hatası! Lütfen token'ınızı kontrol edin.")
    except Exception as e:
        print(f"❌ Bot başlatılamadı: {e}")
