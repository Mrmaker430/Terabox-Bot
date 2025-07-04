import os
import requests
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Get the bot token from the environment variable
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Function to start the bot
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Welcome! Send me a Terabox link to download or stream.')

# Function to handle Terabox links
def handle_link(update: Update, context: CallbackContext) -> None:
    if context.args:
        terabox_url = context.args[0]
        api_url = f"https://teraboxdownloder.rishuapi.workers.dev/?url={terabox_url}"
        
        response = requests.get(api_url)
        
        if response.status_code == 200:
            data = response.json()
            video_name = data.get('name', 'Unknown Video')
            play_url = data.get('playUrl', 'No URL found')
            update.message.reply_text(f'Video Name: {video_name}\nDownload Link: {play_url}')
        else:
            update.message.reply_text('Failed to fetch the video. Please check the link.')
    else:
        update.message.reply_text('Please provide a Terabox link.')

def main() -> None:
    updater = Updater(TELEGRAM_BOT_TOKEN)
    
    # Register handlers
    updater.dispatcher.add_handler(CommandHandler("start", start))
    updater.dispatcher.add_handler(CommandHandler("link", handle_link))
    
    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
      
