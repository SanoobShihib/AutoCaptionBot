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


DEFAULT_TEMPLATE = """Series: Money Mafia
Season: {season}
Episode: {episode}
Language: Hindi + English
Quality: {quality}"""


def get_template():
    data = settings.find_one({"_id": "caption_template"})

    if data:
        return data["template"]

    return DEFAULT_TEMPLATE


def extract_details(filename, old_caption):
    text = f"{filename or ''} {old_caption or ''}"

    # Season and Episode detection
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
            season = str(int(match.group(1)))
            episode = str(int(match.group(2)))
            break

    # Quality detection
    quality = "N/A"

    quality_match = re.search(
        r"(?i)\b(2160p|1080p|720p|480p|360p|240p|4k)\b",
        text
    )

    if quality_match:
        quality = quality_match.group(1).upper() if quality_match.group(1).lower() == "4k" else quality_match.group(1)

    return season, episode, quality


def create_caption(message):
    media = message.document or message.video or message.audio

    filename = getattr(media, "file_name", "") or ""
    old_caption = message.caption or ""

    season, episode, quality = extract_details(
        filename,
        old_caption
    )

    template = get_template()

    caption = template.format(
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
        "Placeholders:\n"
        "{season}\n"
        "{episode}\n"
        "{quality}"
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
            "/setcaption Series: Money Mafia\n"
            "Season: {season}\n"
            "Episode: {episode}\n"
            "Language: Hindi + English\n"
            "Quality: {quality}"
        )

    required = ["{season}", "{episode}", "{quality}"]

    if not all(item in template for item in required):
        return await message.reply_text(
            "❌ Template must contain:\n"
            "{season}\n"
            "{episode}\n"
            "{quality}"
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
