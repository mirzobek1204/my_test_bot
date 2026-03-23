import logging
import os
import re
import json
import threading
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ===== RENDER UCHUN WEB SERVER =====
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot is live!"

def run_flask():
    # Render 10000-portni talab qiladi
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# ===== SOZLAMALAR =====
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
ADMIN_ID = 6257157305
TOKEN = os.getenv("BOT_TOKEN")

# MA'LUMOTLAR BAZASI
DB_FILE = "bot_db.json"
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: return json.load(f)
    return {"answers": {}, "pdfs": {}, "categories": {}, "users": [], "results": {}}

db = load_db()
def save_db():
    with open(DB_FILE, "w") as f: json.dump(db, f)

# ===== KLAVIATURALAR =====
def main_menu(user_id):
    btns = [
        [KeyboardButton("🏅 MILLIY SERTIFIKAT (Matematika)"), KeyboardButton("🏅 MILLIY SERTIFIKAT (Fizika)")],
        [KeyboardButton("🏛️ DTM TESTLAR (Matematika)"), KeyboardButton("🏛️ DTM TESTLAR (Fizika)")],
        [KeyboardButton("📊 NATIJA CHIQARISH"), KeyboardButton("👨‍💻 Admin")]
    ]
    if user_id == ADMIN_ID:
        btns.append([KeyboardButton("➕ TEST QO‘SHISH"), KeyboardButton("🔑 KALIT YUKLASH")])
    return ReplyKeyboardMarkup(btns, resize_keyboard=True)

def test_start_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🚀 Testni boshlash")],
        [KeyboardButton("🔙 ASOSIY MENYU")]
    ], resize_keyboard=True)

# ===== ASOSIY LOGIKA =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in db["users"]:
        db["users"].append(uid)
        save_db()
    context.user_data.clear()
    await update.message.reply_text("👋 Xush kelibsiz! Bo'limni tanlang:", reply_markup=main_menu(uid))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    udata = context.user_data

    # 🔙 ASOSIY MENYU
    if text == "🔙 ASOSIY MENYU":
        udata.clear()
        await update.message.reply_text("Asosiy menyuga qaytdingiz:", reply_markup=main_menu(uid))
        return

    # --- USER: TEST TANLASH ---
    categories = {
        "🏅 MILLIY SERTIFIKAT (Matematika)": "MAT_MILLIY",
        "🏅 MILLIY SERTIFIKAT (Fizika)": "FIZ_MILLIY",
        "🏛️ DTM TESTLAR (Matematika)": "MAT_DTM",
        "🏛️ DTM TESTLAR (Fizika)": "FIZ_DTM"
    }

    if text in categories:
        target = categories[text]
        available = [tid for tid, cat in db["categories"].items() if cat == target]
        if not available:
            await update.message.reply_text("⚠️ Hozircha bu bo'limda testlar yo'q.")
        else:
            udata['active_tid'] = available[-1] # Eng oxirgi testni olish
            udata['step'] = 'waiting_to_start'
            await update.message.reply_text(f"💎 Test ID: {udata['active_tid']}\nTestni boshlashga tayyormisiz?", reply_markup=test_start_menu())
        return

    # --- USER: TESTNI BOSHLASH VA YUBORISH ---
    if text == "🚀 Testni boshlash" and udata.get('step') == 'waiting_to_start':
        tid = udata.get('active_tid')
        path = db["pdfs"].get(tid)
        if path and os.path.exists(path):
            udata['step'] = 'solving'
            await update.message.reply_document(document=open(path, 'rb'), caption=f"📝 Test ID: {tid}\nJavoblarni matn sifatida yuboring (masalan: abcd...):")
        else:
            await update.message.reply_text("❌ PDF fayl topilmadi.")
        return

    if udata.get('step') == 'solving':
        tid = udata.get('active_tid')
        ans = re.sub(r'[^a-zA-Z]', '', text).lower()
        uid_s = str(uid)
        if uid_s not in db["results"]: db["results"][uid_s] = {}
        db["results"][uid_s][tid] = ans
        save_db()
        await update.message.reply_text("✅ Javoblaringiz saqlandi! Natijani 'NATIJA CHIQARISH' bo'limidan ko'rishingiz mumkin.", reply_markup=main_menu(uid))
        udata.clear()
        return

    # --- ADMIN: TEST QO'SHISH (PDF) ---
    if uid == ADMIN_ID:
        if text == "➕ TEST QO‘SHISH":
            udata['step'] = 'admin_cat'
            await update.message.reply_text("Kategoriyani tanlang:\n1. MAT_MILLIY\n2. FIZ_MILLIY\n3. MAT_DTM\n4. FIZ_DTM")
            return

        if udata.get('step') == 'admin_cat':
            m = {"1": "MAT_MILLIY", "2": "FIZ_MILLIY", "3": "MAT_DTM", "4": "FIZ_DTM"}
            if text in m:
                udata['new_cat'] = m[text]
                udata['step'] = 'admin_id'
                await update.message.reply_text("Yangi Test ID raqamini yozing:")
            return

        if udata.get('step') == 'admin_id':
            udata['new_tid'] = text
            udata['step'] = 'admin_pdf'
            await update.message.reply_text(f"ID: {text} uchun PDF faylni yuboring.")
            return

        # --- ADMIN: KALIT YUKLASH ---
        if text == "🔑 KALIT YUKLASH":
            udata['step'] = 'key_id'
            await update.message.reply_text("Qaysi ID uchun kalit yuklaysiz?")
            return

        if udata.get('step') == 'key_id':
            udata['target_tid'] = text
            udata['step'] = 'key_val'
            await update.message.reply_text("Kalitlarni yuboring (abcd...):")
            return

        if udata.get('step') == 'key_val':
            tid = udata['target_tid']
            db["answers"][tid] = text.lower()
            save_db()
            await update.message.reply_text(f"✅ ID: {tid} uchun kalitlar saqlandi!", reply_markup=main_menu(uid))
            udata.clear()
            return

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    udata = context.user_data
    if uid == ADMIN_ID and udata.get('step') == 'admin_pdf':
        tid = udata['new_tid']
        cat = udata['new_cat']
        file = await context.bot.get_file(update.message.document.file_id)
        path = f"{tid}.pdf"
        await file.download_to_drive(path)
        db["pdfs"][tid] = path
        db["categories"][tid] = cat
        save_db()
        await update.message.reply_text(f"✅ Test ID: {tid} muvaffaqiyatli yuklandi!", reply_markup=main_menu(uid))
        udata.clear()

# ===== RUN BOT =====
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    if not TOKEN:
        logging.error("BOT_TOKEN TOPILMADI!")
    else:
        # Yangi ApplicationBuilder v20.x uchun
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        app.add_handler(MessageHandler(filters.Document.PDF, handle_document))
        logging.info("Bot ishga tushdi...")
        app.run_polling(drop_pending_updates=True)
