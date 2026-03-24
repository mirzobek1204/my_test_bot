import logging
import os
import re
import json
import threading
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ===== SERVER (Render uchun 10000-port) =====
server = Flask('')

@server.route('/')
def home():
    return "Bot is running!"

def run():
    # Render aynan 10000-portni talab qiladi
    port = int(os.environ.get("PORT", 10000))
    server.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run)
    t.daemon = True
    t.start()

# ===== CONFIG =====
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
ADMIN_ID = 6257157305
TOKEN = os.getenv("BOT_TOKEN") 

if not TOKEN:
    print("XATO: BOT_TOKEN topilmadi! Render dashboard orqali qo‘shing.")

# ===== DATA STORAGE =====
# Lug'atlarni global miqyosda e'lon qilamiz
correct_answers = {}
pdf_files = {}
test_category = {}
user_results = {}
admin_state = {}

def save_data():
    try:
        data = {
            "answers": correct_answers,
            "pdfs": pdf_files,
            "categories": test_category,
            "user_results": user_results
        }
        with open("data.json", "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logging.error(f"Saqlashda xato: {e}")

def load_data():
    global correct_answers, pdf_files, test_category, user_results
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r") as f:
                data = json.load(f)
                correct_answers.update(data.get("answers", {}))
                pdf_files.update(data.get("pdfs", {}))
                test_category.update(data.get("categories", {}))
                user_results.update(data.get("user_results", {}))
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
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def start_test_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🚀 Testni boshlash")],
        [KeyboardButton("❌ Testni to'xtatish")],
        [KeyboardButton("🔙 ASOSIY MENYU")]
    ], resize_keyboard=True)

# ===== START COMMAND =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.clear()
    await update.message.reply_text("👋 Assalomu alaykum! Bo‘limni tanlang 👇", reply_markup=get_main_keyboard(user_id))

# ===== MAIN HANDLER =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    user_data = context.user_data

    # --- ADMIN: TEST VA KALIT YUKLASH ---
    if user_id == ADMIN_ID and user_id in admin_state:
        state = admin_state[user_id]

        if state == "choose_category":
            cats = {"1": "MAT_MILLIY", "2": "FIZ_MILLIY", "3": "MAT_DTM", "4": "FIZ_DTM"}
            if text in cats:
                user_data["category"] = cats[text]
                admin_state[user_id] = "pdf_id"
                await update.message.reply_text("Test uchun yangi ID raqam yozing:")
            return

        elif state == "pdf_id":
            user_data["pdf_test_id"] = text.upper()
            admin_state[user_id] = "pdf_file"
            await update.message.reply_text("📄 Endi PDF faylni yuboring:")
            return

        elif state == "key_id":
            user_data["key_test_id"] = text.upper()
            admin_state[user_id] = "key_answers"
            await update.message.reply_text("✍️ Kalitlarni yuboring (masalan: abcd...):")
            return

        elif state == "key_answers":
            tid = user_data["key_test_id"]
            ans = re.sub(r'[^a-eA-E]', '', text).lower()
            correct_answers[tid] = ans
            save_data()
            await update.message.reply_text(f"✅ Kalit saqlandi! ID: {tid}", reply_markup=get_main_keyboard(user_id))
            del admin_state[user_id]
            return

    # --- NAVIGATION ---
    if text == "🔙 ASOSIY MENYU":
        user_data.clear()
        await update.message.reply_text("🏠 Bosh menyu:", reply_markup=get_main_keyboard(user_id))
        return

    elif text == "➕ TEST QO‘SHISH" and user_id == ADMIN_ID:
        admin_state[user_id] = "choose_category"
        await update.message.reply_text("Bo'limni tanlang:\n1-Mat Milliy\n2-Fiz Milliy\n3-Mat DTM\n4-Fiz DTM")
        return

    elif text == "🔑 KALIT YUKLASH" and user_id == ADMIN_ID:
        admin_state[user_id] = "key_id"
        await update.message.reply_text("Kalit yuklanadigan Test ID raqamini yozing:")
        return

    # --- CATEGORY SELECTION ---
    if "Matematika" in text or "Fizika" in text:
        if "Matematika" in text and "MILLIY" in text: sel_cat="MAT_MILLIY"
        elif "Fizika" in text and "MILLIY" in text: sel_cat="FIZ_MILLIY"
        elif "Matematika" in text and "DTM" in text: sel_cat="MAT_DTM"
        else: sel_cat="FIZ_DTM"

        available = [tid for tid, cat in test_category.items() if cat == sel_cat]
        if not available:
            await update.message.reply_text("⚠️ Hozircha bu bo'limda testlar yo'q.")
            return

        buttons = [[KeyboardButton(t)] for t in available]
        buttons.append([KeyboardButton("🔙 ASOSIY MENYU")])
        user_data['state'] = 'choosing_test'
        await update.message.reply_text("📑 Testni tanlang:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return

    # --- TEST TANLASH VA BOSHLASH ---
    if user_data.get('state') == 'choosing_test':
        if text in test_category:
            user_data['selected_test_id'] = text
            user_data['state'] = 'waiting_test'
            await update.message.reply_text(f"💎 Tanlandi: {text}", reply_markup=start_test_menu())
        return

    if text == "🚀 Testni boshlash" and user_data.get('state') == 'waiting_test':
        tid = user_data['selected_test_id']
        path = pdf_files.get(tid)
        if path and os.path.exists(path):
            await update.message.reply_document(document=open(path, 'rb'), caption=f"📝 Test ID: {tid}")
            user_data['state'] = 'solving'
        return

    # --- NATIJA HISOBLASH ---
    if user_data.get('state') == 'solving':
        tid = user_data['selected_test_id']
        correct_key = correct_answers.get(tid)
        if not correct_key:
            await update.message.reply_text("❗ Bu test uchun kalitlar hali yuklanmagan.")
            return
            
        user_ans = re.sub(r'[^a-eA-E]', '', text).lower()
        correct_count = sum(1 for u, c in zip(user_ans, correct_key) if u == c)
        total = len(correct_key)
        percent = (correct_count * 100) // total

        msg = f"📊 Natija: {tid}\n✅ To'g'ri: {correct_count}/{total}\n📈 Foiz: {percent}%"
        await update.message.reply_text(msg, reply_markup=get_main_keyboard(user_id))
        user_data.clear()
        return

    # NATIJA CHIQARISH (ID orqali)
    if text == "📊 NATIJA CHIQARISH":
        user_data['state'] = 'enter_test_id'
        await update.message.reply_text("Natijani bilish uchun Test ID yuboring:")
        return

# ===== PDF UPLOAD (ADMIN) =====
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_ID and admin_state.get(user_id) == "pdf_file":
        doc = update.message.document
        test_id = context.user_data["pdf_test_id"]
        category = context.user_data["category"]

        fname = f"{test_id}.pdf"
        file = await context.bot.get_file(doc.file_id)
        # v20+ da download_to_drive o'rniga download_to_drive ishlatiladi
        await file.download_to_drive(fname)

        pdf_files[test_id] = fname
        test_category[test_id] = category
        save_data()

        await update.message.reply_text(f"✅ PDF saqlandi! ID: {test_id}", reply_markup=get_main_keyboard(user_id))
        del admin_state[user_id]

# ===== RUN =====
if __name__ == "__main__":
    load_data()
    keep_alive() # Render uchun Flaskni yoqish
    
    if TOKEN:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(MessageHandler(filters.Document.PDF, handle_document))
        
        print("Bot ishlamoqda... 🚀")
        app.run_polling(drop_pending_updates=True)
