import logging
import os
import re
import json
import asyncio
import threading
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ===== RENDER UCHUN WEB SERVER (Port 10000) =====
# Render o'chib qolmasligi uchun bu qism shart
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    # Render aynan 10000 portni band qilishni talab qiladi
    flask_app.run(host='0.0.0.0', port=10000)

# ===== LOGGING VA TOKEN =====
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
ADMIN_ID = 6257157305
TOKEN = os.getenv("BOT_TOKEN") # Render Settings'dagi o'zgaruvchi

# ===== DATA STORAGE =====
correct_answers = {}
pdf_files = {}
test_category = {}
user_results = {}
all_users = set()
user_answers_storage = {}
admin_state = {}

# ===== SAVE / LOAD =====
def save_data():
    try:
        data = {
            "answers": correct_answers,
            "pdfs": pdf_files,
            "categories": test_category,
            "user_results": user_results,
            "all_users": list(all_users),
            "user_answers_storage": user_answers_storage
        }
        with open("data.json", "w") as f:
            json.dump(data, f)
    except Exception as e:
        logging.error(f"Saqlashda xato: {e}")

def load_data():
    global correct_answers, pdf_files, test_category, user_results, all_users, user_answers_storage
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r") as f:
                data = json.load(f)
                correct_answers = data.get("answers", {})
                pdf_files = data.get("pdfs", {})
                test_category = data.get("categories", {})
                user_results = data.get("user_results", {})
                all_users = set(data.get("all_users", []))
                user_answers_storage = data.get("user_answers_storage", {})
        except Exception as e:
            logging.error(f"Yuklashda xato: {e}")

# ===== KEYBOARDS =====
def get_main_keyboard(user_id):
    buttons = [
        [KeyboardButton("🏅 MILLIY SERTIFIKAT (Matematika)"), KeyboardButton("🏅 MILLIY SERTIFIKAT (Fizika)")],
        [KeyboardButton("🏛️ DTM TESTLAR (Matematika)"), KeyboardButton("🏛️ DTM TESTLAR (Fizika)")],
        [KeyboardButton("📊 NATIJA CHIQARISH")],
        [KeyboardButton("👨‍💻 Adminga bog'lanish")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton("➕ TEST QO‘SHISH"), KeyboardButton("🔑 KALIT YUKLASH")])
        buttons.append([KeyboardButton("👤 FOYDALANUVCHILAR")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def start_test_menu():
    return ReplyKeyboardMarkup([[KeyboardButton("🚀 Testni boshlash")],[KeyboardButton("🔙 ASOSIY MENYU")]], resize_keyboard=True)

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in all_users:
        all_users.add(user_id)
        save_data()
    context.user_data.clear()
    await update.message.reply_text("👋 Assalomu alaykum! Bo'limni tanlang 👇", reply_markup=get_main_keyboard(user_id))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    user_data = context.user_data

    # --- ADMIN: FOYDALANUVCHILAR ---
    if text == "👤 FOYDALANUVCHILAR" and user_id == ADMIN_ID:
        count = len(all_users)
        await update.message.reply_text(f"👤 Jami foydalanuvchilar: {count} ta")
        return

    # --- NATIJA ---
    if text == "📊 NATIJA CHIQARISH":
        user_data['state'] = 'checking_result'
        await update.message.reply_text("🔍 Natijani bilish uchun Test ID raqamini yuboring:")
        return

    if user_data.get('state') == 'checking_result':
        test_id = text.strip()
        uid = str(user_id)
        if uid not in user_answers_storage or test_id not in user_answers_storage[uid]:
            await update.message.reply_text(f"❌ Siz hali {test_id} ID-li testga javob bermagansiz.")
        else:
            correct_key = correct_answers.get(test_id)
            if not correct_key:
                await update.message.reply_text("❗ Bu test uchun kalit yuklanmagan.")
            else:
                u_ans = user_answers_storage[uid][test_id]
                correct_count = sum(1 for u, c in zip(u_ans, correct_key) if u == c)
                percent = (correct_count * 100) // len(correct_key)
                await update.message.reply_text(f"🎯 Natija:\n🆔 Test ID: {test_id}\n✅ To'g'ri: {correct_count}/{len(correct_key)}\n📈 Foiz: {percent}%")
        user_data.clear()
        return

    # --- ADMIN FUNKSIYALARI ---
    if user_id == ADMIN_ID and user_id in admin_state:
        state = admin_state[user_id]
        if state == "choose_category":
            cats = {"1": "MAT_MILLIY", "2": "FIZ_MILLIY", "3": "MAT_DTM", "4": "FIZ_DTM"}
            if text in cats:
                user_data["category"] = cats[text]
                admin_state[user_id] = "pdf_id"
                await update.message.reply_text("🆔 Test uchun yangi ID yozing:")
            return
        elif state == "pdf_id":
            user_data["pdf_test_id"] = text
            admin_state[user_id] = "pdf_file"
            await update.message.reply_text("📄 PDF faylni yuboring:")
            return
        elif state == "key_id":
            user_data["key_test_id"] = text
            admin_state[user_id] = "key_answers"
            await update.message.reply_text("✍️ Kalitlarni yuboring (abcd...):")
            return
        elif state == "key_answers":
            tid = user_data["key_test_id"]
            ans = re.sub(r'[^a-zA-Z]', '', text).lower()
            correct_answers[tid] = ans
            save_data()
            await update.message.reply_text(f"✅ Kalit saqlandi! ID: {tid}")
            del admin_state[user_id]
            return

    # --- NAVIGATION ---
    if text == "🔙 ASOSIY MENYU":
        user_data.clear()
        await update.message.reply_text("🏠 Asosiy menu:", reply_markup=get_main_keyboard(user_id))
    elif text == "➕ TEST QO‘SHISH" and user_id == ADMIN_ID:
        admin_state[user_id] = "choose_category"
        await update.message.reply_text("Bo'limni tanlang:\n1.Mat Milliy\n2.Fiz Milliy\n3.Mat DTM\n4.Fiz DTM")
    elif text == "🔑 KALIT YUKLASH" and user_id == ADMIN_ID:
        admin_state[user_id] = "key_id"
        await update.message.reply_text("Test ID raqamini yozing:")
    elif text == "👨‍💻 Adminga bog'lanish":
        await update.message.reply_text("Savollar bo'yicha: @miracle_0023")

    # --- TESTLAR ---
    if "MILLIY" in text or "DTM" in text:
        sel_cat = ""
        if "Matematika" in text and "MILLIY" in text: sel_cat="MAT_MILLIY"
        elif "Fizika" in text and "MILLIY" in text: sel_cat="FIZ_MILLIY"
        elif "Matematika" in text and "DTM" in text: sel_cat="MAT_DTM"
        elif "Fizika" in text and "DTM" in text: sel_cat="FIZ_DTM"
        
        available = [tid for tid, cat in test_category.items() if cat == sel_cat]
        if not available:
            await update.message.reply_text("⚠️ Bu bo'limda test hozircha yo'q.")
            return
        user_data['selected_test_id'] = available[0]
        user_data['state'] = 'waiting_test'
        await update.message.reply_text(f"💎 Test topildi: {available[0]}", reply_markup=start_test_menu())

    elif text == "🚀 Testni boshlash" and user_data.get('state') == 'waiting_test':
        tid = user_data.get('selected_test_id')
        path = pdf_files.get(tid)
        if tid and path and os.path.exists(path):
            await update.message.reply_document(document=open(path, 'rb'), caption=f"📝 Test ID: {tid}", reply_markup=start_test_menu())
            user_data['state'] = 'solving'
        else:
            await update.message.reply_text("❌ Xato: PDF fayl topilmadi.")

    elif user_data.get('state') == 'solving':
        tid = user_data.get('selected_test_id')
        ans = re.sub(r'[^a-zA-Z]', '', text).lower()
        uid = str(user_id)
        if uid not in user_answers_storage: user_answers_storage[uid] = {}
        user_answers_storage[uid][tid] = ans
        save_data()
        await update.message.reply_text(f"✅ Javoblar qabul qilindi!", reply_markup=get_main_keyboard(user_id))
        user_data.clear()

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_ID and admin_state.get(user_id) == "pdf_file":
        doc = update.message.document
        tid = context.user_data["pdf_test_id"]
        cat = context.user_data["category"]
        fname = f"{tid}.pdf"
        file = await context.bot.get_file(doc.file_id)
        await file.download_to_drive(fname)
        pdf_files[tid], test_category[tid] = fname, cat
        save_data()
        await update.message.reply_text(f"✅ PDF saqlandi: {tid}")
        del admin_state[user_id]

# ===== ASOSIY RUN QISMI =====
if __name__ == "__main__":
    load_data()
    
    # Render uyg'oq turishi uchun Flask
    threading.Thread(target=run_flask, daemon=True).start()
    
    if not TOKEN:
        logging.error("❌ BOT_TOKEN TOPILMADI!")
    else:
        # Yangi ApplicationBuilder (v20+)
        application = ApplicationBuilder().token(TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(MessageHandler(filters.Document.PDF, handle_document))
        
        logging.info("Bot ishga tushdi...")
        application.run_polling()
