import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import asyncio
import json
import os
import io
import random
import re
from datetime import datetime

# ---------------------------------------------------------
# BOT AYARLARI
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

DB_FILE = "accounts_db.json"
db = {}
scanned_ids = set()
added_account_ids = set()

# ---------------------------------------------------------
# YIL ARALIKLARI
# ---------------------------------------------------------
YEAR_ID_RANGES = {
    "2010": 10000000,
    "2011": 18000000,
    "2012": 25000000,
    "2013": 35000000,
    "2014": 50000000,
    "2015": 80000000,
    "2016": 120000000,
    "2017": 200000000,
    "2018": 400000000,
    "2019": 700000000,
    "2020": 1000000000
}
YEARS = list(YEAR_ID_RANGES.keys())

METHOD_CHOICES = [
    app_commands.Choice(name="123_method", value="123_method"),
    app_commands.Choice(name="321_method", value="321_method"),
    app_commands.Choice(name="year_user", value="year_user"),
    app_commands.Choice(name="cross_user", value="cross_user"),
    app_commands.Choice(name="double_user", value="double_user"),
    app_commands.Choice(name="4_number_method", value="4_number_method"),
    app_commands.Choice(name="2_number_method", value="2_number_method"),
]

# ---------------------------------------------------------
# FİLTRELEME
# ---------------------------------------------------------
def validate_username_by_filter(username: str):
    if not username:
        return None

    if re.search(r'^[a-zA-Z]+\d*(?:123)+$', username, re.IGNORECASE) or re.search(r'^123[a-zA-Z]+\d*(?:123)*$', username, re.IGNORECASE):
        return '123_method'

    if re.search(r'^[a-zA-Z]+\d*(?:321)+$', username, re.IGNORECASE) or re.search(r'^321[a-zA-Z]+\d*(?:321)*$', username, re.IGNORECASE):
        return '321_method'

    if re.search(r'^[a-zA-Z]+\d*(199[8-9]|20[0-2][0-6])\d*$', username, re.IGNORECASE) or re.search(r'^(199[8-9]|20[0-2][0-6])[a-zA-Z]+\d*$', username, re.IGNORECASE):
        return 'year_user'

    if re.search(r'^(?:\d+[a-zA-Z]+\d+|\d+[a-zA-Z]+\d+[a-zA-Z]+\d*|[a-zA-Z]+\d+[a-zA-Z]+\d*)$', username, re.IGNORECASE):
        return 'cross_user'

    if re.search(r'^[a-zA-Z]+(\d{2})\1+$', username, re.IGNORECASE) or re.search(r'^[a-zA-Z]+\d*(\d)\1{3,}$', username, re.IGNORECASE) or re.search(r'^[a-zA-Z]+\d{2,4}$', username, re.IGNORECASE):
        if re.search(r'\d{4}$', username) and not re.search(r'(\d{2})\1$', username):
            pass
        else:
            return 'double_user'

    if re.search(r'^[a-zA-Z]+\d{4}$', username):
        return '4_number_method'

    if re.search(r'^[a-zA-Z]+\d{2}$', username):
        return '2_number_method'

    return None

# ---------------------------------------------------------
# VERİTABANI
# ---------------------------------------------------------
def load_db():
    global db, added_account_ids
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                db = json.load(f)
                for key, acc_list in db.items():
                    for acc in acc_list:
                        added_account_ids.add(acc['id'])
            print("[SİSTEM] Veritabanı yüklendi.")
        except Exception as e:
            print(f"[HATA] Veritabanı yüklenirken hata: {e}")
            db = {}

def save_db():
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[HATA] Veritabanı kaydedilirken hata: {e}")

# ---------------------------------------------------------
# HESAP ALMA FONKSİYONU
# ---------------------------------------------------------
def get_accounts_from_db(prefix: str, year: str, method: str, limit: int = 1):
    key = f"{prefix}_{year}_{method}"
    if key in db and len(db[key]) > 0:
        count = min(limit, len(db[key]))
        selected = db[key][:count]
        db[key] = db[key][count:]
        save_db()
        return selected
    return []

# ---------------------------------------------------------
# ARKA PLAN TARAYICI
# ---------------------------------------------------------
async def run_generator_loop(session: aiohttp.ClientSession):
    print("[TURBO] Tarayıcı Başlatıldı!")
    pending_saves = 0

    while True:
        try:
            target_year = random.choice(YEARS)
            random_offset = random.randint(0, 2000000)
            test_id = YEAR_ID_RANGES[target_year] + random_offset

            if test_id in scanned_ids:
                await asyncio.sleep(0.01)
                continue
            scanned_ids.add(test_id)

            async with session.get(f"https://users.roblox.com/v1/users/{test_id}") as resp:
                if resp.status == 429:
                    await asyncio.sleep(15)
                    continue
                if resp.status != 200:
                    continue
                user_data = await resp.json()

            if not user_data or "name" not in user_data:
                continue

            account_id_str = str(user_data["id"])
            if account_id_str in added_account_ids:
                continue

            username = user_data["name"]
            matched_filter = validate_username_by_filter(username)
            if not matched_filter:
                continue

            item_count = 0
            is_offsale_account = False
            async with session.get(f"https://inventory.roblox.com/v1/users/{test_id}/assets/collectibles?limit=10") as inv_resp:
                if inv_resp.status == 200:
                    inv_data = await inv_resp.json()
                    if inv_data and "data" in inv_data:
                        item_count = len(inv_data["data"])
                        if item_count >= 1:
                            is_offsale_account = True

            added_account_ids.add(account_id_str)

            avatar_url = "https://tr.rbxcdn.com/30day-avatar-headshot/150/150/Avatar/Png"
            async with session.get(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={test_id}&size=150x150&format=Png&isCircular=false") as av_resp:
                if av_resp.status == 200:
                    av_data = await av_resp.json()
                    if av_data.get("data") and len(av_data["data"]) > 0:
                        avatar_url = av_data["data"][0].get("imageUrl", avatar_url)

            account_created = user_data.get("created", "2000-01-01T00:00:00.000Z")
            account_year = account_created.split("-")[0]

            account_data = {
                "id": account_id_str,
                "name": username,
                "createdDate": account_created.split("T")[0],
                "isBanned": user_data.get("isBanned", False),
                "itemCount": item_count,
                "avatarUrl": avatar_url
            }

            added = False
            gen_key = f"gen_{account_year}_{matched_filter}"
            bulk_key = f"bulk_{account_year}_{matched_filter}"

            if gen_key not in db: db[gen_key] = []
            if bulk_key not in db: db[bulk_key] = []

            if not any(acc['id'] == account_data['id'] for acc in db[gen_key]):
                db[gen_key].append(account_data)
                added = True

            if not any(acc['id'] == account_data['id'] for acc in db[bulk_key]):
                db[bulk_key].append(account_data)
                added = True

            if is_offsale_account:
                offsale_key = f"offsale_{account_year}_{matched_filter}"
                if offsale_key not in db: db[offsale_key] = []
                if not any(acc['id'] == account_data['id'] for acc in db[offsale_key]):
                    db[offsale_key].append(account_data)
                    added = True

            if added:
                pending_saves += 1
                if pending_saves >= 5:
                    save_db()
                    pending_saves = 0

            print(f"[TURBO BAŞARILI] {username} | {account_year} | {matched_filter} | Eşya: {item_count}")
            await asyncio.sleep(0.06)

        except Exception as err:
            print(f"[HATA]: {err}")
            await asyncio.sleep(2)

# ---------------------------------------------------------
# DISCORD OLAY
# ---------------------------------------------------------
@client.event
async def on_ready():
    load_db()
    client.session = aiohttp.ClientSession()
    client.loop.create_task(run_generator_loop(client.session))
    await tree.sync()
    print(f"[DISCORD] {client.user} olarak giriş yapıldı!")

# ---------------------------------------------------------
# DM MESAJ KONTROL (TXT GÖNDERME)
# ---------------------------------------------------------
@client.event
async def on_message(message):
    if message.author.bot:
        return

    if not isinstance(message.channel, discord.DMChannel):
        await message.reply("⚠️ Bu bot sadece **DM** üzerinden çalışır!")
        return

    content = message.content.lower()

    if content.startswith("!hesap"):
        parts = content.split()
        if len(parts) < 3:
            await message.channel.send("❌ Kullanım: `!hesap <yıl> <method> <adet>`\nÖrnek: `!hesap 2016 123_method 5`")
            return

        yil = parts[1]
        method = parts[2]
        adet = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 5

        if adet > 50:
            adet = 50

        accounts = get_accounts_from_db("gen", yil, method, adet)

        if not accounts:
            await message.channel.send(f"❌ **{yil}** yılı ve **{method}** filtresi için stokta hesap yok!")
            return

        # TXT oluştur
        content_txt = f"📦 {yil} - {method} Havuzundan {len(accounts)} Hesap\n"
        content_txt += "=" * 60 + "\n\n"
        
        for i, acc in enumerate(accounts, 1):
            content_txt += f"{i}. Kullanıcı: {acc['name']}\n"
            content_txt += f"   ID: {acc['id']}\n"
            content_txt += f"   Kuruluş: {acc['createdDate']}\n"
            content_txt += f"   Eşya: {acc['itemCount']}\n\n"
        
        content_txt += "=" * 60 + "\n"
        content_txt += f"📅 Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        content_txt += "🤖 Bot tarafından oluşturuldu."

        txt_file = io.StringIO(content_txt)
        file = discord.File(txt_file, filename=f"{yil}_{method}_{len(accounts)}hesap.txt")
        
        await message.channel.send(f"✅ **{len(accounts)}** hesap hazır!", file=file)

    elif content.startswith("!offsale"):
        parts = content.split()
        if len(parts) < 3:
            await message.channel.send("❌ Kullanım: `!offsale <yıl> <method>`\nÖrnek: `!offsale 2016 123_method`")
            return

        yil = parts[1]
        method = parts[2]

        accounts = get_accounts_from_db("offsale", yil, method, 5)

        if not accounts:
            await message.channel.send(f"❌ **{yil}** yılı ve **{method}** filtresi için Off-Sale hesap yok!")
            return

        content_txt = f"🔥 Off-Sale {yil} - {method} Havuzundan {len(accounts)} Hesap\n"
        content_txt += "=" * 60 + "\n\n"
        
        for i, acc in enumerate(accounts, 1):
            content_txt += f"{i}. Kullanıcı: {acc['name']}\n"
            content_txt += f"   ID: {acc['id']}\n"
            content_txt += f"   Kuruluş: {acc['createdDate']}\n"
            content_txt += f"   Eşya: {acc['itemCount']} (Off-Sale)\n\n"

        txt_file = io.StringIO(content_txt)
        file = discord.File(txt_file, filename=f"offsale_{yil}_{method}.txt")
        
        await message.channel.send(f"✅ **{len(accounts)}** Off-Sale hesap!", file=file)

    elif content.startswith("!toplam"):
        total = 0
        for key, acc_list in db.items():
            total += len(acc_list)
        
        embed = discord.Embed(
            title="📊 İstatistikler",
            color=discord.Color.green()
        )
        embed.add_field(name="Toplam Hesap", value=f"**{total}**", inline=True)
        embed.add_field(name="Filtre Sayısı", value=f"**{len(db)}**", inline=True)
        embed.add_field(name="Taranan ID", value=f"**{len(scanned_ids)}**", inline=True)
        
        await message.channel.send(embed=embed)

    elif content.startswith("!yardim"):
        embed = discord.Embed(
            title="📖 Yardım Menüsü",
            description="Bot **DM** üzerinden çalışır!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="!hesap <yıl> <method> <adet>",
            value="Örnek: `!hesap 2016 123_method 5`\nMetodlar: `123_method`, `321_method`, `year_user`, `cross_user`, `double_user`, `4_number_method`, `2_number_method`",
            inline=False
        )
        embed.add_field(
            name="!offsale <yıl> <method>",
            value="Örnek: `!offsale 2016 123_method`",
            inline=False
        )
        embed.add_field(
            name="!toplam",
            value="Toplam hesap sayısını gösterir.",
            inline=False
        )
        await message.channel.send(embed=embed)

    elif content.startswith("!"):
        await message.channel.send("❌ Bilinmeyen komut! `!yardim` yazarak yardım alabilirsin.")

# ---------------------------------------------------------
# SLASH KOMUTLAR (Sunucuda da çalışsın diye)
# ---------------------------------------------------------
@tree.command(name="gen", description="Tek hesap getirir (DM'ye gönderir)")
@app_commands.choices(method=METHOD_CHOICES)
async def gen_slash(interaction: discord.Interaction, yil: str, method: app_commands.Choice[str]):
    await interaction.response.send_message("✅ Hesap DM'ne gönderiliyor...", ephemeral=True)
    
    accounts = get_accounts_from_db("gen", yil, method.value, 1)
    
    if not accounts:
        await interaction.followup.send(f"❌ **{yil}** yılı ve **{method.value}** filtresi için stokta hesap yok!", ephemeral=True)
        return

    acc = accounts[0]
    
    # DM'ye gönder
    try:
        embed = discord.Embed(title="🎮 Roblox Hesap", color=discord.Color.green())
        embed.add_field(name="Kullanıcı Adı", value=f"`{acc['name']}`", inline=True)
        embed.add_field(name="ID", value=f"`{acc['id']}`", inline=True)
        embed.add_field(name="Kuruluş", value=acc['createdDate'], inline=True)
        embed.add_field(name="Eşya Sayısı", value=str(acc['itemCount']), inline=True)
        embed.set_thumbnail(url=acc['avatarUrl'])
        embed.set_footer(text=f"Filtre: {method.value} | Yıl: {yil}")
        
        await interaction.user.send(embed=embed)
        await interaction.followup.send("✅ Hesap DM'ne gönderildi!", ephemeral=True)
    except:
        await interaction.followup.send("❌ DM'ni açık tut! Hesap gönderilemedi.", ephemeral=True)

@tree.command(name="bulkgen", description="Toplu hesap getirir (DM'ye .txt gönderir)")
@app_commands.choices(method=METHOD_CHOICES)
async def bulkgen_slash(interaction: discord.Interaction, yil: str, method: app_commands.Choice[str], adet: int = 5):
    if adet > 50:
        adet = 50
        await interaction.response.send_message("⚠️ En fazla 50 hesap gönderebilirim, 50'ye düşürüyorum!", ephemeral=True)
    else:
        await interaction.response.send_message("✅ Hesaplar DM'ne .txt olarak gönderiliyor...", ephemeral=True)

    accounts = get_accounts_from_db("bulk", yil, method.value, adet)

    if not accounts:
        await interaction.followup.send(f"❌ **{yil}** yılı ve **{method.value}** filtresi için stokta hesap yok!", ephemeral=True)
        return

    # TXT oluştur
    content_txt = f"📦 {yil} - {method.value} Havuzundan {len(accounts)} Hesap\n"
    content_txt += "=" * 60 + "\n\n"
    
    for i, acc in enumerate(accounts, 1):
        content_txt += f"{i}. Kullanıcı: {acc['name']}\n"
        content_txt += f"   ID: {acc['id']}\n"
        content_txt += f"   Kuruluş: {acc['createdDate']}\n"
        content_txt += f"   Eşya: {acc['itemCount']}\n\n"
    
    content_txt += "=" * 60 + "\n"
    content_txt += f"📅 Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
    content_txt += "🤖 Bot tarafından oluşturuldu."

    txt_file = io.StringIO(content_txt)
    file = discord.File(txt_file, filename=f"{yil}_{method.value}_{len(accounts)}hesap.txt")

    try:
        await interaction.user.send(f"✅ **{len(accounts)}** hesap hazır!", file=file)
        await interaction.followup.send("✅ Hesaplar DM'ne .txt olarak gönderildi!", ephemeral=True)
    except:
        await interaction.followup.send("❌ DM'ni açık tut! Dosya gönderilemedi.", ephemeral=True)

# ---------------------------------------------------------
# BOT BAŞLAT
# ---------------------------------------------------------
TOKEN = os.environ.get("TOKEN")

if not TOKEN:
    raise ValueError("[HATA] TOKEN environment variable bulunamadı!")

client.run(TOKEN)
