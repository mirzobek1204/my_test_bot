import logging
import os
import re
import json
import threading
import requests
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ===== LOGGING & SERVER =====
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
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
                client["test_arena_db"]["bot_data"].update_one({"_id": "main_storage"}, {"$set": db}, upsert=True)
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
GEMINI_KEY = os.getenv("GEMINI_API_KEY") 

def get_main_keyboard(user_id):
    btns = [
        [KeyboardButton("🥇 MILLIY SERTIFIKAT (Matematika)"), KeyboardButton("🥇 MILLIY SERTIFIKAT (Fizika)")],
        [KeyboardButton("🏛️ DTM TESTLAR (Matematika)"), KeyboardButton("🏛️ DTM TESTLAR (Fizika)")],
        [KeyboardButton("📊 NATIJA TEKSHIRISH"), KeyboardButton("🤖 Ask AI")],
        [KeyboardButton("👨‍💻 Adminga bog'lanish")]
    ]
    if user_id == ADMIN_ID:
        btns.append([KeyboardButton("➕ TEST QO'SHISH"), KeyboardButton("🔑 KALIT YUKLASH")])
        btns.append([KeyboardButton("👥 STATISTIKA")])
    return ReplyKeyboardMarkup(btns, resize_keyboard=True)

def get_back_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("🔙 ASOSIY MENYU")]], resize_keyboard=True)

# ===== Gemini AI (404 TUZATILGAN) =====
def ask_gemini(question):
    if not GEMINI_KEY:
        return "❌ Gemini API kaliti topilmadi."
    
    # URL manzilini v1beta1 deb o'zgartirdik, bu barcha modellarni qo'llab-quvvatlaydi
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": question}]
        }]
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        res_json = resp.json()
        
        if resp.status_code != 200:
            # Xato xabarini aniq ko'rsatish
            error_msg = res_json.get('error', {}).get('message', 'Noma\'lum xato')
            return f"❌ AI xatosi ({resp.status_code}): {error_msg}"

        return res_json['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"❌ Texnik xatolik: {str(e)}"

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in db["users"]: db["users"].append(uid)
    save_data()
    await update.message.reply_text("👋 TestArena botiga xush kelibsiz!", reply_markup=get_main_keyboard(uid))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    user_data = context.user_data

    if text == "🔙 ASOSIY MENYU":
        user_data.clear()
        return await update.message.reply_text("🏠 Asosiy menyu:", reply_markup=get_main_keyboard(uid))

    if text == "👨‍💻 Adminga bog'lanish":
        return await update.message.reply_text("👨‍💻 Admin: @miracle_1204")

    # --- AI REJIMI ---
    if text == "🤖 Ask AI":
        user_data['state'] = 'ai_mode'
        return await update.message.reply_text("🤖 Savolingizni yozing:", reply_markup=get_back_keyboard())

    if user_data.get('state') == 'ai_mode':
        await context.bot.send_chat_action(chat_id=uid, action="typing")
        return await update.message.reply_text(ask_gemini(text))

    # --- ADMIN FUNKSIYALARI ---
    if uid == ADMIN_ID:
        if text == "👥 STATISTIKA":
            return await update.message.reply_text(f"📊 Foydalanuvchilar: {len(db['users'])}\n📝 Testlar: {len(db['pdfs'])}")
        
        if text == "➕ TEST QO'SHISH":
            user_data['admin_state'] = "cat"
            return await update.message.reply_text("Bo'limni tanlang:\n1. Mat Milliy\n2. Fiz Milliy\n3. Mat DTM\n4. Fiz DTM")
        
        if user_data.get('admin_state') == "cat":
            cats = {"1":"MAT_MILLIY","2":"FIZ_MILLIY","3":"MAT_DTM","4":"FIZ_DTM"}
            if text in cats:
                user_data.update({"tcat": cats[text], "admin_state": "tid"})
                return await update.message.reply_text("Test ID yozing (masalan: M-01):")
        
        elif user_data.get('admin_state') == "tid":
            user_data.update({"ttid": text.upper(), "admin_state": "tfile"})
            return await update.message.reply_text("Endi PDF faylni yuboring:")

        if text == "🔑 KALIT YUKLASH":
            user_data['admin_state'] = "kid"
            return await update.message.reply_text("Qaysi ID uchun kalit yuklaysiz?")
        
        elif user_data.get('admin_state') == "kid":
            user_data.update({"tkid": text.upper(), "admin_state": "kval"})
            return await update.message.reply_text(f"{text.upper()} uchun kalitlarni yuboring (abcd...):")
        
        elif user_data.get('admin_state') == "kval":
            db["answers"][user_data["tkid"]] = re.sub(r'[^a-e]', '', text.lower())
            save_data()
            user_data.clear()
            return await update.message.reply_text("✅ Kalitlar saqlandi!", reply_markup=get_main_keyboard(uid))

    # --- NATIJA TEKSHIRISH ---
    if text == "📊 NATIJA TEKSHIRISH":
        user_data['state'] = 'check_id'
        return await update.message.reply_text("📝 Test ID yozing:", reply_markup=get_back_keyboard())

    if user_data.get('state') == 'check_id':
        tid = text.upper()
        if tid not in db["answers"]: return await update.message.reply_text("❌ ID topilmadi.")
        user_data.update({"ctid": tid, "state": "check_ans"})
        return await update.message.reply_text(f"✅ {tid} topildi. Javoblarni yuboring:")

    if user_data.get('state') == 'check_ans':
        tid = user_data['ctid']
        correct = db["answers"][tid]
        u_ans = re.sub(r'[^a-e]', '', text.lower())
        score = sum(1 for i, char in enumerate(correct) if i < len(u_ans) and u_ans[i] == char)
        user_data.clear()
        return await update.message.reply_text(f"📊 Natija: {score}/{len(correct)}", reply_markup=get_main_keyboard(uid))

    # --- TESTLARNI CHIQARISH ---
    menus = {"🥇 MILLIY SERTIFIKAT (Matematika)": "MAT_MILLIY", "🥇 MILLIY SERTIFIKAT (Fizika)": "FIZ_MILLIY", 
             "🏛️ DTM TESTLAR (Matematika)": "MAT_DTM", "🏛️ DTM TESTLAR (Fizika)": "FIZ_DTM"}
    
    if text in menus:
        target = menus[text]
        av = [t for t, c in db["categories"].items() if c == target]
        if not av: return await update.message.reply_text("⚠️ Testlar yo'q.")
        btns = [[KeyboardButton(t)] for t in av] + [[KeyboardButton("🔙 ASOSIY MENYU")]]
        user_data['state'] = 'choosing'
        return await update.message.reply_text("📑 Tanlang:", reply_markup=ReplyKeyboardMarkup(btns, resize_keyboard=True))

    if user_data.get('state') == 'choosing' and text in db["categories"]:
        path = db["pdfs"].get(text)
        if path and os.path.exists(path):
            with open(path, 'rb') as f:
                await update.message.reply_document(document=f, caption=f"ID: {text}")

async def handle_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID and context.user_data.get('admin_state') == "tfile":
        tid, cat = context.user_data["ttid"], context.user_data["tcat"]
        file = await context.bot.get_file(update.message.document.file_id)
        path = f"{tid}.pdf"
        await file.download_to_drive(path)
        db["pdfs"][tid], db["categories"][tid] = path, cat
        save_data()
        context.user_data.clear()
        await update.message.reply_text("✅ Test muvaffaqiyatli qo'shildi!", reply_markup=get_main_keyboard(ADMIN_ID))

if __name__ == "__main__":
    load_data()
    threading.Thread(target=run, daemon=True).start()
    if TOKEN:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(MessageHandler(filters.Document.PDF, handle_doc))
        app.run_polling(drop_pending_updates=True)
