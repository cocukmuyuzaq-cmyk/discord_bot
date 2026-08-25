import asyncio
import random
import re
import json
import os
from datetime import datetime
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

# ---------------------------------------------------------
# GLOBAL DEĞİŞKENLER VE VERİTABANI DOSYASI
# ---------------------------------------------------------
DB_FILE = "accounts_db.json"
db = {}

scanned_ids = set()
added_account_ids = set()

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

# ---------------------------------------------------------
# FİLTRELEME FONKSİYONU (validateUsernameByFilter)
# ---------------------------------------------------------
def validate_username_by_filter(username: str):
    if not username:
        return None

    # 1. 123_method
    if re.search(r'^[a-zA-Z]+\d*(?:123)+$', username, re.IGNORECASE) or re.search(r'^123[a-zA-Z]+\d*(?:123)*$', username, re.IGNORECASE):
        return '123_method'

    # 2. 321_method
    if re.search(r'^[a-zA-Z]+\d*(?:321)+$', username, re.IGNORECASE) or re.search(r'^321[a-zA-Z]+\d*(?:321)*$', username, re.IGNORECASE):
        return '321_method'

    # 3. year_user
    if re.search(r'^[a-zA-Z]+\d*(199[8-9]|20[0-2][0-6])\d*$', username, re.IGNORECASE) or re.search(r'^(199[8-9]|20[0-2][0-6])[a-zA-Z]+\d*$', username, re.IGNORECASE):
        return 'year_user'

    # 4. cross_user
    if re.search(r'^(?:\d+[a-zA-Z]+\d+|\d+[a-zA-Z]+\d+[a-zA-Z]+\d*|[a-zA-Z]+\d+[a-zA-Z]+\d*)$', username, re.IGNORECASE):
        return 'cross_user'

    # 5. double_user
    if re.search(r'^[a-zA-Z]+(\d{2})\1+$', username, re.IGNORECASE) or re.search(r'^[a-zA-Z]+\d*(\d)\1{3,}$', username, re.IGNORECASE) or re.search(r'^[a-zA-Z]+\d{2,4}$', username, re.IGNORECASE):
        if re.search(r'\d{4}$', username) and not re.search(r'(\d{2})\1$', username):
            pass
        else:
            return 'double_user'

    # 6. 4_number_method
    if re.search(r'^[a-zA-Z]+\d{4}$', username):
        return '4_number_method'

    # 7. 2_number_method
    if re.search(r'^[a-zA-Z]+\d{2}$', username):
        return '2_number_method'

    return None

# ---------------------------------------------------------
# VERİTABANI İŞLEMLERİ
# ---------------------------------------------------------
def load_db():
    global db
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                db = json.load(f)
                for key, acc_list in db.items():
                    for acc in acc_list:
                        added_account_ids.add(acc['id'])
            print("[SİSTEM] Veritabanı başarıyla yüklendi.")
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
# ARKA PLAN TARAYICI DÖNGÜSÜ (TURBO GENERATOR)
# ---------------------------------------------------------
async def run_generator_loop(session: aiohttp.ClientSession):
    print("[TURBO] Embedded Generator Başlatıldı!")
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

            print(f"[TURBO BAŞARILI] Hesap Eklendi: {username} | Yıl: {account_year} | Tip: {matched_filter} | Eşya: {item_count}")
            await asyncio.sleep(0.06)

        except Exception as err:
            print(f"[HATA]: {err}")
            await asyncio.sleep(2)

# ---------------------------------------------------------
# DISCORD BOT KURULUMU VE SLASH KOMUTLARI
# ---------------------------------------------------------
class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        load_db()
        self.session = aiohttp.ClientSession()
        self.loop.create_task(run_generator_loop(self.session))
        await self.tree.sync()

client = MyClient()

METHOD_CHOICES = [
    app_commands.Choice(name="123_method", value="123_method"),
    app_commands.Choice(name="321_method", value="321_method"),
    app_commands.Choice(name="year_user", value="year_user"),
    app_commands.Choice(name="cross_user", value="cross_user"),
    app_commands.Choice(name="double_user", value="double_user"),
    app_commands.Choice(name="4_number_method", value="4_number_method"),
    app_commands.Choice(name="2_number_method", value="2_number_method"),
]

def get_accounts_from_db(prefix: str, year: str, method: str, limit: int = 1):
    key = f"{prefix}_{year}_{method}"
    if key in db and len(db[key]) > 0:
        count = min(limit, len(db[key]))
        selected = db[key][:count]
        db[key] = db[key][count:]
        save_db()
        return selected
    return []

@client.event
async def on_ready():
    print(f"[DISCORD] {client.user} adıyla giriş yapıldı ve Slash komutları senkronize edildi!")

# 1. /gen Komutu
@client.tree.command(name="gen", description="Tek bir hesap oluşturur/getirir.")
@app_commands.choices(method=METHOD_CHOICES)
async def gen_command(interaction: discord.Interaction, yil: str, method: app_commands.Choice[str]):
    accounts = get_accounts_from_db("gen", yil, method.value, limit=1)
    
    if not accounts:
        await interaction.response.send_message(f"❌ **{yil}** yılı ve **{method.value}** filtresi için stokta hesap bulunamadı!", ephemeral=True)
        return

    acc = accounts[0]
    embed = discord.Embed(title="🎮 Roblox Hesap Oluşturuldu", color=discord.Color.green())
    embed.add_field(name="Kullanıcı Adı", value=f"`{acc['name']}`", inline=True)
    embed.add_field(name="ID", value=f"`{acc['id']}`", inline=True)
    embed.add_field(name="Kuruluş Tarihi", value=acc['createdDate'], inline=True)
    embed.add_field(name="Eşya Sayısı", value=str(acc['itemCount']), inline=True)
    embed.set_thumbnail(url=acc['avatarUrl'])
    embed.set_footer(text=f"Filtre: {method.value} | Yıl: {yil}")

    await interaction.response.send_message(embed=embed)

# 2. /bulkgen Komutu
@client.tree.command(name="bulkgen", description="Toplu hesap getirir.")
@app_commands.choices(method=METHOD_CHOICES)
async def bulkgen_command(interaction: discord.Interaction, yil: str, method: app_commands.Choice[str], adet: int = 5):
    if adet > 20:
        await interaction.response.send_message("❌ Tek seferde en fazla 20 hesap isteyebilirsiniz.", ephemeral=True)
        return

    accounts = get_accounts_from_db("bulk", yil, method.value, limit=adet)

    if not accounts:
        await interaction.response.send_message(f"❌ **{yil}** yılı ve **{method.value}** filtresi için stokta hesap bulunamadı!", ephemeral=True)
        return

    text_content = f"📦 **{yil} - {method.value}** Havuzundan Çekilen **{len(accounts)}** Adet Hesap:\n\n"
    for acc in accounts:
        text_content += f"• **İsim:** `{acc['name']}` | **ID:** `{acc['id']}` | **Tarih:** {acc['createdDate']} | **Eşya:** {acc['itemCount']}\n"

    await interaction.response.send_message(text_content)

# 3. /offsalegen Komutu
@client.tree.command(name="offsalegen", description="Envanterinde Off-Sale/Collectible eşya olan hesap getirir.")
@app_commands.choices(method=METHOD_CHOICES)
async def offsalegen_command(interaction: discord.Interaction, yil: str, method: app_commands.Choice[str]):
    accounts = get_accounts_from_db("offsale", yil, method.value, limit=1)

    if not accounts:
        await interaction.response.send_message(f"❌ **{yil}** yılı, **{method.value}** filtresi için **Off-Sale** hesap bulunamadı!", ephemeral=True)
        return

    acc = accounts[0]
    embed = discord.Embed(title="🔥 Off-Sale Roblox Hesap", color=discord.Color.gold())
    embed.add_field(name="Kullanıcı Adı", value=f"`{acc['name']}`", inline=True)
    embed.add_field(name="ID", value=f"`{acc['id']}`", inline=True)
    embed.add_field(name="Kuruluş Tarihi", value=acc['createdDate'], inline=True)
    embed.add_field(name="Collectible Eşya", value=f"**{acc['itemCount']} Adet**", inline=True)
    embed.set_thumbnail(url=acc['avatarUrl'])
    embed.set_footer(text=f"Off-Sale Havuzu | Filtre: {method.value}")

    await interaction.response.send_message(embed=embed)

# ---------------------------------------------------------
# BOTU BAŞLATMA (RENDER ENVIRONMENT VARIABLE)
# ---------------------------------------------------------
BOT_TOKEN = os.environ.get("TOKEN")

if not BOT_TOKEN:
    raise ValueError("[HATA] TOKEN çevre değişkeni (Environment Variable) bulunamadı! Lütfen Render panelinden ekleyin.")

client.run(BOT_TOKEN)
