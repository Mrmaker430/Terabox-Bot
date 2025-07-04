import os
import logging
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FORCE_SUB_CHANNEL = os.getenv("FORCE_SUB_CHANNEL")  # Channel username without @

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

API_URL = "https://teraboxdownloder.rishuapi.workers.dev/?url="

async def is_subscribed(user_id, bot):
    try:
        member = await bot.get_chat_member(chat_id=f"@{FORCE_SUB_CHANNEL}", user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Subscription check error: {e}")
        return False

async def force_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    join_button = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Join Channel", url=f"https://t.me/{FORCE_SUB_CHANNEL}")]]
    )
    await update.message.reply_text(
        f"🔒 To use this bot, you must join our channel first:\n\n"
        f"👉 https://t.me/{FORCE_SUB_CHANNEL}\n\n"
        f"After joining, press /start.",
        reply_markup=join_button,
        disable_web_page_preview=True
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_subscribed(user_id, context.bot):
        await force_subscribe(update, context)
        return
    await update.message.reply_text(
        "👋 Send me a TeraBox link and I'll fetch the download and streaming links for you!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_subscribed(user_id, context.bot):
        await force_subscribe(update, context)
        return

    text = update.message.text.strip()
    if not text.startswith("http"):
        await update.message.reply_text("❌ Please send a valid TeraBox link.")
        return

    await update.message.reply_text("⏳ Fetching links, please wait...")

    try:
        response = requests.get(API_URL + text, timeout=30)
        if response.status_code != 200:
            await update.message.reply_text("❌ Failed to fetch data from API.")
            return

        data = response.json()
        if not data.get("success"):
            await update.message.reply_text("❌ API Error: " + data.get("message", "Unknown error."))
            return

        download_link = data.get("download_link")
        streaming_link = data.get("streaming_link")

        reply = ""
        if download_link:
            reply += f"🔗 <b>Download Link:</b>\n<code>{download_link}</code>\n\n"
        if streaming_link:
            reply += f"▶️ <b>Online Streaming:</b>\n<code>{streaming_link}</code>\n\n"
        if not reply:
            reply = "❌ No links found."

        await update.message.reply_text(reply, parse_mode="HTML")

    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("❌ An error occurred while processing your request.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
    
