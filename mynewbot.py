import logging
import os
import re
import json
import threading
from datetime import datetime
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

try:
    import pymongo
except ImportError:
    pymongo = None

# ===== SERVER (Render uchun) =====
server = Flask('')
@server.route('/')
def home(): return "Bot is live! 🚀"

def run():
    port = int(os.environ.get("PORT", 10000))
    server.run(host='0.0.0.0', port=port)

# ===== DATABASE (MongoDB Atlas) =====
MONGO_URL = os.getenv("MONGO_URL") 
db = {"answers": {}, "pdfs": {}, "categories": {}, "users": [], "results": {}}

def save_data():
    with open("data.json", "w") as f:
        json.dump(db, f, indent=4)
    if MONGO_URL and pymongo:
        try:
            client = pymongo.MongoClient(MONGO_URL)
            collection = client["test_arena_db"]["bot_data"]
            collection.update_one({"_id": "main_storage"}, {"$set": db}, upsert=True)
        except Exception as e:
            logging.error(f"Database error: {e}")

def load_data():
    global db
    if MONGO_URL and pymongo:
        try:
            client = pymongo.MongoClient(MONGO_URL)
            data = client["test_arena_db"]["bot_data"].find_one({"_id": "main_storage"})
            if data:
                for k in db.keys():
                    if k in data: db[k] = data[k]
                return
        except: pass
    if os.path.exists("data.json"):
        with open("data.json", "r") as f:
            loaded = json.load(f)
            for k in db.keys():
                if k in loaded: db[k] = loaded[k]

# ===== CONFIG =====
ADMIN_ID = 6257157305
TOKEN = os.getenv("BOT_TOKEN")

# ===== KEYBOARDS =====
def get_main_keyboard(user_id):
    btns = [
        [KeyboardButton("🥇 MILLIY SERTIFIKAT (Matematika)"), KeyboardButton("🥇 MILLIY SERTIFIKAT (Fizika)")],
        [KeyboardButton("🏛️ DTM TESTLAR (Matematika)"), KeyboardButton("🏛️ DTM TESTLAR (Fizika)")],
        [KeyboardButton("📊 NATIJA TIKSHIRISH"), KeyboardButton("📜 MENING NATIJALARIM")],
        [KeyboardButton("👨‍💻 Adminga bog'lanish")]
    ]
    if user_id == ADMIN_ID:
        btns.append([KeyboardButton("➕ TEST QO'SHISH"), KeyboardButton("🔑 KALIT YUKLASH")])
        btns.append([KeyboardButton("👥 STATISTIKA")])
    return ReplyKeyboardMarkup(btns, resize_keyboard=True)

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in db["users"]: db["users"].append(uid)
    save_data()
    await update.message.reply_text("👋 TestArena botiga xush kelibsiz!", reply_markup=get_main_keyboard(int(uid)))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = str(update.effective_user.id)
    user_data = context.user_data

    # 1. HAR DOIM ISHLAYDIGAN TUGMALAR
    if text == "👨‍💻 Adminga bog'lanish":
        await update.message.reply_text("👨‍💻 Admin bilan bog'lanish: @miracle_1204")
        return

    if text == "🔙 ASOSIY MENYU" or text == "🛑 TESTNI YAKUNLASH":
        user_data.clear()
        await update.message.reply_text("🏠 Asosiy menyu:", reply_markup=get_main_keyboard(int(uid)))
        return

    # 2. ADMIN FUNKSIYALARI
    if int(uid) == ADMIN_ID:
        if text == "➕ TEST QO'SHISH":
            user_data['admin_state'] = "cat"
            await update.message.reply_text("Bo'limni tanlang:\n1. Mat Milliy\n2. Fiz Milliy\n3. Mat DTM\n4. Fiz DTM")
            return
        
        if user_data.get('admin_state') == "cat":
            cs = {"1":"MAT_MILLIY","2":"FIZ_MILLIY","3":"MAT_DTM","4":"FIZ_DTM"}
            if text in cs:
                user_data["tcat"], user_data['admin_state'] = cs[text], "tid"
                await update.message.reply_text("Test uchun ID kiriting (Masalan: M-01):")
            return

        if user_data.get('admin_state') == "tid":
            user_data["ttid"], user_data['admin_state'] = text.upper(), "tfile"
            await update.message.reply_text(f"ID: {text.upper()} qabul qilindi. Endi PDF faylni yuboring:")
            return

        if text == "🔑 KALIT YUKLASH":
            user_data['admin_state'] = "kid"
            await update.message.reply_text("Kalit yuklanadigan Test ID-ni yozing:")
            return

        if user_data.get('admin_state') == "kid":
            user_data["tkid"], user_data['admin_state'] = text.upper(), "kval"
            await update.message.reply_text(f"'{text.upper()}' uchun kalitlarni yuboring (masalan: abcd...):")
            return

        if user_data.get('admin_state') == "kval":
            db["answers"][user_data["tkid"]] = re.sub(r'[^a-eA-E]', '', text).lower()
            save_data()
            await update.message.reply_text("✅ Kalitlar muvaffaqiyatli saqlandi!", reply_markup=get_main_keyboard(ADMIN_ID))
            user_data.clear()
            return

        if text == "👥 STATISTIKA":
            await update.message.reply_text(f"👤 Foydalanuvchilar: {len(db['users'])}\n📝 Testlar: {len(db['pdfs'])}")
            return

    # 3. FOYDALANUVCHI FUNKSIYALARI
    if text == "📊 NATIJA TIKSHIRISH":
        user_data['state'] = 'check_id'
        await update.message.reply_text("Test ID-ni yozing:")
        return

    if user_data.get('state') == 'check_id':
        tid = text.upper()
        if tid not in db["answers"]:
            await update.message.reply_text(f"❌ '{tid}' ID topilmadi. Qayta yozing:")
        else:
            user_data['ctid'], user_data['state'] = tid, 'check_ans'
            await update.message.reply_text(f"✅ {tid} topildi. Javoblarni yuboring (masalan: abcd...):")
        return

    if user_data.get('state') == 'check_ans':
        tid = user_data['ctid']
        correct = db["answers"][tid]
        u_ans = re.sub(r'[^a-eA-E]', '', text).lower()
        score, analysis = 0, ""
        for i in range(len(correct)):
            ua = u_ans[i] if i < len(u_ans) else "?"
            ca = correct[i]
            analysis += f"{i+1}. {'✅' if ua == ca else '❌ (Siz: '+ua.upper()+', Aslida: '+ca.upper()+')'}\n"
            if ua == ca: score += 1
        
        perc = (score * 100) // len(correct)
        dt = datetime.now().strftime("%d/%m %H:%M")
        if uid not in db["results"]: db["results"][uid] = []
        db["results"][uid].append({"id": tid, "score": score, "total": len(correct), "percent": perc, "date": dt})
        save_data()
        await update.message.reply_text(f"📊 Natija: {score}/{len(correct)} ({perc}%)\n\n📝 Tahlil:\n{analysis}", reply_markup=get_main_keyboard(int(uid)))
        user_data.clear()
        return

    # TESTLARNI KO'RSATISH
    if "MILLIY" in text or "DTM" in text:
        if "Matematika" in text and "MILLIY" in text: sc = "MAT_MILLIY"
        elif "Fizika" in text and "MILLIY" in text: sc = "FIZ_MILLIY"
        elif "Matematika" in text and "DTM" in text: sc = "MAT_DTM"
        else: sc = "FIZ_DTM"
        
        av = [t for t, c in db["categories"].items() if c == sc]
        if not av:
            await update.message.reply_text("⚠️ Bu bo'limda testlar yo'q.")
            return
        btns = [[KeyboardButton(t)] for t in av]
        btns.append([KeyboardButton("🔙 ASOSIY MENYU")])
        user_data['state'] = 'choosing'
        await update.message.reply_text("📑 Testni tanlang:", reply_markup=ReplyKeyboardMarkup(btns, resize_keyboard=True))
        return

    if user_data.get('state') == 'choosing' and text in db["categories"]:
        path = db["pdfs"].get(text)
        if path and os.path.exists(path):
            await update.message.reply_document(document=open(path, 'rb'), caption=f"ID: {text}", 
                                               reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🛑 TESTNI YAKUNLASH")]], resize_keyboard=True))

async def handle_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID and context.user_data.get('admin_state') == "tfile":
        tid, cat = context.user_data["ttid"], context.user_data["tcat"]
        file = await context.bot.get_file(update.message.document.file_id)
        path = f"{tid}.pdf"
        await file.download_to_drive(path)
        db["pdfs"][tid], db["categories"][tid] = path, cat
        save_data()
        await update.message.reply_text(f"✅ Test {tid} muvaffaqiyatli yuklandi!", reply_markup=get_main_keyboard(ADMIN_ID))
        context.user_data.clear()

if __name__ == "__main__":
    load_data()
    threading.Thread(target=run, daemon=True).start()
    if TOKEN:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(MessageHandler(filters.Document.PDF, handle_doc))
        print("Bot ishlamoqda... 🚀")
        app.run_polling(drop_pending_updates=True)
