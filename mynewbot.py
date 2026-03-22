import logging
import os
import re
import json
import asyncio
import matplotlib.pyplot as plt

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ===== CONFIG =====
ADMIN_ID = 6257157305
TOKEN = "8670442749:AAE1zOey6D2Pf2WwrXOI2-sWxushdR0-CrY"

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
        with open("data.json", "r") as f:
            data = json.load(f)
            correct_answers = data.get("answers", {})
            pdf_files = data.get("pdfs", {})
            test_category = data.get("categories", {})
            user_results = data.get("user_results", {})

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

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.clear()
    await update.message.reply_text("Assalomu alaykum! Bo‘limni tanlang 👇", reply_markup=get_main_keyboard(user_id))

# ===== HANDLE MESSAGE =====
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
                await update.message.reply_text("🆔 Test ID yoz:")
            return
        elif state == "pdf_id":
            user_data["pdf_test_id"] = text
            admin_state[user_id] = "pdf_file"
            await update.message.reply_text("📄 PDF yubor:")
            return
        elif state == "key_id":
            user_data["key_test_id"] = text
            admin_state[user_id] = "key_answers"
            await update.message.reply_text("✍️ Kalit yubor:")
            return
        elif state == "key_answers":
            test_id = user_data["key_test_id"]
            answers = re.sub(r'[^a-zA-Z]', '', text).lower()
            correct_answers[test_id] = answers
            save_data()
            await update.message.reply_text(f"✅ Answer key saqlandi!\n🆔 Test ID: {test_id}\nJavoblar: {answers}")
            del admin_state[user_id]
            return

    # ===== MENU =====
    if text == "🔙 ASOSIY MENYU":
        user_data.clear()
        await update.message.reply_text("🏠 Menu:", reply_markup=get_main_keyboard(user_id))
        return
    elif text == "➕ TEST QO‘SHISH" and user_id == ADMIN_ID:
        admin_state[user_id] = "choose_category"
        await update.message.reply_text("1.Mat 2.Fiz 3.MatDTM 4.FizDTM")
        return
    elif text == "🔑 KALIT YUKLASH" and user_id == ADMIN_ID:
        admin_state[user_id] = "key_id"
        await update.message.reply_text("Test ID yubor:")
        return
    elif text in ["🏅 MILLIY SERTIFIKAT (Matematika)","🏅 MILLIY SERTIFIKAT (Fizika)","🏛️ DTM TESTLAR (Matematika)","🏛️ DTM TESTLAR (Fizika)"]:
        selected_category = ""
        if "Matematika" in text and "MILLIY" in text: selected_category="MAT_MILLIY"
        elif "Fizika" in text and "MILLIY" in text: selected_category="FIZ_MILLIY"
        elif "Matematika" in text and "DTM" in text: selected_category="MAT_DTM"
        elif "Fizika" in text and "DTM" in text: selected_category="FIZ_DTM"
        available_tests = [tid for tid, cat in test_category.items() if cat==selected_category]
        if not available_tests:
            await update.message.reply_text("⚠️ Bu bo‘limda test hali yo‘q")
            return
        user_data['selected_test_id']=available_tests[0]
        await update.message.reply_text("Testni boshlash?", reply_markup=start_test_menu())
        user_data['state']='waiting_test'
        return
    elif text == "🚀 Testni boshlash" and user_data.get('state')=='waiting_test':
        test_id = user_data.get('selected_test_id')
        file_path = pdf_files.get(test_id)
        if test_id and file_path and os.path.exists(file_path):
            await update.message.reply_document(document=open(file_path,'rb'), caption="Test ishlashga tayyor.{test_id}", reply_markup=start_test_menu())
            user_data['state']='solving'
        else:
            await update.message.reply_text("❌ Test topilmadi")
        return
    elif text == "❌ Testni to'xtatish" and user_data.get('state')=='solving':
        user_data.clear()
        await update.message.reply_text("Bekor qilindi", reply_markup=get_main_keyboard(user_id))
        return

    # ===== TEKSHIRISH =====
    if user_data.get('state')=='solving':
        test_id = user_data.get('selected_test_id')
        correct_key = correct_answers.get(test_id)
        user_answers = re.sub(r'[^a-zA-Z]', '', text).lower()
        if not correct_key:
            await update.message.reply_text("❗ Bu test uchun kalit yo‘q")
            return
        wrong = []
        correct_count=0
        for i,(u,c) in enumerate(zip(user_answers,correct_key),1):
            if u==c: correct_count+=1
            else: wrong.append(i)
        percent = (correct_count*100)//len(correct_key)
        # Save result
        uid = str(user_id)
        if uid not in user_results: user_results[uid]=[]
        user_results[uid].append({"test_id":test_id,"score":correct_count,"total":len(correct_key),"percent":percent})
        save_data()
        wrong_questions = ', '.join(map(str, wrong)) if wrong else "Yo‘q"
        await update.message.reply_text(f"🎯 Test natijasi\n🆔 Test ID: {test_id}\n✅ To‘g‘ri: {correct_count}/{len(correct_key)}\n📈 Foiz: {percent}%\n❌ Xato: {wrong_questions}", reply_markup=start_test_menu())
        user_data.clear()
        return

# ===== HANDLE DOCUMENT =====
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_ID and admin_state.get(user_id)=="pdf_file":
        doc = update.message.document
        test_id = context.user_data["pdf_test_id"]
        category = context.user_data["category"]
        fname = f"{test_id}.pdf"
        file = await context.bot.get_file(doc.file_id)
        asyncio.create_task(file.download_to_drive(fname))
        pdf_files[test_id] = fname
        test_category[test_id] = category
        save_data()
        await update.message.reply_text(f"✅ PDF saqlandi!\n🆔 Test ID: {test_id}\n📂 Bo‘lim: {category}\nEndi kalit yuklashingiz mumkin")
        del admin_state[user_id]

# ===== RUN =====
if __name__=="__main__":
    load_data()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_document))
    app.run_polling()