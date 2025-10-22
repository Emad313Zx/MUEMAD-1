import os
import logging
import asyncio
import tempfile
import shutil
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from yt_dlp import YoutubeDL, DownloadError

# Set up Flask app for web service
app = Flask(__name__)

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8348486900:AAEmiSgwX0B9ByJjbla_ytqKjGCPGCzbKjE"

async def download_audio_file(query: str) -> str | None:
    """Download audio file and return the file path"""
    temp_dir = tempfile.mkdtemp()
    filename = os.path.join(temp_dir, "temp_song.%(ext)s")
    
    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "outtmpl": filename,
        "default_search": "ytsearch1",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    
    try:
        loop = asyncio.get_event_loop()
        with YoutubeDL(ydl_opts) as ydl:
            await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=True))
        
        # Find the actual downloaded file
        for file in os.listdir(temp_dir):
            if file.endswith('.mp3'):
                return os.path.join(temp_dir, file)
        return None
        
    except DownloadError as e:
        logger.error(f"Download error: {e}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None

async def yt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /song command"""
    if not context.args:
        await update.message.reply_text("📌 Please type the song name after /song\nExample: /song Fairuz")
        return

    query = " ".join(context.args)
    loading_msg = None

    try:
        loading_msg = await update.message.reply_text(f"🔍 Searching for: {query} ...")
        path = await download_audio_file(query)

        if loading_msg:
            await loading_msg.delete()

        if path and os.path.exists(path):
            try:
                file_size = os.path.getsize(path)
                if file_size > 50 * 1024 * 1024:
                    await update.message.reply_text("❌ File is too large (more than 50MB)")
                    shutil.rmtree(os.path.dirname(path), ignore_errors=True)
                    return

                with open(path, "rb") as audio_file:
                    await update.message.reply_audio(
                        audio=audio_file, 
                        caption=f"🎶 {query}",
                        read_timeout=60,
                        write_timeout=60,
                        connect_timeout=60,
                        pool_timeout=60
                    )
                
                shutil.rmtree(os.path.dirname(path), ignore_errors=True)
                
            except Exception as e:
                logger.error(f"Error sending file: {e}")
                await update.message.reply_text("❌ Error while sending the file.")
                if path and os.path.exists(path):
                    shutil.rmtree(os.path.dirname(path), ignore_errors=True)
        else:
            await update.message.reply_text("❌ Song not found.")

    except Exception as e:
        logger.error(f"Unexpected error in yt_command: {e}")
        if loading_msg:
            try:
                await loading_msg.delete()
            except:
                pass
        await update.message.reply_text("❌ Unexpected error occurred.")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command"""
    await update.message.reply_text("🎵 Welcome! Send /song + song name and I'll send you the audio 🎶\n\n🎵 مرحبا! أرسل الأمر /song + اسم الأغنية وسأرسل لك المقطع الصوتي 🎶")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command"""
    help_text = """
🤖 **Bot Commands:**

/start - Start the bot
/song [song name] - Download audio from YouTube
/help - Show this help message

📝 **Examples:**
/song Fairuz
/song Adele hello
/song "Queen Bohemian Rhapsody"

🎵 **أوامر البوت:**

/start - بدء البوت
/song [اسم الأغنية] - تحميل صوت من يوتيوب
/help - عرض رسالة المساعدة
"""
    await update.message.reply_text(help_text)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the telegram bot"""
    logger.error(f"Exception while handling an update: {context.error}")

def run_bot():
    """Run the Telegram bot in a separate thread"""
    try:
        bot_app = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        bot_app.add_handler(CommandHandler("start", start_command))
        bot_app.add_handler(CommandHandler("song", yt_command))
        bot_app.add_handler(CommandHandler("s", yt_command))
        bot_app.add_handler(CommandHandler("help", help_command))
        
        bot_app.add_error_handler(error_handler)
        
        logger.info("🤖 Telegram Bot is starting...")
        print("✅ Bot is running and waiting for messages...")
        
        # Run the bot
        bot_app.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

@app.route('/')
def home():
    """Root endpoint for web service"""
    return "🤖 Telegram Music Bot is running! Use /start in Telegram to begin."

@app.route('/health')
def health():
    """Health check endpoint"""
    return "✅ Bot is healthy and running"

@app.route('/status')
def status():
    """Status endpoint"""
    return "🎵 Music Bot Status: Active - Ready to download songs"

# Start the bot when the web service starts
if __name__ == '__main__':
    # Start the Telegram bot in a separate thread
    bot_thread = Thread(target=lambda: asyncio.run(run_bot()))
    bot_thread.daemon = True
    bot_thread.start()
    
    # Start the Flask web server
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
