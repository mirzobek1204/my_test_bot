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
def home(): return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# ===== CONFIG =====
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
ADMIN_ID = 6257157305
TOKEN = os.getenv("BOT_TOKEN")

# ===== DATA STORAGE =====
db_file = "bot_db.json"
def load_db():
    if os.path.exists(db_file):
        with open(db_file, "r") as f: return json.load(f)
    return {"answers": {}, "pdfs": {}, "categories": {}, "users": [], "results": {}}

db = load_db()
def save_db():
    with open(db_file, "w") as f: json.dump(db, f)

# ===== KEYBOARDS =====
def main_menu(user_id):
    btns = [
        [KeyboardButton("🏅 MILLIY SERTIFIKAT (Matematika)"), KeyboardButton("🏅 MILLIY SERTIFIKAT (Fizika)")],
        [KeyboardButton("🏛️ DTM TESTLAR (Matematika)"), KeyboardButton("🏛️ DTM TESTLAR (Fizika)")],
        [KeyboardButton("📊 NATIJA CHIQARISH"), KeyboardButton("👨+👨‍💻 Admin")]
    ]
    if user_id == ADMIN_ID:
        btns.append([KeyboardButton("➕ TEST QO‘SHISH"), KeyboardButton("🔑 KALIT YUKLASH")])
    return ReplyKeyboardMarkup(btns, resize_keyboard=True)

def test_start_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🚀 Testni boshlash")],
        [KeyboardButton("🔙 ASOSIY MENYU")]
    ], resize_keyboard=True)

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in db["users"]:
        db["users"].append(uid)
        save_db()
    context.user_data.clear()
    await update.message.reply_text("Xush kelibsiz! Bo'limni tanlang:", reply_markup=main_menu(uid))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    udata = context.user_data

    # 🔙 ASOSIY MENYUGA QAYTISH
    if text == "🔙 ASOSIY MENYU":
        udata.clear()
        await update.message.reply_text("Asosiy menyuga qaytdingiz:", reply_markup=main_menu(uid))
        return

    # KATEGORIYA TANLANGANDA
    cats = {
        "🏅 MILLIY SERTIFIKAT (Matematika)": "MAT_MILLIY",
        "🏅 MILLIY SERTIFIKAT (Fizika)": "FIZ_MILLIY",
        "🏛️ DTM TESTLAR (Matematika)": "MAT_DTM",
        "🏛️ DTM TESTLAR (Fizika)": "FIZ_DTM"
    }

    if text in cats:
        target_cat = cats[text]
        available = [tid for tid, cat in db["categories"].items() if cat == target_cat]
        if not available:
            await update.message.reply_text("⚠️ Bu bo'limda testlar yo'q.")
        else:
            udata['active_tid'] = available[-1] # Oxirgi test
            udata['step'] = 'waiting_to_start'
            await update.message.reply_text(f"💎 Test topildi! ID: {udata['active_tid']}\nTestni boshlaymizmi?", reply_markup=test_start_menu())
        return

    # 🚀 TESTNI BOSHLASH
    if text == "🚀 Testni boshlash" and udata.get('step') == 'waiting_to_start':
        tid = udata.get('active_tid')
        path = db["pdfs"].get(tid)
        if path and os.path.exists(path):
            udata['step'] = 'solving'
            await update.message.reply_document(document=open(path, 'rb'), caption=f"📝 Test ID: {tid}\n\nJavoblarni matn ko'rinishida yuboring (masalan: abcd...).")
        else:
            await update.message.reply_text("❌ Xato: PDF topilmadi.")
        return

    # TEST JAVOBLARINI QABUL QILISH
    if udata.get('step') == 'solving':
        tid = udata.get('active_tid')
        ans = re.sub(r'[^a-zA-Z]', '', text).lower()
        uid_s = str(uid)
        if uid_s not in db["results"]: db["results"][uid_s] = {}
        db["results"][uid_s][tid] = ans
        save_db()
        await update.message.reply_text(f"✅ Javoblar qabul qilindi!\nID: {tid}\nNatijani 'NATIJA CHIQARISH' bo'limidan ko'rishingiz mumkin.", reply_markup=main_menu(uid))
        udata.clear()
        return

    # ADMIN FUNKSIYALARI (Qisqacha)
    if uid == ADMIN_ID:
        if text == "➕ TEST QO‘SHISH":
            udata['step'] = 'admin_cat'
            await update.message.reply_text("Kategoriya raqamini yuboring: 1.MAT_M 2.FIZ_M 3.MAT_D 4.FIZ_D")
        elif text == "🔑 KALIT YUKLASH":
            udata['step'] = 'admin_key_id'
            await update.message.reply_text("Test ID yozing:")

# ===== ASOSIY ISHGA TUSHIRISH =====
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start() # Render uchun port band qilish
    
    if TOKEN:
        # Yangi ApplicationBuilder (v20.x uchun)
        app = ApplicationBuilder().token(TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        logging.info("Bot ishga tushdi...")
        app.run_polling(drop_pending_updates=True)
