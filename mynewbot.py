import logging
import os
import re
import json
import asyncio
import matplotlib.pyplot as plt
from flask import Flask
from threading import Thread

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ===== RENDER UCHUN ODDIY SERVER =====
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
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
ADMIN_ID = 6257157305
TOKEN = "8670442749:AAGNOJpvObU5RhFHd2LEfeCNaVgpiqyRGxE"

# ===== DATA =====
correct_answers = {}
pdf_files = {}
test_category = {}
user_results = {}
admin_state = {}

# ===== SAVE / LOAD =====
def save_data():
    with open("data.json", "w") as f:
        json.dump({
            "answers": correct_answers,
            "pdfs": pdf_files,
            "categories": test_category,
            "user_results": user_results
        }, f)

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
        except:
            pass

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
    return ReplyKeyboardMarkup([[KeyboardButton("🚀 Testni boshlash")],[KeyboardButton("❌ Testni to'xtatish")],[KeyboardButton("🔙 ASOSIY MENYU")]], resize_keyboard=True)

# ===== GRAPH =====
def generate_graph(user_id):
    results = user_results.get(str(user_id), [])
    if not results:
        return None
    results = results[-10:]
    tests = [r["test_id"] for r in results]
    percents = [r["percent"] for r in results]

    plt.figure(figsize=(8,4))
    plt.bar(tests, percents, color='#4CAF50', alpha=0.7)
    plt.ylim(0,100)
    plt.xlabel("Testlar")
    plt.ylabel("Foiz (%)")
    plt.title("📊 Sizning progress")
    plt.xticks(rotation=45)
    for i, v in enumerate(percents):
        plt.text(i, v + 1, f"{v}%", ha='center', fontweight='bold')
    plt.tight_layout()
    filename = f"graph_{user_id}.png"
    plt.savefig(filename)
    plt.close()
    return filename

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.clear()
    await update.message.reply_text("Assalomu alaykum! Bo‘limni tanlang 👇", reply_markup=get_main_keyboard(user_id))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    user_data = context.user_data

    # --- ADMIN STATES ---
    if user_id == ADMIN_ID and user_id in admin_state:
        state = admin_state[user_id]
        if state == "choose_category":
            categories = {"1": "MAT_MILLIY", "2": "FIZ_MILLIY", "3": "MAT_DTM", "4": "FIZ_DTM"}
            if text in categories:
                user_data["category"] = categories[text]
                admin_state[user_id] = "pdf_id"
                await update.message.reply_text("🆔 Test uchun yangi ID yozing (masalan: MATH01):")
            return
        elif state == "pdf_id":
            user_data["pdf_test_id"] = text.upper()
            admin_state[user_id] = "pdf_file"
            await update.message.reply_text(f"📄 {text.upper()} uchun PDF yuboring:")
            return
        elif state == "key_id":
            user_data["key_test_id"] = text.upper()
            admin_state[user_id] = "key_answers"
            await update.message.reply_text(f"✍️ {text.upper()} uchun javoblarni yuboring (abcd...):")
            return
        elif state == "key_answers":
            test_id = user_data["key_test_id"]
            answers = re.sub(r'[^a-eA-E]', '', text).lower()
            correct_answers[test_id] = answers
            save_data()
            await update.message.reply_text(f"✅ Kalit saqlandi!\n🆔 ID: {test_id}\nJavoblar: {answers}", reply_markup=get_main_keyboard(user_id))
            del admin_state[user_id]
            return

    # --- MENU NAVIGATION ---
    if text == "🔙 ASOSIY MENYU":
        user_data.clear()
        await update.message.reply_text("🏠 Asosiy menu:", reply_markup=get_main_keyboard(user_id))
        return
    elif text == "➕ TEST QO‘SHISH" and user_id == ADMIN_ID:
        admin_state[user_id] = "choose_category"
        await update.message.reply_text("Kategoriyani tanlang:\n1. Mat Milliy\n2. Fiz Milliy\n3. Mat DTM\n4. Fiz DTM")
        return
    elif text == "🔑 KALIT YUKLASH" and user_id == ADMIN_ID:
        admin_state[user_id] = "key_id"
        await update.message.reply_text("Qaysi Test ID uchun kalit yuklaysiz?")
        return
    elif text == "📊 NATIJA CHIQARISH":
        graph = generate_graph(user_id)
        if graph:
            await update.message.reply_photo(photo=open(graph, 'rb'), caption="Sizning oxirgi natijalaringiz progressi")
            os.remove(graph)
        else:
            await update.message.reply_text("Hali natijalar mavjud emas.")
        return

    # --- CATEGORY SELECTION ---
    if "Matematika" in text or "Fizika" in text:
        sel_cat = ""
        if "Matematika" in text and "MILLIY" in text: sel_cat="MAT_MILLIY"
        elif "Fizika" in text and "MILLIY" in text: sel_cat="FIZ_MILLIY"
        elif "Matematika" in text and "DTM" in text: sel_cat="MAT_DTM"
        elif "Fizika" in text and "DTM" in text: sel_cat="FIZ_DTM"
        
        available = [tid for tid, cat in test_category.items() if cat == sel_cat]
        if not available:
            await update.message.reply_text("⚠️ Bu bo'limda hozircha testlar yo'q.")
            return
        user_data['selected_test_id'] = available[0]
        user_data['state'] = 'waiting_test'
        await update.message.reply_text(f"📚 Test topildi: {available[0]}\nBoshlaymizmi?", reply_markup=start_test_menu())
        return

    elif text == "🚀 Testni boshlash" and user_data.get('state') == 'waiting_test':
        test_id = user_data.get('selected_test_id')
        fpath = pdf_files.get(test_id)
        if fpath and os.path.exists(fpath):
            await update.message.reply_document(document=open(fpath, 'rb'), caption=f"ID: {test_id}\nJavoblarni ketma-ket yuboring (masalan: abcd...)")
            user_data['state'] = 'solving'
        else:
            await update.message.reply_text("❌ PDF fayl topilmadi.")
        return

    # --- CHECKING ANSWERS ---
    if user_data.get('state') == 'solving':
        test_id = user_data.get('selected_test_id')
        correct_key = correct_answers.get(test_id)
        user_ans = re.sub(r'[^a-eA-E]', '', text).lower()
        
        if not correct_key:
            await update.message.reply_text("Tizimda bu test uchun kalit topilmadi.")
            return

        correct_count = sum(1 for u, c in zip(user_ans, correct_key) if u == c)
        percent = (correct_count * 100) // len(correct_key)
        
        # Save results
        uid = str(user_id)
        if uid not in user_results: user_results[uid] = []
        user_results[uid].append({"test_id": test_id, "score": correct_count, "total": len(correct_key), "percent": percent})
        save_data()

        await update.message.reply_text(
            f"🎯 Natija: {test_id}\n✅ To'g'ri: {correct_count}/{len(correct_key)}\n📈 Foiz: {percent}%",
            reply_markup=get_main_keyboard(user_id)
        )
        user_data.clear()
        return

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
        await update.message.reply_text(f"✅ PDF yuklandi: {test_id}\nEndi kalit yuklashingiz mumkin.")
        del admin_state[user_id]

# ===== RUN =====
if __name__ == "__main__":
    load_data()
    keep_alive() # Render serverini yoqish
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_document))
    print("🚀 Bot ishga tushdi...")
    app.run_polling()
