import os
import re
import threading

from flask import Flask
from pyrogram import Client, filters
from pymongo import MongoClient

# ================= CONFIG =================

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
MONGO_URL = os.environ.get("MONGO_URL", "")
DB_NAME = os.environ.get("DB_NAME", "autocaption")

# ==========================================

bot = Client(
    "auto_caption_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

mongo = MongoClient(MONGO_URL)
db = mongo[DB_NAME]
settings = db.settings

web = Flask(__name__)


@web.route("/")
def home():
    return "Auto Caption Bot is Running!"


def run_web():
    port = int(os.environ.get("PORT", "10000"))
    web.run(host="0.0.0.0", port=port)


DEFAULT_TEMPLATE = """Series Name: {series}
Language: Hindi + English
Season: {season}
Quality: {quality}
Episode: {episode}"""


def get_template():
    data = settings.find_one({"_id": "caption_template"})

    if data:
        return data["template"]

    return DEFAULT_TEMPLATE


def extract_details(filename, old_caption):
    text = f"{filename or ''} {old_caption or ''}"

    season = "N/A"
    episode = "N/A"

    patterns = [
        r"(?i)\bS(\d{1,2})\s*E(\d{1,3})\b",
        r"(?i)\bS(\d{1,2})[\s._-]+EP?(\d{1,3})\b",
        r"(?i)\bSeason\s*(\d{1,2})\D{0,15}Episode\s*(\d{1,3})\b"
    ]

    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            season = match.group(1)
            episode = match.group(2)
            break

    quality = "N/A"

    quality_match = re.search(
        r"(?i)\b(2160p|1080p|720p|480p|360p|240p|4k)\b",
        text
    )

    if quality_match:
        quality = quality_match.group(1)

        if quality.lower() == "4k":
            quality = "4K"

    return season, episode, quality


def create_caption(message):
    media = message.document or message.video or message.audio

    filename = getattr(media, "file_name", "") or ""
    old_caption = message.caption or ""

    season, episode, quality = extract_details(
        filename,
        old_caption
    )

    series = filename.rsplit(".", 1)[0] if filename else "N/A"

    template = get_template()

    caption = template.format(
        series=series,
        season=season,
        episode=episode,
        quality=quality
    )

    return caption


# ================= START =================


@bot.on_message(filters.private & filters.command("start"))
async def start_command(client, message):

    await message.reply_text(
        "🤖 AUTO CAPTION BOT\n\n"
        "Admin Commands:\n\n"
        "/setcaption - Set Caption Format\n"
        "/caption - Show Current Caption\n"
        "/resetcaption - Reset Caption\n\n"
        "Available Auto Placeholders:\n"
        "{series}\n"
        "{season}\n"
        "{episode}\n"
        "{quality}\n\n"
        "Other text will remain unchanged."
    )


# ================ SET CAPTION ================


@bot.on_message(filters.private & filters.command("setcaption"))
async def set_caption(client, message):

    if not message.from_user or message.from_user.id != OWNER_ID:
        return await message.reply_text("⛔ Admin Only!")

    template = message.text.partition(" ")[2].strip()

    if not template:
        return await message.reply_text(
            "Example:\n\n"
            "/setcaption Series Name: {series}\n"
            "Language: Hindi Korean Tamil Telugu\n"
            "Season: {season}\n"
            "Quality: 720p\n"
            "Episode: {episode}\n\n"
            "Available placeholders:\n"
            "{series}, {season}, {episode}, {quality}\n\n"
            "Use only the placeholders you need."
        )

    settings.update_one(
        {"_id": "caption_template"},
        {"$set": {"template": template}},
        upsert=True
    )

    await message.reply_text(
        "✅ Caption Template Saved Successfully!"
    )


# ================ SHOW CAPTION ================


@bot.on_message(filters.private & filters.command("caption"))
async def show_caption(client, message):

    if not message.from_user or message.from_user.id != OWNER_ID:
        return await message.reply_text("⛔ Admin Only!")

    await message.reply_text(
        "📄 CURRENT CAPTION FORMAT\n\n"
        + get_template()
    )


# ================ RESET CAPTION ================


@bot.on_message(filters.private & filters.command("resetcaption"))
async def reset_caption(client, message):

    if not message.from_user or message.from_user.id != OWNER_ID:
        return await message.reply_text("⛔ Admin Only!")

    settings.delete_one(
        {"_id": "caption_template"}
    )

    await message.reply_text(
        "✅ Default Caption Restored!"
    )


# ================ AUTO CAPTION ================


@bot.on_message(
    filters.channel
    & (filters.document | filters.video | filters.audio)
)
async def auto_caption(client, message):

    try:
        caption = create_caption(message)

        await message.edit_caption(
            caption=caption
        )

        print("Caption Updated Successfully")

    except Exception as error:

        print("Caption Error:", error)


# ================ RUN BOT ================


if __name__ == "__main__":

    threading.Thread(
        target=run_web,
        daemon=True
    ).start()

    print("Auto Caption Bot Started!")

    bot.run()
