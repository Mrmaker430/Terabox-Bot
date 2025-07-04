import os
import logging
import requests
import json
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters,
    ConversationHandler
)

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FORCE_SUB_CHANNEL = os.getenv("FORCE_SUB_CHANNEL")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
DELETE_AFTER_MINUTES = int(os.getenv("DELETE_AFTER_MINUTES", "10"))
STORAGE_CHANNEL_ID = os.getenv("STORAGE_CHANNEL_ID")
API_URL = "API_URL"

USERS_FILE = "users.json"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- User Storage Helpers ---

def load_users():
    if not os.path.exists(USERS_FILE):
        return set()
    with open(USERS_FILE, "r") as f:
        try:
            return set(json.load(f))
        except Exception:
            return set()

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(list(users), f)

def add_user(user_id):
    users = load_users()
    if user_id not in users:
        users.add(user_id)
        save_users(users)
        return True  # New user
    return False  # Existing user

# --- Force Subscription ---

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

# --- Bot Commands ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_subscribed(user_id, context.bot):
        await force_subscribe(update, context)
        return
    is_new = add_user(user_id)
    await update.message.reply_text(
        "👋 Send me a TeraBox link and I'll fetch the download and streaming links for you!"
    )
    # Notify storage channel if new user
    if is_new and STORAGE_CHANNEL_ID:
        try:
            await context.bot.send_message(
                chat_id=STORAGE_CHANNEL_ID,
                text=(
                    f"🆕 <b>New user started the bot!</b>\n"
                    f"👤 <a href='tg://user?id={user_id}'>{user_id}</a>\n"
                    f"Username: @{update.effective_user.username or 'N/A'}"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logging.warning(f"Failed to notify storage channel about new user: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_subscribed(user_id, context.bot):
        await force_subscribe(update, context)
        return
    add_user(user_id)

    text = update.message.text.strip()
    if not text.startswith("http"):
        await update.message.reply_text("❌ Please send a valid TeraBox link.")
        return

    await update.message.reply_text("⏳ Fetching links, please wait...")

    try:
        api_url = API_URL + text
        response = requests.get(api_url, timeout=30)
        if response.status_code != 200:
            await update.message.reply_text(f"❌ Failed to fetch data from API. Status: {response.status_code}")
            if user_id == ADMIN_USER_ID:
                await update.message.reply_text(f"API raw response: {response.text}")
            return

        try:
            data = response.json()
        except Exception as e:
            await update.message.reply_text("❌ API did not return valid JSON.")
            if user_id == ADMIN_USER_ID:
                await update.message.reply_text(f"API raw response: {response.text}")
            return

        if not data.get("success"):
            await update.message.reply_text(
                "❌ Sorry, the TeraBox API is currently unavailable or the link is invalid. Please try again later."
            )
            if user_id == ADMIN_USER_ID:
                await update.message.reply_text(f"API returned error: {data}")
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

        sent = await update.message.reply_text(
            reply + f"\n\n⏳ <i>This message will be deleted in {DELETE_AFTER_MINUTES} minutes.</i>",
            parse_mode="HTML"
        )

        # Schedule deletion
        context.job_queue.run_once(
            delete_message_job,
            DELETE_AFTER_MINUTES * 60,
            data={
                "chat_id": sent.chat_id,
                "message_id": sent.message_id
            }
        )

        # --- Store in private channel ---
        if STORAGE_CHANNEL_ID:
            try:
                # Forward the user's original message (the TeraBox link)
                await context.bot.forward_message(
                    chat_id=STORAGE_CHANNEL_ID,
                    from_chat_id=update.message.chat_id,
                    message_id=update.message.message_id
                )
                # Send the result (download/streaming links) to the storage channel
                await context.bot.send_message(
                    chat_id=STORAGE_CHANNEL_ID,
                    text=(
                        f"👤 User: <a href='tg://user?id={user_id}'>{user_id}</a>\n"
                        f"Username: @{update.effective_user.username or 'N/A'}\n"
                        f"🔗 <b>Original Link:</b> <code>{text}</code>\n\n"
                        f"{reply}"
                    ),
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
            except Exception as e:
                logging.warning(f"Failed to store in private channel: {e}")

    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("❌ An error occurred while processing your request.")

async def delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    try:
        await context.bot.delete_message(
            chat_id=job_data["chat_id"],
            message_id=job_data["message_id"]
        )
    except Exception as e:
        logging.warning(f"Failed to delete message: {e}")

# --- Admin Commands ---

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    users = load_users()
    await update.message.reply_text(f"👥 Total users: <b>{len(users)}</b>", parse_mode="HTML")

# --- Broadcast Conversation ---

BROADCAST = range(1)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return ConversationHandler.END
    await update.message.reply_text("📢 Send the message you want to broadcast to all users.")
    return BROADCAST

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text
    users = load_users()
    count = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=message)
            count += 1
        except Exception as e:
            logging.warning(f"Failed to send to {uid}: {e}")
    await update.message.reply_text(f"✅ Broadcast sent to {count} users.")
    return ConversationHandler.END

async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Broadcast cancelled.")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("users", users_command))
    # Broadcast conversation
    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_command)],
        states={
            BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_message)]
        },
        fallbacks=[CommandHandler("cancel", cancel_broadcast)],
        allow_reentry=True
    )
    app.add_handler(broadcast_conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
