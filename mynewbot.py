import logging
import os
import re
import json
import threading
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ===== RENDER PORTNI BAND QILISH =====
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is live!"

def run_flask():
    # Render 10000-portni talab qiladi
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# ===== SOZLAMALAR =====
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
ADMIN_ID = 6257157305
TOKEN = os.getenv("BOT_TOKEN")

# Ma'lumotlar bazasi (JSON fayl bilan)
DATA_FILE = "bot_data.json"

def load_all_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"answers": {}, "pdfs": {}, "categories": {}, "users": []}

db = load_all_data()

def save_all_data():
    with open(DATA_FILE, "w") as f:
        json.dump(db, f)

# ===== ADMIN STATE =====
admin_temp_data = {}

# ===== KLAVIATURA =====
def main_menu(user_id):
    btns = [
        [KeyboardButton("🏅 MILLIY SERTIFIKAT (Matematika)"), KeyboardButton("🏅 MILLIY SERTIFIKAT (Fizika)")],
        [KeyboardButton("🏛️ DTM TESTLAR (Matematika)"), KeyboardButton("🏛️ DTM TESTLAR (Fizika)")],
        [KeyboardButton("📊 NATIJA CHIQARISH"), KeyboardButton("👨‍💻 Admin")]
    ]
    if user_id == ADMIN_ID:
        btns.append([KeyboardButton("➕ TEST QO‘SHISH"), KeyboardButton("🔑 KALIT YUKLASH")])
    return ReplyKeyboardMarkup(btns, resize_keyboard=True)

# ===== BOT LOGIKASI =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in db["users"]:
        db["users"].append(uid)
        save_all_data()
    await update.message.reply_text("Xush kelibsiz!", reply_markup=main_menu(uid))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id

    if text == "➕ TEST QO‘SHISH" and uid == ADMIN_ID:
        context.user_data['step'] = 'get_cat'
        await update.message.reply_text("Kategoriyani tanlang:\n1. MAT_MILLIY\n2. FIZ_MILLIY")
        return

    if context.user_data.get('step') == 'get_cat':
        context.user_data['cat'] = "MAT_MILLIY" if text == "1" else "FIZ_MILLIY"
        context.user_data['step'] = 'get_id'
        await update.message.reply_text("Test uchun ID raqam yozing:")
        return

    if context.user_data.get('step') == 'get_id':
        context.user_data['tid'] = text
        context.user_data['step'] = 'get_pdf'
        await update.message.reply_text("Endi PDF faylini yuboring.")
        return

    # Kalit yuklash qismi
    if text == "🔑 KALIT YUKLASH" and uid == ADMIN_ID:
        context.user_data['step'] = 'key_id'
        await update.message.reply_text("Qaysi ID uchun kalit yuklaysiz?")
        return

    if context.user_data.get('step') == 'key_id':
        context.user_data['target_id'] = text
        context.user_data['step'] = 'key_val'
        await update.message.reply_text("Kalitlarni yuboring (masalan: abcd...):")
        return

    if context.user_data.get('step') == 'key_val':
        tid = context.user_data['target_id']
        db["answers"][tid] = text.lower()
        save_all_data()
        await update.message.reply_text(f"Tayyor! {tid} uchun kalitlar saqlandi.")
        context.user_data.clear()
        return

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid == ADMIN_ID and context.user_data.get('step') == 'get_pdf':
        tid = context.user_data['tid']
        cat = context.user_data['cat']
        file = await context.bot.get_file(update.message.document.file_id)
        path = f"{tid}.pdf"
        await file.download_to_drive(path)
        db["pdfs"][tid] = path
        db["categories"][tid] = cat
        save_all_data()
        await update.message.reply_text("Test muvaffaqiyatli qo'shildi!")
        context.user_data.clear()

# ===== ASOSIY ISHGA TUSHIRISH =====
if __name__ == "__main__":
    # 1. Flaskni alohida thread'da yoqish
    threading.Thread(target=run_flask, daemon=True).start()

    if not TOKEN:
        print("XATO: BOT_TOKEN topilmadi!")
    else:
        # 2. Telegram botni sozlash (v20.8 versiya uchun)
        application = ApplicationBuilder().token(TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_docs))
        
        print("Bot ishlamoqda...")
        application.run_polling(drop_pending_updates=True)
