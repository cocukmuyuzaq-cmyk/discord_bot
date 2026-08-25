import discord
from discord.ext import commands
import os
import json
import io

# ---------------------------------------------------------
# BOT AYARLARI
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

DB_FILE = "accounts_db.json"

# ---------------------------------------------------------
# VERİTABANINI YÜKLE
# ---------------------------------------------------------
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

db = load_db()

# ---------------------------------------------------------
# KOMUT: !hesap <yıl> <method> -> DM'den .txt gönderir
# ---------------------------------------------------------
@bot.command()
async def hesap(ctx, yil: str, method: str):
    """Örnek: !hesap 2016 123_method"""
    
    # Sadece DM'de çalışsın (opsiyonel)
    if ctx.guild:
        await ctx.send("⚠️ Bu komut sadece DM'den kullanılabilir!", delete_after=5)
        return

    # Veritabanında ara
    gen_key = f"gen_{yil}_{method}"
    bulk_key = f"bulk_{yil}_{method}"
    
    accounts = []
    
    if gen_key in db and db[gen_key]:
        accounts = db[gen_key][:20]  # En fazla 20 hesap
    elif bulk_key in db and db[bulk_key]:
        accounts = db[bulk_key][:20]
    
    if not accounts:
        await ctx.send(f"❌ **{yil}** yılı ve **{method}** filtresi için hesap bulunamadı!")
        return

    # .txt dosyası oluştur
    content = f"📦 {yil} - {method} Havuzundan {len(accounts)} Hesap\n"
    content += "=" * 50 + "\n\n"
    
    for i, acc in enumerate(accounts, 1):
        content += f"{i}. Kullanıcı: {acc['name']}\n"
        content += f"   ID: {acc['id']}\n"
        content += f"   Kuruluş: {acc['createdDate']}\n"
        content += f"   Eşya: {acc['itemCount']}\n\n"
    
    content += "=" * 50 + "\n"
    content += "Bot tarafından oluşturuldu. 🚀"

    # .txt dosyasını DM'den gönder
    txt_file = io.StringIO(content)
    file = discord.File(txt_file, filename=f"{yil}_{method}.txt")
    
    await ctx.send(f"✅ **{yil} - {method}** hesap listesi hazır!", file=file)

# ---------------------------------------------------------
# KOMUT: !yardım
# ---------------------------------------------------------
@bot.command()
async def yardim(ctx):
    """Yardım menüsü"""
    embed = discord.Embed(
        title="📖 Yardım Menüsü",
        description="Bot ile DM üzerinden hesap alabilirsin!",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="!hesap <yıl> <method>",
        value="Örnek: `!hesap 2016 123_method`\n.size/size\ method isimleri: `123_method`, `321_method`, `year_user`, `cross_user`, `double_user`, `4_number_method`, `2_number_method`",
        inline=False
    )
    embed.add_field(
        name="📌 Not",
        value="Bu komut sadece **DM'den** çalışır. Bot seninle DM'de konuşur.",
        inline=False
    )
    await ctx.send(embed=embed)

# ---------------------------------------------------------
# BOT BAŞLAT
# ---------------------------------------------------------
TOKEN = os.environ.get("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN environment variable bulunamadı!")

bot.run(TOKEN)
