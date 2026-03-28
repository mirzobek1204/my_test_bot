import logging
import os
import re
import json
import threading
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ===== LOGGING & SERVER =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

server = Flask('')

@server.route('/')
def home():
    return "Bot is live! 🚀"

def run():
    port = int(os.environ.get("PORT", 10000))
    server.run(host='0.0.0.0', port=port)

# ===== DATABASE =====
MONGO_URL = os.getenv("MONGO_URL")
db = {"answers": {}, "pdfs": {}, "categories": {}, "users": [], "results": {}}

def save_data():
    with open("data.json", "w") as f:
        json.dump(db, f, indent=4)
    if MONGO_URL:
        def bg_save():
            try:
                from pymongo import MongoClient
                client = MongoClient(MONGO_URL)
                client["test_arena_db"]["bot_data"].update_one(
                    {"_id": "main_storage"}, {"$set": db}, upsert=True
                )
            except Exception as e:
                logging.error(f"MongoDB save error: {e}")
        threading.Thread(target=bg_save).start()

def load_data():
    global db
    if MONGO_URL:
        try:
            from pymongo import MongoClient
            client = MongoClient(MONGO_URL)
            data = client["test_arena_db"]["bot_data"].find_one({"_id": "main_storage"})
            if data:
                for k in db.keys():
                    if k in data: db[k] = data[k]
                return
        except Exception as e:
            logging.error(f"MongoDB load error: {e}")
    if os.path.exists("data.json"):
        with open("data.json", "r") as f:
            loaded = json.load(f)
            for k in db.keys():
                if k in loaded: db[k] = loaded[k]

# ===== CONFIG & KEYBOARDS =====
ADMIN_ID = 6257157305
TOKEN = os.getenv("BOT_TOKEN")

def get_main_keyboard(user_id):
    btns = [
        [KeyboardButton("🥇 MILLIY SERTIFIKAT (Matematika)"), KeyboardButton("🥇 MILLIY SERTIFIKAT (Fizika)")],
        [KeyboardButton("🏛️ DTM TESTLAR (Matematika)"), KeyboardButton("🏛️ DTM TESTLAR (Fizika)")],
        [KeyboardButton("📊 NATIJA TEKSHIRISH"), KeyboardButton("📜 MENING NATIJALARIM")],
        [KeyboardButton("👨‍💻 Adminga bog'lanish")]
    ]
    if user_id == ADMIN_ID:
        btns.append([KeyboardButton("➕ TEST QO'SHISH"), KeyboardButton("🔑 KALIT YUKLASH")])
        btns.append([KeyboardButton("👥 STATISTIKA")])
    return ReplyKeyboardMarkup(btns, resize_keyboard=True)

def get_back_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("🔙 ASOSIY MENYU")]], resize_keyboard=True)

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id  # int
    if uid not in db["users"]: 
        db["users"].append(uid)
    save_data()
    await update.message.reply_text(
        "👋 TestArena botiga xush kelibsiz!", 
        reply_markup=get_main_keyboard(uid)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    user_data = context.user_data

    # --- 1. ASOSIY BUYRUQLAR ---
    if text in ["🔙 ASOSIY MENYU", "🛑 TESTNI YAKUNLASH"]:
        user_data.pop('state', None)
        user_data.pop('admin_state', None)
        return await update.message.reply_text(
            "🏠 Asosiy menyu:", reply_markup=get_main_keyboard(uid)
        )

    if text == "👨‍💻 Adminga bog'lanish":
        return await update.message.reply_text("👨‍💻 Admin bilan bog'lanish: @miracle_1204")

    # --- 2. FAQAT ADMIN ---
    if uid == ADMIN_ID:
        # Statistik
        if text == "👥 STATISTIKA":
            u_count = len(db.get("users", []))
            t_count = len(db.get("answers", {}))
            return await update.message.reply_text(
                f"📊 **BOT STATISTIKASI**\n\n👤 Jami foydalanuvchilar: {u_count}\n📝 Yuklangan testlar: {t_count}"
            )
        # Test qo‘shish bosqichlari
        if text == "➕ TEST QO'SHISH":
            user_data['admin_state'] = "cat"
            return await update.message.reply_text(
                "Bo'limni tanlang:\n1. Mat Milliy\n2. Fiz Milliy\n3. Mat DTM\n4. Fiz DTM", 
                reply_markup=get_back_keyboard()
            )
        if user_data.get('admin_state') == "cat":
            cs = {"1":"MAT_MILLIY","2":"FIZ_MILLIY","3":"MAT_DTM","4":"FIZ_DTM"}
            if text in cs:
                user_data.update({"tcat": cs[text], "admin_state": "tid"})
                return await update.message.reply_text("Test ID-ni yozing (Masalan: M-01):", reply_markup=get_back_keyboard())
        elif user_data.get('admin_state') == "tid":
            user_data.update({"ttid": text.upper(), "admin_state": "tfile"})
            return await update.message.reply_text(f"ID: {text.upper()}. Endi PDF-ni yuboring:", reply_markup=get_back_keyboard())

        # Kalit yuklash bosqichlari
        if text == "🔑 KALIT YUKLASH":
            user_data['admin_state'] = "kid"
            return await update.message.reply_text("Test ID-ni yozing:", reply_markup=get_back_keyboard())
        elif user_data.get('admin_state') == "kid":
            user_data.update({"tkid": text.upper(), "admin_state": "kval"})
            return await update.message.reply_text(f"'{text.upper()}' uchun kalitlarni yuboring:", reply_markup=get_back_keyboard())
        elif user_data.get('admin_state') == "kval":
            db["answers"][user_data["tkid"]] = re.sub(r'[^a-eA-E]', '', text).lower()
            save_data()
            user_data.clear()
            return await update.message.reply_text("✅ Saqlandi!", reply_markup=get_main_keyboard(ADMIN_ID))

    # --- 3. NATIJA TEKSHIRISH ---
    if text == "📊 NATIJA TEKSHIRISH":
        user_data['state'] = 'check_id'
        return await update.message.reply_text("📝 Test ID-ni yozing:", reply_markup=get_back_keyboard())

    if user_data.get('state') == 'check_id':
        tid = text.upper()
        if tid not in db["answers"]:
            return await update.message.reply_text("❌ ID topilmadi. Qayta urinib ko'ring.", reply_markup=get_back_keyboard())
        user_data.update({"ctid": tid, "state": "check_ans"})
        return await update.message.reply_text(f"✅ {tid} topildi. Javoblarni yuboring:", reply_markup=get_back_keyboard())

    if user_data.get('state') == 'check_ans':
        tid = user_data['ctid']
        correct = db["answers"][tid]
        u_ans = re.sub(r'[^a-eA-E]', '', text).lower()
        score = sum(1 for i, char in enumerate(correct) if i < len(u_ans) and u_ans[i] == char)
        user_data.clear()
        save_data()
        return await update.message.reply_text(f"📊 Natija: {score}/{len(correct)}", reply_markup=get_main_keyboard(uid))

    # --- 4. BO'LIM TANLASH ---
    all_menus = [
        "🥇 MILLIY SERTIFIKAT (Matematika)", "🥇 MILLIY SERTIFIKAT (Fizika)",
        "🏛️ DTM TESTLAR (Matematika)", "🏛️ DTM TESTLAR (Fizika)"
    ]
    if text in all_menus:
        sc = "MAT_MILLIY" if "Matematika" in text and "MILLIY" in text else \
             "FIZ_MILLIY" if "Fizika" in text and "MILLIY" in text else \
             "MAT_DTM" if "Matematika" in text and "DTM" in text else "FIZ_DTM"
        av = [t for t, c in db["categories"].items() if c == sc]
        if not av: return await update.message.reply_text("⚠️ Hozircha testlar yo'q.")
        btns = [[KeyboardButton(t)] for t in av] + [[KeyboardButton("🔙 ASOSIY MENYU")]]
        user_data['state'] = 'choosing'
        return await update.message.reply_text("📑 Tanlang:", reply_markup=ReplyKeyboardMarkup(btns, resize_keyboard=True))

    if user_data.get('state') == 'choosing' and text in db["categories"]:
        path = db["pdfs"].get(text)
        if path and os.path.exists(path):
            with open(path, 'rb') as f:
                await update.message.reply_document(document=f, caption=f"ID: {text}")
        return

    # --- 5. TUSHUNARSIZ XABAR ---
    await update.message.reply_text(
        "⚠️ Noma'lum buyruq. Iltimos, menyudagi tugmalardan foydalaning.",
        reply_markup=get_main_keyboard(uid)
    )

async def handle_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID and context.user_data.get('admin_state') == "tfile":
        tid, cat = context.user_data["ttid"], context.user_data["tcat"]
        file = await context.bot.get_file(update.message.document.file_id)
        path = f"{tid}.pdf"
        await file.download_to_drive(path)
        db["pdfs"][tid], db["categories"][tid] = path, cat
        save_data()
        await update.message.reply_text("✅ Test PDF yuklandi!", reply_markup=get_main_keyboard(ADMIN_ID))
        context.user_data.clear()

# ===== BOT ISHLASHI =====
if __name__ == "__main__":
    load_data()
    threading.Thread(target=run, daemon=True).start()
    if TOKEN:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(MessageHandler(filters.Document.PDF, handle_doc))
        app.run_polling(drop_pending_updates=True, poll_interval=0.5)
