import logging
import os
import re
import json
import threading
import asyncio
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ===== RENDER PORTNI BAND QILISH (Xatolikni oldini oladi) =====
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is active!"

def run_flask():
    # Render 10000-portni talab qiladi
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# ===== SOZLAMALAR =====
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
ADMIN_ID = 6257157305
TOKEN = os.getenv("BOT_TOKEN") # Render Environment Variables'dan olinadi

# Ma'lumotlarni saqlash fayli
DATA_FILE = "bot_data.json"

def load_db():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"answers": {}, "pdfs": {}, "categories": {}, "users": [], "results": {}}

db = load_db()

def save_db():
    with open(DATA_FILE, "w") as f:
        json.dump(db, f)

# ===== KLAVIATURA =====
def get_main_keyboard(user_id):
    btns = [
        [KeyboardButton("🏅 MILLIY SERTIFIKAT (Matematika)"), KeyboardButton("🏅 MILLIY SERTIFIKAT (Fizika)")],
        [KeyboardButton("🏛️ DTM TESTLAR (Matematika)"), KeyboardButton("🏛️ DTM TESTLAR (Fizika)")],
        [KeyboardButton("📊 NATIJA CHIQARISH"), KeyboardButton("👨‍💻 Admin")]
    ]
    if user_id == ADMIN_ID:
        btns.append([KeyboardButton("➕ TEST QO‘SHISH"), KeyboardButton("🔑 KALIT YUKLASH")])
        btns.append([KeyboardButton("👤 FOYDALANUVCHILAR")])
    return ReplyKeyboardMarkup(btns, resize_keyboard=True)

# ===== BOT HANDLERLARI =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in db["users"]:
        db["users"].append(user_id)
        save_db()
    await update.message.reply_text("👋 Assalomu alaykum! Kerakli bo'limni tanlang:", reply_markup=get_main_keyboard(user_id))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    udata = context.user_data

    # Admin: Foydalanuvchilar soni
    if text == "👤 FOYDALANUVCHILAR" and user_id == ADMIN_ID:
        await update.message.reply_text(f"👤 Jami a'zolar: {len(db['users'])} ta")
        return

    # Admin: Test qo'shish boshlanishi
    if text == "➕ TEST QO‘SHISH" and user_id == ADMIN_ID:
        udata['step'] = 'choose_cat'
        await update.message.reply_text("Kategoriyani tanlang:\n1. MAT_MILLIY\n2. FIZ_MILLIY\n3. MAT_DTM\n4. FIZ_DTM")
        return

    # Bosqichma-bosqich ma'lumot yig'ish
    step = udata.get('step')

    if step == 'choose_cat':
        cats = {"1": "MAT_MILLIY", "2": "FIZ_MILLIY", "3": "MAT_DTM", "4": "FIZ_DTM"}
        if text in cats:
            udata['cat'] = cats[text]
            udata['step'] = 'get_id'
            await update.message.reply_text("Ushbu test uchun ID raqam yozing (masalan: 101):")
        return

    if step == 'get_id':
        udata['tid'] = text
        udata['step'] = 'get_pdf'
        await update.message.reply_text(f"ID {text} uchun PDF faylni yuboring.")
        return

    # Admin: Kalit yuklash
    if text == "🔑 KALIT YUKLASH" and user_id == ADMIN_ID:
        udata['step'] = 'key_id'
        await update.message.reply_text("Qaysi Test ID uchun kalit yuklamoqchisiz?")
        return

    if step == 'key_id':
        udata['target_tid'] = text
        udata['step'] = 'key_val'
        await update.message.reply_text("Kalitlarni kiriting (masalan: abcd...):")
        return

    if step == 'key_val':
        tid = udata['target_tid']
        db['answers'][tid] = re.sub(r'[^a-zA-Z]', '', text).lower()
        save_db()
        await update.message.reply_text(f"✅ {tid} ID uchun kalitlar saqlandi!", reply_markup=get_main_keyboard(user_id))
        udata.clear()
        return

    # Natija chiqarish
    if text == "📊 NATIJA CHIQARISH":
        udata['step'] = 'check_res'
        await update.message.reply_text("Natijani bilish uchun Test ID raqamini yuboring:")
        return

    if step == 'check_res':
        tid = text.strip()
        uid_str = str(user_id)
        if tid in db['results'].get(uid_str, {}):
            u_ans = db['results'][uid_str][tid]
            c_ans = db['answers'].get(tid)
            if not c_ans:
                await update.message.reply_text("❗ Bu test uchun kalitlar hali yuklanmagan.")
            else:
                correct = sum(1 for u, c in zip(u_ans, c_ans) if u == c)
                total = len(c_ans)
                await update.message.reply_text(f"🎯 Natijangiz:\n✅ To'g'ri: {correct}/{total}\n📈 Foiz: {(correct*100)//total}%")
        else:
            await update.message.reply_text("❌ Siz bu testni hali topshirmagansiz.")
        udata.clear()
        return

    # Test bo'limlarini tanlash
    category_map = {
        "🏅 MILLIY SERTIFIKAT (Matematika)": "MAT_MILLIY",
        "🏅 MILLIY SERTIFIKAT (Fizika)": "FIZ_MILLIY",
        "🏛️ DTM TESTLAR (Matematika)": "MAT_DTM",
        "🏛️ DTM TESTLAR (Fizika)": "FIZ_DTM"
    }
    
    if text in category_map:
        target_cat = category_map[text]
        available = [tid for tid, cat in db['categories'].items() if cat == target_cat]
        if not available:
            await update.message.reply_text("⚠️ Hozircha bu bo'limda testlar yo'q.")
        else:
            tid = available[0] # Eng oxirgi qo'shilganini chiqarish mantiqi
            path = db['pdfs'].get(tid)
            if path and os.path.exists(path):
                udata['active_tid'] = tid
                udata['step'] = 'solving'
                await update.message.reply_document(document=open(path, 'rb'), caption=f"📝 Test ID: {tid}\n\nJavoblarni shunchaki matn ko'rinishida yuboring.")
        return

    if step == 'solving':
        tid = udata['active_tid']
        ans = re.sub(r'[^a-zA-Z]', '', text).lower()
        uid_str = str(user_id)
        if uid_str not in db['results']: db['results'][uid_str] = {}
        db['results'][uid_str][tid] = ans
        save_db()
        await update.message.reply_text("✅ Javoblaringiz qabul qilindi! Natijani bilish uchun 'NATIJA CHIQARISH' tugmasini bosing.")
        udata.clear()

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    udata = context.user_data
    if user_id == ADMIN_ID and udata.get('step') == 'get_pdf':
        doc = update.message.document
        tid = udata['tid']
        cat = udata['cat']
        f_name = f"{tid}.pdf"
        file = await context.bot.get_file(doc.file_id)
        await file.download_to_drive(f_name)
        db['pdfs'][tid] = f_name
        db['categories'][tid] = cat
        save_db()
        await update.message.reply_text(f"✅ Test muvaffaqiyatli saqlandi! ID: {tid}", reply_markup=get_main_keyboard(user_id))
        udata.clear()

# ===== MAIN RUN =====
if __name__ == "__main__":
    # Flask port band qilish
    threading.Thread(target=run_flask, daemon=True).start()
    
    if not TOKEN:
        logging.error("❌ TOKEN TOPILMADI!")
    else:
        # v20.x uchun barqaror ishga tushirish
        app = ApplicationBuilder().token(TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        app.add_handler(MessageHandler(filters.Document.PDF, handle_document))
        
        logging.info("Bot ishga tushmoqda...")
        app.run_polling(drop_pending_updates=True)
