import logging
import os
import re
import json
import matplotlib.pyplot as plt
from flask import Flask
from threading import Thread

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ===== SERVER (Render uchun) =====
server = Flask('')

@server.route('/')
def home():
    return "Bot is running!"

def run():
    server.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# ===== CONFIG =====
logging.basicConfig(level=logging.INFO)
ADMIN_ID = 6257157305
TOKEN = os.getenv("BOT_TOKEN")  # Render environment variable orqali

if not TOKEN:
    raise ValueError("BOT_TOKEN topilmadi! Render dashboard orqali qo‘shing.")

# ===== DATA =====
correct_answers = {}
pdf_files = {}
test_category = {}
user_results = {}
admin_state = {}

# ===== SAVE / LOAD =====
def save_data():
    temp = "data_temp.json"
    with open(temp, "w") as f:
        json.dump({
            "answers": correct_answers,
            "pdfs": pdf_files,
            "categories": test_category,
            "user_results": user_results
        }, f, indent=4)
    os.replace(temp, "data.json")

def load_data():
    global correct_answers, pdf_files, test_category, user_results
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r") as f:
                data = json.load(f)
                correct_answers = data.get("answers", {})
                pdf_files = data.get("pdfs", {})
                test_category = data.get("categories", {})
                user_results = data.get("user_results", {})
        except Exception as e:
            print("LOAD ERROR:", e)

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
    context.user_data.clear()
    await update.message.reply_text("Bo‘limni tanlang 👇", reply_markup=get_main_keyboard(update.effective_user.id))

# ===== MAIN HANDLER =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    user_data = context.user_data

    # ===== ADMIN STATES =====
    if user_id == ADMIN_ID and user_id in admin_state:
        state = admin_state[user_id]

        if state == "choose_category":
            categories = {"1": "MAT_MILLIY", "2": "FIZ_MILLIY", "3": "MAT_DTM", "4": "FIZ_DTM"}
            if text in categories:
                user_data["category"] = categories[text]
                admin_state[user_id] = "pdf_id"
                await update.message.reply_text("Test ID yozing:")
            return

        elif state == "pdf_id":
            user_data["pdf_test_id"] = text.upper()
            admin_state[user_id] = "pdf_file"
            await update.message.reply_text("PDF yuboring:")
            return

        elif state == "key_id":
            user_data["key_test_id"] = text.upper()
            admin_state[user_id] = "key_answers"
            await update.message.reply_text("Javoblarni yuboring:")
            return

        elif state == "key_answers":
            test_id = user_data["key_test_id"]
            answers = re.sub(r'[^a-eA-E]', '', text).lower()
            correct_answers[test_id] = answers
            save_data()
            await update.message.reply_text("Kalit saqlandi ✅", reply_markup=get_main_keyboard(user_id))
            del admin_state[user_id]
            return

    # ===== NAVIGATION =====
    if text == "🔙 ASOSIY MENYU":
        user_data.clear()
        await update.message.reply_text("Menu", reply_markup=get_main_keyboard(user_id))
        return

    elif text == "👨‍💻 Adminga bog'lanish":
        await update.message.reply_text("Admin: @miracle_1204")
        return

    elif text == "📊 NATIJA CHIQARISH":
        user_data['state'] = 'enter_test_id'
        await update.message.reply_text("Test ID kiriting:")
        return

    elif text == "➕ TEST QO‘SHISH" and user_id == ADMIN_ID:
        admin_state[user_id] = "choose_category"
        await update.message.reply_text("1-Mat Milliy\n2-Fiz Milliy\n3-Mat DTM\n4-Fiz DTM")
        return

    elif text == "🔑 KALIT YUKLASH" and user_id == ADMIN_ID:
        admin_state[user_id] = "key_id"
        await update.message.reply_text("Test ID kiriting:")
        return

    # ===== CATEGORY SELECTION =====
    if "Matematika" in text or "Fizika" in text:
        if "Matematika" in text and "MILLIY" in text: sel_cat="MAT_MILLIY"
        elif "Fizika" in text and "MILLIY" in text: sel_cat="FIZ_MILLIY"
        elif "Matematika" in text and "DTM" in text: sel_cat="MAT_DTM"
        else: sel_cat="FIZ_DTM"

        available = [tid for tid, cat in test_category.items() if cat == sel_cat]

        if not available:
            await update.message.reply_text("Test yo‘q ❌")
            return

        buttons = [[KeyboardButton(t)] for t in available]
        buttons.append([KeyboardButton("🔙 ASOSIY MENYU")])

        user_data['state'] = 'choosing_test'
        user_data['current_category'] = sel_cat

        await update.message.reply_text("Testni tanlang:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return

    # ===== TEST TANLASH =====
    if user_data.get('state') == 'choosing_test':
        if text in test_category:
            user_data['selected_test_id'] = text
            user_data['state'] = 'waiting_test'
            await update.message.reply_text(f"{text} tanlandi", reply_markup=start_test_menu())
        return

    # ===== START TEST =====
    if text == "🚀 Testni boshlash" and user_data.get('state') == 'waiting_test':
        tid = user_data['selected_test_id']
        fpath = pdf_files.get(tid)
        if fpath and os.path.exists(fpath):
            await update.message.reply_document(open(fpath, 'rb'))
            user_data['state'] = 'solving'
        return

    if text == "❌ Testni to'xtatish":
        user_data.clear()
        await update.message.reply_text("Test to‘xtatildi", reply_markup=get_main_keyboard(user_id))
        return

    # ===== TEST CHECK =====
    if user_data.get('state') == 'solving':
        test_id = user_data['selected_test_id']
        correct_key = correct_answers.get(test_id)
        user_ans = re.sub(r'[^a-eA-E]', '', text).lower()

        correct_count = 0
        wrong = []

        for i, (u, c) in enumerate(zip(user_ans, correct_key), start=1):
            if u == c:
                correct_count += 1
            else:
                wrong.append(f"{i}) Siz:{u.upper()} | To‘g‘ri:{c.upper()}")

        percent = (correct_count * 100) // len(correct_key)

        msg = f"Natija {test_id}\n{correct_count}/{len(correct_key)} ({percent}%)\n"
        if wrong:
            msg += "\n❌ Xatolar:\n" + "\n".join(wrong[:10])
        else:
            msg += "\n🎉 Hammasi to‘g‘ri!"

        await update.message.reply_text(msg, reply_markup=get_main_keyboard(user_id))
        user_data.clear()
        return

    # ===== RESULT CHECK (ID) =====
    if user_data.get('state') == 'enter_test_id':
        tid = text.upper()
        if tid not in correct_answers:
            await update.message.reply_text("Topilmadi ❌")
            return
        user_data['check_test_id'] = tid
        user_data['state'] = 'enter_answers'
        await update.message.reply_text("Javoblarni yubor:")
        return

    if user_data.get('state') == 'enter_answers':
        test_id = user_data['check_test_id']
        correct_key = correct_answers.get(test_id)
        user_ans = re.sub(r'[^a-eA-E]', '', text).lower()

        correct_count = 0
        wrong = []

        for i, (u, c) in enumerate(zip(user_ans, correct_key), start=1):
            if u == c:
                correct_count += 1
            else:
                wrong.append(f"{i}) Siz:{u.upper()} | To‘g‘ri:{c.upper()}")

        percent = (correct_count * 100) // len(correct_key)

        msg = f"Natija {test_id}\n{correct_count}/{len(correct_key)} ({percent}%)\n"
        if wrong:
            msg += "\n❌ Xatolar:\n" + "\n".join(wrong[:10])

        await update.message.reply_text(msg, reply_markup=get_main_keyboard(user_id))
        user_data.clear()
        return

# ===== PDF UPLOAD =====
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_ID and admin_state.get(user_id) == "pdf_file":
        doc = update.message.document
        test_id = context.user_data["pdf_test_id"]
        category = context.user_data["category"]

        fname = f"{test_id}.pdf"
        file = await context.bot.get_file(doc.file_id)
        await file.download_to_drive(fname)

        pdf_files[test_id] = fname
        test_category[test_id] = category
        save_data()

        await update.message.reply_text("PDF saqlandi ✅")
        del admin_state[user_id]

# ===== RUN =====
if __name__ == "__main__":
    load_data()
    keep_alive()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_document))

    print("Bot ishga tushdi 🚀")
    app.run_polling()
