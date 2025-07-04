import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Get the bot token from the environment variable
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Function to start the bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Welcome! Send me a Terabox link to download or stream.')

# Function to handle Terabox links
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        terabox_url = context.args[0]
        api_url = f"https://teraboxdownloder.rishuapi.workers.dev/?url={terabox_url}"
        
        response = requests.get(api_url)
        
        if response.status_code == 200:
            data = response.json()
            video_name = data.get('name', 'Unknown Video')
            play_url = data.get('playUrl', 'No URL found')
            await update.message.reply_text(f'Video Name: {video_name}\nDownload Link: {play_url}')
        else:
            await update.message.reply_text('Failed to fetch the video. Please check the link.')
    else:
        await update.message.reply_text('Please provide a Terabox link.')

async def main() -> None:
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("link", handle_link))
    
    # Start the bot
    await application.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
        
