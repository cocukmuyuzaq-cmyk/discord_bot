import discord
from discord import app_commands
import aiohttp
import asyncio
import json
import os
import io
import random
import re
from datetime import datetime

# ---------------------------------------------------------
# BOT SETTINGS
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
# TÜM METHODLAR
# ---------------------------------------------------------
ALL_METHODS = [
    "123_method",
    "321_method", 
    "year_user",
    "cross_user",
    "double_user",
    "4_number_method",
    "2_number_method"
]

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
# FİLTRE - SADECE GERÇEK 123_METHOD
# ---------------------------------------------------------
def validate_username_by_filter(username: str):
    if not username:
        return None

    username_lower = username.lower()

    # 1. 123_method: SADECE 123 ile BİTENLER
    if re.search(r'123$', username_lower):
        return '123_method'

    # 2. 321_method: SADECE 321 ile BİTENLER
    if re.search(r'321$', username_lower):
        return '321_method'

    # 3. year_user: İçinde yıl geçen (1998-2026)
    if re.search(r'(199[8-9]|20[0-2][0-6])', username):
        return 'year_user'

    # 4. cross_user: Harf-sayı-harf geçişli
    if re.search(r'^[a-zA-Z]+\d+[a-zA-Z]+\d*$', username) or \
       re.search(r'^\d+[a-zA-Z]+\d+$', username):
        return 'cross_user'

    # 5. double_user: Tekrar eden sayılar (1414, 1010, 9999, 666)
    if re.search(r'(\d{2})\1', username) or \
       re.search(r'(\d)\1{2,}', username):
        return 'double_user'

    # 6. 4_number_method: Harf + 4 sayı ile biten
    if re.search(r'^[a-zA-Z]+\d{4}$', username):
        return '4_number_method'

    # 7. 2_number_method: Harf + 2 sayı ile biten
    if re.search(r'^[a-zA-Z]+\d{2}$', username):
        return '2_number_method'

    return None

# ---------------------------------------------------------
# DATABASE
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
            print("[SYSTEM] Database loaded.")
        except Exception as e:
            print(f"[ERROR] Database load error: {e}")
            db = {}

def save_db():
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] Database save error: {e}")

def save_account_to_all_methods(account_data, account_year, matched_filter, is_offsale_account):
    global db
    added = False
    
    for method in ALL_METHODS:
        gen_key = f"gen_{account_year}_{method}"
        bulk_key = f"bulk_{account_year}_{method}"
        
        if gen_key not in db: db[gen_key] = []
        if bulk_key not in db: db[bulk_key] = []
        
        if not any(acc['id'] == account_data['id'] for acc in db[gen_key]):
            db[gen_key].append(account_data)
            added = True
        
        if not any(acc['id'] == account_data['id'] for acc in db[bulk_key]):
            db[bulk_key].append(account_data)
            added = True
        
        if is_offsale_account:
            offsale_key = f"offsale_{account_year}_{method}"
            if offsale_key not in db: db[offsale_key] = []
            if not any(acc['id'] == account_data['id'] for acc in db[offsale_key]):
                db[offsale_key].append(account_data)
                added = True
    
    return added

def get_all_accounts_from_db(year: str, method: str):
    gen_key = f"gen_{year}_{method}"
    if gen_key in db and len(db[gen_key]) > 0:
        return db[gen_key].copy()
    return []

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
# BACKGROUND GENERATOR - RANDOM ID İLE TARA
# ---------------------------------------------------------
async def run_generator_loop(session: aiohttp.ClientSession):
    print("[TURBO] Generator Started! Random ID scanning...")
    pending_saves = 0

    while True:
        try:
            # ✅ RANDOM ID ÜRET (1 ile 999999999 arası)
            test_id = random.randint(1, 999999999)

            if test_id in scanned_ids:
                await asyncio.sleep(0.01)
                continue
            scanned_ids.add(test_id)

            # ✅ YENİ API
            async with session.get(f"https://apis.roblox.com/cloud/v2/users/{test_id}") as resp:
                if resp.status == 429:
                    await asyncio.sleep(15)
                    continue
                if resp.status == 404:
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

            # Envanter kontrolü
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

            # Avatar
            avatar_url = "https://tr.rbxcdn.com/30day-avatar-headshot/150/150/Avatar/Png"
            async with session.get(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={test_id}&size=150x150&format=Png&isCircular=false") as av_resp:
                if av_resp.status == 200:
                    av_data = await av_resp.json()
                    if av_data.get("data") and len(av_data["data"]) > 0:
                        avatar_url = av_data["data"][0].get("imageUrl", avatar_url)

            account_created = user_data.get("created", datetime.now().isoformat())
            account_year = account_created.split("-")[0] if "-" in account_created else str(datetime.now().year)

            account_data = {
                "id": account_id_str,
                "name": username,
                "createdDate": account_created.split("T")[0] if "T" in account_created else account_created,
                "isBanned": user_data.get("isBanned", False),
                "itemCount": item_count,
                "avatarUrl": avatar_url
            }

            added = save_account_to_all_methods(account_data, account_year, matched_filter, is_offsale_account)

            if added:
                pending_saves += 1
                if pending_saves >= 5:
                    save_db()
                    pending_saves = 0

            print(f"[TURBO SUCCESS] {username} | {account_year} | {matched_filter} | Items: {item_count}")
            await asyncio.sleep(0.06)

        except Exception as err:
            print(f"[ERROR]: {err}")
            await asyncio.sleep(2)

# ---------------------------------------------------------
# DISCORD EVENTS
# ---------------------------------------------------------
@client.event
async def on_ready():
    load_db()
    client.session = aiohttp.ClientSession()
    client.loop.create_task(run_generator_loop(client.session))
    await tree.sync()
    print(f"[DISCORD] Logged in as {client.user}!")

# ---------------------------------------------------------
# DM MESSAGE HANDLER
# ---------------------------------------------------------
@client.event
async def on_message(message):
    if message.author.bot:
        return

    if not isinstance(message.channel, discord.DMChannel):
        await message.reply("⚠️ This bot only works in **DM**!")
        return

    content = message.content.lower()

    if content.startswith("!help"):
        embed = discord.Embed(
            title="📖 Help Menu",
            description="Bot works in **DM** only!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="!list <year> <method>",
            value="Example: `!list 2016 123_method`\nShows ALL account usernames",
            inline=False
        )
        embed.add_field(
            name="!get <year> <method> <amount>",
            value="Example: `!get 2016 123_method 5`\nGets accounts as .txt",
            inline=False
        )
        embed.add_field(
            name="!stats",
            value="Shows total account count.",
            inline=False
        )
        await message.channel.send(embed=embed)

    elif content.startswith("!list"):
        parts = content.split()
        if len(parts) < 3:
            await message.channel.send("❌ Usage: `!list <year> <method>`\nExample: `!list 2016 123_method`")
            return

        year = parts[1]
        method = parts[2]

        accounts = get_all_accounts_from_db(year, method)

        if not accounts:
            await message.channel.send(f"❌ No accounts found for **{year}** and **{method}**!")
            return

        username_list = []
        for acc in accounts:
            username_list.append(acc['name'])
        
        content_txt = f"📋 {year} - {method} - {len(accounts)} Accounts\n"
        content_txt += "=" * 50 + "\n\n"
        content_txt += "\n".join(username_list)
        content_txt += "\n\n" + "=" * 50 + "\n"
        content_txt += f"📅 Date: {datetime.now().strftime('%d.%m.%Y %H:%M')}"

        if len(content_txt) > 1900:
            txt_file = io.StringIO(content_txt)
            file = discord.File(txt_file, filename=f"{year}_{method}_usernames.txt")
            await message.channel.send(f"✅ **{len(accounts)}** usernames found!", file=file)
        else:
            await message.channel.send(f"✅ **{len(accounts)}** accounts found:\n```\n{content_txt}\n```")

    elif content.startswith("!get"):
        parts = content.split()
        if len(parts) < 3:
            await message.channel.send("❌ Usage: `!get <year> <method> <amount>`\nExample: `!get 2016 123_method 5`")
            return

        year = parts[1]
        method = parts[2]
        amount = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 5

        if amount > 50:
            amount = 50

        accounts = get_accounts_from_db("gen", year, method, amount)

        if not accounts:
            await message.channel.send(f"❌ No accounts found for **{year}** and **{method}**!")
            return

        content_txt = f"📦 {year} - {method} - {len(accounts)} Accounts\n"
        content_txt += "=" * 60 + "\n\n"
        
        for i, acc in enumerate(accounts, 1):
            content_txt += f"{i}. Username: {acc['name']}\n"
            content_txt += f"   ID: {acc['id']}\n"
            content_txt += f"   Created: {acc['createdDate']}\n"
            content_txt += f"   Items: {acc['itemCount']}\n\n"
        
        content_txt += "=" * 60 + "\n"
        content_txt += f"📅 Date: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        content_txt += "🤖 Generated by bot."

        txt_file = io.StringIO(content_txt)
        file = discord.File(txt_file, filename=f"{year}_{method}_{len(accounts)}accounts.txt")
        
        await message.channel.send(f"✅ **{len(accounts)}** accounts ready!", file=file)

    elif content.startswith("!stats"):
        total = 0
        for key, acc_list in db.items():
            total += len(acc_list)
        
        embed = discord.Embed(
            title="📊 Statistics",
            color=discord.Color.green()
        )
        embed.add_field(name="Total Accounts", value=f"**{total}**", inline=True)
        embed.add_field(name="Filters", value=f"**{len(db)}**", inline=True)
        embed.add_field(name="Scanned IDs", value=f"**{len(scanned_ids)}**", inline=True)
        
        await message.channel.send(embed=embed)

    elif content.startswith("!"):
        await message.channel.send("❌ Unknown command! Type `!help` for help.")

# ---------------------------------------------------------
# SLASH COMMANDS
# ---------------------------------------------------------
@tree.command(name="list", description="List ALL account usernames for a filter")
@app_commands.choices(method=METHOD_CHOICES)
async def list_slash(interaction: discord.Interaction, year: str, method: app_commands.Choice[str]):
    await interaction.response.send_message("✅ Fetching accounts...", ephemeral=True)
    
    accounts = get_all_accounts_from_db(year, method.value)

    if not accounts:
        await interaction.followup.send(f"❌ No accounts for **{year}** and **{method.value}**!", ephemeral=True)
        return

    username_list = []
    for acc in accounts:
        username_list.append(acc['name'])
    
    content_txt = f"📋 {year} - {method.value} - {len(accounts)} Accounts\n"
    content_txt += "=" * 50 + "\n\n"
    content_txt += "\n".join(username_list)
    content_txt += "\n\n" + "=" * 50 + "\n"
    content_txt += f"📅 Date: {datetime.now().strftime('%d.%m.%Y %H:%M')}"

    try:
        if len(content_txt) > 1900:
            txt_file = io.StringIO(content_txt)
            file = discord.File(txt_file, filename=f"{year}_{method.value}_usernames.txt")
            await interaction.user.send(f"✅ **{len(accounts)}** usernames!", file=file)
        else:
            await interaction.user.send(f"✅ **{len(accounts)}** accounts:\n```\n{content_txt}\n```")
        await interaction.followup.send("✅ Sent to your DM!", ephemeral=True)
    except:
        await interaction.followup.send("❌ Open your DMs!", ephemeral=True)

@tree.command(name="get", description="Get accounts as .txt via DM")
@app_commands.choices(method=METHOD_CHOICES)
async def get_slash(interaction: discord.Interaction, year: str, method: app_commands.Choice[str], amount: int = 5):
    if amount > 50:
        amount = 50
        await interaction.response.send_message("⚠️ Max 50, reducing!", ephemeral=True)
    else:
        await interaction.response.send_message("✅ Sending...", ephemeral=True)

    accounts = get_accounts_from_db("gen", year, method.value, amount)

    if not accounts:
        await interaction.followup.send(f"❌ No accounts for **{year}** and **{method.value}**!", ephemeral=True)
        return

    content_txt = f"📦 {year} - {method.value} - {len(accounts)} Accounts\n"
    content_txt += "=" * 60 + "\n\n"
    
    for i, acc in enumerate(accounts, 1):
        content_txt += f"{i}. Username: {acc['name']}\n"
        content_txt += f"   ID: {acc['id']}\n"
        content_txt += f"   Created: {acc['createdDate']}\n"
        content_txt += f"   Items: {acc['itemCount']}\n\n"
    
    content_txt += "=" * 60 + "\n"
    content_txt += f"📅 Date: {datetime.now().strftime('%d.%m.%Y %H:%M')}"

    txt_file = io.StringIO(content_txt)
    file = discord.File(txt_file, filename=f"{year}_{method.value}_{len(accounts)}accounts.txt")

    try:
        await interaction.user.send(f"✅ **{len(accounts)}** accounts!", file=file)
        await interaction.followup.send("✅ Sent to your DM!", ephemeral=True)
    except:
        await interaction.followup.send("❌ Open your DMs!", ephemeral=True)

@tree.command(name="stats", description="Show bot statistics")
async def stats_slash(interaction: discord.Interaction):
    total = 0
    for key, acc_list in db.items():
        total += len(acc_list)
    
    embed = discord.Embed(
        title="📊 Statistics",
        color=discord.Color.green()
    )
    embed.add_field(name="Total Accounts", value=f"**{total}**", inline=True)
    embed.add_field(name="Filters", value=f"**{len(db)}**", inline=True)
    embed.add_field(name="Scanned IDs", value=f"**{len(scanned_ids)}**", inline=True)
    
    await interaction.response.send_message(embed=embed)

# ---------------------------------------------------------
# BOT START
# ---------------------------------------------------------
TOKEN = os.environ.get("TOKEN")

if not TOKEN:
    raise ValueError("[ERROR] TOKEN environment variable not found!")

client.run(TOKEN)
