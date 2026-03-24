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
    # Render portni muhit o'zgaruvchisidan oladi
    port = int(os.environ.get("PORT", 10000))
    server.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run)
    t.daemon = True
    t.start()

# ===== CONFIG =====
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
ADMIN_ID = 6257157305
TOKEN = os.getenv("BOT_TOKEN")

# ===== DATA STORAGE =====
db = {
    "answers": {},
    "pdfs": {},
    "categories": {},
    "users": [],
    "results": {}
}

def save_data():
    try:
        with open("data.json", "w") as f:
            json.dump(db, f, indent=4)
    except Exception as e:
        logging.error(f"Saqlashda xato: {e}")

def load_data():
    global db
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r") as f:
                loaded_data = json.load(f)
                # Faqat mavjud kalitlarni yangilaymiz
                for key in db.keys():
                    if key in loaded_data:
                        db[key] = loaded_data[key]
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
    # Faqat admin uchun maxsus bo'limlar
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton("➕ TEST QO‘SHISH"), KeyboardButton("🔑 KALIT YUKLASH")])
        buttons.append([KeyboardButton("👥 STATISTIKA")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def start_test_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🚀 Testni boshlash")],
        [KeyboardButton("🔙 ASOSIY MENYU")]
    ], resize_keyboard=True)

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Foydalanuvchini statistikaga qo'shish
    if user_id not in db["users"]:
        db["users"].append(user_id)
        save_data()
    
    context.user_data.clear()
    await update.message.reply_text(
        "👋 Assalomu alaykum! Botga xush kelibsiz.\nBo‘limni tanlang 👇", 
        reply_markup=get_main_keyboard(user_id)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    user_data = context.user_data

    # 1. ASOSIY NAVIGATSIYA
    if text == "🔙 ASOSIY MENYU":
        user_data.clear()
        await update.message.reply_text("🏠 Asosiy menyu:", reply_markup=get_main_keyboard(user_id))
        return

    elif text == "👨‍💻 Adminga bog'lanish":
        await update.message.reply_text("👨‍💻 Admin bilan bog'lanish: @miracle_1204")
        return

    # 2. ADMIN BO'LIMI (Faqat ADMIN_ID uchun)
    if user_id == ADMIN_ID:
        if text == "👥 STATISTIKA":
            u_count = len(db["users"])
            t_count = len(db["pdfs"])
            await update.message.reply_text(
                f"📊 **BOT STATISTIKASI**\n\n👤 Foydalanuvchilar: {u_count} ta\n📝 Yuklangan testlar: {t_count} ta",
                parse_mode='Markdown'
            )
            return

        if text == "➕ TEST QO‘SHISH":
            user_data['admin_state'] = "choose_category"
            await update.message.reply_text("Kategoriyani tanlang:\n1-Mat Milliy\n2-Fiz Milliy\n3-Mat DTM\n4-Fiz DTM")
            return

        if text == "🔑 KALIT YUKLASH":
            user_data['admin_state'] = "key_id"
            await update.message.reply_text("Kalit yuklanadigan Test ID raqamini yozing:")
            return

        # Admin mantiqiy qadamlari
        astate = user_data.get('admin_state')
        if astate == "choose_category":
            cats = {"1": "MAT_MILLIY", "2": "FIZ_MILLIY", "3": "MAT_DTM", "4": "FIZ_DTM"}
            if text in cats:
                user_data["temp_cat"] = cats[text]
                user_data['admin_state'] = "pdf_id"
                await update.message.reply_text("Test uchun ID raqam yozing (masalan: M01):")
            return
        elif astate == "pdf_id":
            user_data["temp_tid"] = text.upper()
            user_data['admin_state'] = "pdf_file"
            await update.message.reply_text("📄 Endi PDF faylni yuboring:")
            return
        elif astate == "key_id":
            user_data["temp_key_id"] = text.upper()
            user_data['admin_state'] = "key_val"
            await update.message.reply_text(f"✍️ {text.upper()} uchun kalitlarni yuboring (abcd...):")
            return
        elif astate == "key_val":
            tid = user_data["temp_key_id"]
            db["answers"][tid] = re.sub(r'[^a-eA-E]', '', text).lower()
            save_data()
            await update.message.reply_text(f"✅ Kalit saqlandi! ID: {tid}", reply_markup=get_main_keyboard(user_id))
            user_data.clear()
            return

    # 3. TEST KATEGORIYALARI
    if "Matematika" in text or "Fizika" in text:
        if "Matematika" in text and "MILLIY" in text: sel_cat="MAT_MILLIY"
        elif "Fizika" in text and "MILLIY" in text: sel_cat="FIZ_MILLIY"
        elif "Matematika" in text and "DTM" in text: sel_cat="MAT_DTM"
        else: sel_cat="FIZ_DTM"

        available = [tid for tid, cat in db["categories"].items() if cat == sel_cat]
        if not available:
            await update.message.reply_text("⚠️ Hozircha bu bo'limda testlar yo'q.")
            return

        buttons = [[KeyboardButton(t)] for t in available]
        buttons.append([KeyboardButton("🔙 ASOSIY MENYU")])
        user_data['state'] = 'choosing_test'
        await update.message.reply_text("📑 Testni tanlang:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return

    # 4. TEST TOPSHIRISH JARAYONI
    if user_data.get('state') == 'choosing_test':
        if text in db["categories"]:
            user_data['selected_test_id'] = text
            user_data['state'] = 'waiting_test'
            await update.message.reply_text(f"💎 Tanlandi: {text}", reply_markup=start_test_menu())
        return

    if text == "🚀 Testni boshlash" and user_data.get('state') == 'waiting_test':
        tid = user_data['selected_test_id']
        path = db["pdfs"].get(tid)
        if path and os.path.exists(path):
            await update.message.reply_document(document=open(path, 'rb'), caption=f"📝 Test ID: {tid}\nJavoblaringizni bir qatorda yuboring (masalan: abcd...)")
            user_data['state'] = 'solving'
        else:
            await update.message.reply_text("❌ PDF fayl topilmadi.")
        return

    if user_data.get('state') == 'solving':
        tid = user_data['selected_test_id']
        correct_key = db["answers"].get(tid)
        if not correct_key:
            await update.message.reply_text("❗ Kalitlar hali yuklanmagan.")
            return
            
        user_ans = re.sub(r'[^a-eA-E]', '', text).lower()
        correct_count = sum(1 for u, c in zip(user_ans, correct_key) if u == c)
        total = len(correct_key)
        percent = (correct_count * 100) // total

        msg = f"📊 Natija: {tid}\n✅ To'g'ri: {correct_count}/{total}\n📈 Foiz: {percent}%"
        await update.message.reply_text(msg, reply_markup=get_main_keyboard(user_id))
        user_data.clear()
        return

    # 5. NATIJA CHIQARISH (ID tekshirish bilan)
    if text == "📊 NATIJA CHIQARISH":
        user_data['state'] = 'enter_check_id'
        await update.message.reply_text("Natijani bilish uchun Test ID yuboring:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 ASOSIY MENYU")]], resize_keyboard=True))
        return

    if user_data.get('state') == 'enter_check_id':
        tid = text.upper()
        if tid not in db["answers"]:
            await update.message.reply_text(f"❌ '{tid}' ID raqamli test topilmadi. Qayta urinib ko'ring:")
        else:
            user_data['check_tid'] = tid
            user_data['state'] = 'enter_check_ans'
            await update.message.reply_text(f"✅ {tid} topildi. Endi javoblaringizni yuboring:")
        return

    if user_data.get('state') == 'enter_check_ans':
        tid = user_data['check_tid']
        correct_key = db["answers"][tid]
        user_ans = re.sub(r'[^a-eA-E]', '', text).lower()
        correct_count = sum(1 for u, c in zip(user_ans, correct_key) if u == c)
        percent = (correct_count * 100) // len(correct_key)
        await update.message.reply_text(f"📊 Natija: {tid}\n✅ To'g'ri: {correct_count}/{len(correct_key)}\n📈 Foiz: {percent}%", reply_markup=get_main_keyboard(user_id))
        user_data.clear()
        return

# ===== PDF UPLOAD (ADMIN) =====
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_ID and context.user_data.get('admin_state') == "pdf_file":
        tid = context.user_data.get("temp_tid")
        cat = context.user_data.get("temp_cat")
        
        file = await context.bot.get_file(update.message.document.file_id)
        fname = f"{tid}.pdf"
        await file.download_to_drive(fname)
        
        db["pdfs"][tid] = fname
        db["categories"][tid] = cat
        save_data()
        
        await update.message.reply_text(f"✅ PDF yuklandi! ID: {tid}", reply_markup=get_main_keyboard(user_id))
        context.user_data.clear()

# ===== MAIN RUN =====
if __name__ == "__main__":
    load_data()
    keep_alive() # Render uchun Flask
    
    if TOKEN:
        app = ApplicationBuilder().token(TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(MessageHandler(filters.Document.PDF, handle_document))
        
        print("Bot ishlamoqda... 🚀")
        # drop_pending_updates=True konfliktlarni oldini oladi
        app.run_polling(drop_pending_updates=True)
