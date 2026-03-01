import os
import logging
import sqlite3
import requests
import qrcode
import edge_tts
import yt_dlp
import asyncio
from PIL import Image
from deep_translator import GoogleTranslator
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

if not TOKEN:
    raise ValueError("BOT_TOKEN missing!")

logging.basicConfig(level=logging.INFO)

# ================= DATABASE =================

db = sqlite3.connect("ultra_v14.db", check_same_thread=False)
cur = db.cursor()
cur.execute(
    "CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, mode TEXT)"
)
db.commit()


def set_mode(user_id, mode):
    cur.execute("INSERT OR REPLACE INTO users VALUES(?,?)", (user_id, mode))
    db.commit()


def get_mode(user_id):
    cur.execute("SELECT mode FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    return row[0] if row else "none"


def get_all_users():
    cur.execute("SELECT user_id FROM users")
    return [x[0] for x in cur.fetchall()]


# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    set_mode(user_id, "none")

    keyboard = [
        [KeyboardButton("💬 AI Chat 🤖"), KeyboardButton("🎵 Song Download 🎶")],
        [KeyboardButton("📄 Image to PDF 📂"), KeyboardButton("🎤 TTS Voice 🗣️")],
        [KeyboardButton("🌐 Translate 🌍"), KeyboardButton("🎬 TikTok Save 📥")],
        [KeyboardButton("🔳 QR Generator 💠"), KeyboardButton("🛡️ URL Safety 🔍")],
        [KeyboardButton("📋 Summarize 📝")],
    ]

    await update.message.reply_text(
        "🚀 Ultra AI Bot v14 Ready!\n\n"
        "👑 Create by Toufiq",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )


# ================= ADMIN =================

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ তুমি admin না!")

    if not context.args:
        return await update.message.reply_text("⚠️ Message দাও")

    msg = " ".join(context.args)
    users = get_all_users()
    sent = 0

    for user in users:
        try:
            await context.bot.send_message(chat_id=user, text=msg)
            sent += 1
        except:
            continue

    await update.message.reply_text(f"✅ Sent to {sent} users")


# ================= MENU =================

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    modes = {
        "💬 AI Chat 🤖": "ai",
        "🎵 Song Download 🎶": "song",
        "📄 Image to PDF 📂": "pdf",
        "🎤 TTS Voice 🗣️": "tts",
        "🌐 Translate 🌍": "tr",
        "🎬 TikTok Save 📥": "tt",
        "🔳 QR Generator 💠": "qr",
        "🛡️ URL Safety 🔍": "safe",
        "📋 Summarize 📝": "sum",
    }

    if text in modes:
        set_mode(user_id, modes[text])
        context.user_data["images"] = []
        return await update.message.reply_text("✅ মোড চালু হয়েছে")

    await process_message(update, context)


# ================= PROCESS =================

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mode = get_mode(user_id)
    text = update.message.text or ""

    try:
        if mode == "ai":
            res = requests.get(f"https://text.pollinations.ai/{text}", timeout=30)
            await update.message.reply_text(res.text[:4000])

        elif mode == "tr":
            translated = GoogleTranslator(source="auto", target="bn").translate(text)
            await update.message.reply_text(translated)

        elif mode == "qr":
            file = f"qr_{user_id}.png"
            img = qrcode.make(text)
            img.save(file)
            with open(file, "rb") as f:
                await update.message.reply_photo(photo=f)
            os.remove(file)

        elif mode == "tts":
            file = f"voice_{user_id}.mp3"
            voice = (
                "bn-BD-NabanitaNeural"
                if any("\u0980" <= c <= "\u09FF" for c in text)
                else "en-US-AvaNeural"
            )
            tts = edge_tts.Communicate(text, voice)
            await tts.save(file)
            with open(file, "rb") as f:
                await update.message.reply_voice(voice=f)
            os.remove(file)

        elif mode == "safe":
            if text.startswith("http"):
                await update.message.reply_text("🔍 লিংক চেক সম্পন্ন। সতর্ক থাকুন।")
            else:
                await update.message.reply_text("⚠️ সঠিক লিংক দিন")

        elif mode == "sum":
            res = requests.get(
                f"https://text.pollinations.ai/Summarize in Bengali: {text}",
                timeout=30,
            )
            await update.message.reply_text(res.text[:4000])

    except Exception as e:
        logging.error(e)
        await update.message.reply_text("❌ Error হয়েছে, আবার চেষ্টা করুন")


# ================= IMAGE TO PDF =================

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_mode(user_id) == "pdf":
        file = await update.message.photo[-1].get_file()
        path = f"{user_id}_{len(context.user_data.get('images', []))}.jpg"
        await file.download_to_drive(path)
        context.user_data.setdefault("images", []).append(path)
        await update.message.reply_text("📸 ছবি যুক্ত হয়েছে")


async def create_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    images = context.user_data.get("images", [])
    if not images:
        return await update.message.reply_text("⚠️ আগে ছবি পাঠান")

    pdf_name = f"{update.effective_user.id}.pdf"
    imgs = [Image.open(i).convert("RGB") for i in images]
    imgs[0].save(pdf_name, save_all=True, append_images=imgs[1:])

    with open(pdf_name, "rb") as f:
        await update.message.reply_document(document=f)

    for i in images:
        os.remove(i)
    os.remove(pdf_name)
    context.user_data["images"] = []


# ================= MAIN =================

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("done", create_pdf))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

    print("🚀 Ultra AI Bot Running...")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
