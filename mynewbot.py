import logging
import os
import re
import json
import threading
from datetime import datetime
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ===== SERVER =====
server = Flask('')
@server.route('/')
def home(): return "Bot is live!"

def run():
    port = int(os.environ.get("PORT", 10000))
    server.run(host='0.0.0.0', port=port)

# ===== DATA STORAGE =====
db = {"answers": {}, "pdfs": {}, "categories": {}, "users": [], "results": {}}

def save_data():
    with open("data.json", "w") as f:
        json.dump(db, f, indent=4)

def load_data():
    global db
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r") as f:
                loaded = json.load(f)
                for key in db.keys():
                    if key in loaded: db[key] = loaded[key]
        except: pass

# ===== CONFIG =====
ADMIN_ID = 6257157305
TOKEN = os.getenv("BOT_TOKEN")

# ===== KEYBOARDS =====
def get_main_keyboard(user_id):
    buttons = [
        [KeyboardButton("🥇 ᴍɪʟʟɪʏ (ᴍᴀᴛᴇᴍᴀᴛɪᴋᴀ)"), KeyboardButton("🥇 ᴍɪʟʟɪʏ (ғɪᴢɪᴋᴀ)")],
        [KeyboardButton("🏛️ ᴅᴛᴍ (ᴍᴀᴛᴇᴍᴀᴛɪᴋᴀ)"), KeyboardButton("🏛️ ᴅᴛᴍ (ғɪᴢɪᴋᴀ)")],
        [KeyboardButton("📊 ɴᴀᴛɪᴊᴀ ᴛᴇᴋsʜɪʀɪsʜ"), KeyboardButton("📜 ᴍᴇɴɪɴɢ ɴᴀᴛɪᴊᴀʟᴀʀɪᴍ")],
        [KeyboardButton("👨‍💻 ᴀᴅᴍɪɴɢᴀ ʙᴏɢ'ʟᴀɴɪsʜ")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton("➕ ᴛᴇsᴛ ǫᴏ'sʜɪsʜ"), KeyboardButton("🔑 ᴋᴀʟɪᴛ ʏᴜᴋʟᴀsʜ")])
        buttons.append([KeyboardButton("👥 sᴛᴀᴛɪsᴛɪᴋᴀ")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in db["users"]: db["users"].append(uid)
    if uid not in db["results"]: db["results"][uid] = []
    save_data()
    context.user_data.clear()
    await update.message.reply_text("🚀 TestArena1-ga xush kelibsiz!", reply_markup=get_main_keyboard(int(uid)))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = str(update.effective_user.id)
    user_data = context.user_data

    # --- NAVIGATSIYA ---
    if text == "🔙 ᴀsᴏsɪʏ ᴍᴇɴʏᴜ" or text == "🛑 ᴛᴇsᴛɴɪ ʏᴀᴋᴜɴʟᴀsʜ":
        user_data.clear()
        await update.message.reply_text("🏠 Asosiy menyu:", reply_markup=get_main_keyboard(int(uid)))
        return

    # --- MENING NATIJALARIM ---
    if text == "📜 ᴍᴇɴɪɴɢ ɴᴀᴛɪᴊᴀʟᴀʀɪᴍ":
        history = db["results"].get(uid, [])
        if not history:
            await update.message.reply_text("📭 Sizda hali saqlangan natijalar yo'q.")
            return
        msg = "📜 **SIZNING OXIRGI NATIJALARINGIZ:**\n\n"
        for res in history[-10:]:
            msg += f"📅 {res['date']} | 🆔 {res['id']}\n✅ {res['score']}/{res['total']} ({res['percent']}%)\n"
            msg += "----------------------------\n"
        await update.message.reply_text(msg, parse_mode='Markdown')
        return

    # --- NATIJA TEKSHIRISH + XATOLAR TAHLILI ---
    if text == "📊 ɴᴀᴛɪᴊᴀ ᴛᴇᴋsʜɪʀɪsʜ":
        user_data['state'] = 'check_id'
        await update.message.reply_text("Natijani bilish uchun Test ID yuboring:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 ᴀsᴏsɪʏ ᴍᴇɴʏᴜ")]], resize_keyboard=True))
        return

    if user_data.get('state') == 'check_id':
        tid = text.upper()
        if tid not in db["answers"]:
            await update.message.reply_text("❌ ID topilmadi.")
        else:
            user_data['check_tid'], user_data['state'] = tid, 'check_ans'
            await update.message.reply_text(f"✅ {tid} topildi. Endi javoblaringizni yuboring (masalan: abcd...):")
        return

    if user_data.get('state') == 'check_ans':
        tid = user_data['check_tid']
        correct_key = db["answers"][tid]
        user_ans = re.sub(r'[^a-eA-E]', '', text).lower()
        
        score = 0
        analysis = ""
        # Har bir savolni tekshirish
        for i in range(len(correct_key)):
            u_ans = user_ans[i] if i < len(user_ans) else "?"
            c_ans = correct_key[i]
            if u_ans == c_ans:
                score += 1
                analysis += f"{i+1}. ✅\n"
            else:
                analysis += f"{i+1}. ❌ (Siz: {u_ans.upper()}, Aslida: {c_ans.upper()})\n"

        total = len(correct_key)
        percent = (score * 100) // total
        date_str = datetime.now().strftime("%d/%m %H:%M")

        # Tarixga saqlash
        if uid not in db["results"]: db["results"][uid] = []
        db["results"][uid].append({"id": tid, "score": score, "total": total, "percent": percent, "date": date_str})
        save_data()

        result_msg = (f"📊 **Natija: {tid}**\n"
                      f"✅ To'g'ri: {score}/{total}\n"
                      f"📈 Foiz: {percent}%\n\n"
                      f"📝 **Xatolar tahlili:**\n{analysis}")
        
        # Agar tahlil juda uzun bo'lsa (masalan 30+ savol), Telegram xabar sig'imi uchun bo'lib yuboramiz
        if len(result_msg) > 4096:
            await update.message.reply_text(f"📊 Natija: {tid}\n✅ To'g'ri: {score}/{total}\n📈 Foiz: {percent}%")
            await update.message.reply_text(f"📝 **Xatolar tahlili:**\n{analysis}", reply_markup=get_main_keyboard(int(uid)))
        else:
            await update.message.reply_text(result_msg, parse_mode='Markdown', reply_markup=get_main_keyboard(int(uid)))
        
        user_data.clear()
        return

    # --- ADMIN QISMI ---
    if uid == str(ADMIN_ID):
        if text == "👥 sᴛᴀᴛɪsᴛɪᴋᴀ":
            await update.message.reply_text(f"👤 Jami foydalanuvchilar: {len(db['users'])}")
            return
        if text == "➕ ᴛᴇsᴛ ǫᴏ'sʜɪsʜ":
            user_data['admin_state'] = "choose_category"
            await update.message.reply_text("1-Mat Milliy, 2-Fiz Milliy, 3-Mat DTM, 4-Fiz DTM")
            return
        # (Qolgan admin mantiqlari avvalgidek...)

# ===== MAIN =====
if __name__ == "__main__":
    load_data()
    threading.Thread(target=run, daemon=True).start()
    if TOKEN:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        # (PDF yuklash funksiyasini ham qo'shishni unutmang)
        app.run_polling(drop_pending_updates=True)
