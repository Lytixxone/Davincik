import sqlite3
import time
import random
import telebot
from telebot import types

# ==================== ТОКЕН ====================
TOKEN_PART1 = "9181019610:"
TOKEN_PART2 = "AAFP_OKWUTMXx0qZdinGWCqHPveWUxp-ylw"
bot = telebot.TeleBot(TOKEN_PART1 + TOKEN_PART2)

ADMIN_USERNAME = "lytixx"

# ==================== БАЗА ====================
conn = sqlite3.connect("dating.db", check_same_thread=False, timeout=30)

conn.execute("""CREATE TABLE IF NOT EXISTS users(
    tg_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
    referrer_id INTEGER, is_vip INTEGER DEFAULT 0, is_admin INTEGER DEFAULT 0,
    is_moder INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0, reg_date INTEGER
)""")
conn.execute("""CREATE TABLE IF NOT EXISTS profiles(
    user_id INTEGER PRIMARY KEY, name TEXT, bio TEXT, age INTEGER,
    city TEXT, photo_id TEXT, status TEXT DEFAULT 'pending'
)""")
conn.execute("""CREATE TABLE IF NOT EXISTS states(
    tg_id INTEGER PRIMARY KEY, state TEXT, data TEXT
)""")
conn.execute("""CREATE TABLE IF NOT EXISTS config(
    key TEXT PRIMARY KEY, value TEXT
)""")
conn.commit()

if not conn.execute("SELECT value FROM config WHERE key='bot_enabled'").fetchone():
    conn.execute("INSERT INTO config VALUES('bot_enabled', '1')")
    conn.commit()

# ==================== УТИЛИТЫ ====================
def cfg(key):
    r = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    return r[0] if r else None

def set_cfg(key, val):
    conn.execute("INSERT OR REPLACE INTO config VALUES(?, ?)", (key, val))
    conn.commit()

def get_user(tg_id):
    r = conn.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()
    if not r: return None
    return {"tg_id": r[0], "username": r[1], "first_name": r[2], "ref": r[3],
            "vip": r[4], "admin": r[5], "moder": r[6], "banned": r[7]}

def get_profile(tg_id):
    r = conn.execute("SELECT * FROM profiles WHERE user_id=?", (tg_id,)).fetchone()
    if not r: return None
    return {"user_id": r[0], "name": r[1], "bio": r[2], "age": r[3], "city": r[4], "photo": r[5], "status": r[6]}

def set_state(tg_id, state, data=""):
    conn.execute("INSERT OR REPLACE INTO states VALUES(?, ?, ?)", (tg_id, state, data))
    conn.commit()

def get_state(tg_id):
    r = conn.execute("SELECT state, data FROM states WHERE tg_id=?", (tg_id,)).fetchone()
    return r if r else (None, None)

def clear_state(tg_id):
    conn.execute("DELETE FROM states WHERE tg_id=?", (tg_id,))
    conn.commit()

def is_admin(tg_id):
    u = get_user(tg_id)
    if u and u["username"] and u["username"].lower() == ADMIN_USERNAME: return True
    return u and u["admin"] == 1

def is_moder(tg_id):
    u = get_user(tg_id)
    return u and (u["moder"] == 1 or is_admin(tg_id))

def check_bot():
    return cfg("bot_enabled") == "1"

# ==================== ГЛАВНОЕ МЕНЮ ====================
def main_menu(tg_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👀 Смотреть анкеты", callback_data="view_profiles"),
        types.InlineKeyboardButton("📝 Моя анкета", callback_data="my_profile")
    )
    markup.add(
        types.InlineKeyboardButton("👑 VIP", callback_data="vip_info"),
        types.InlineKeyboardButton("🔗 Пригласить друга", callback_data="ref_link")
    )
    if is_moder(tg_id):
        markup.add(types.InlineKeyboardButton("🛡 Модерация", callback_data="mod_panel"))
    if is_admin(tg_id):
        markup.add(types.InlineKeyboardButton("⚙️ Админка", callback_data="admin_panel"))
    return markup

# ==================== СТАРТ ====================
@bot.message_handler(commands=['start'])
def start(m):
    if m.chat.type != "private": return
    ref_id = None
    args = m.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        try: ref_id = int(args[1].split("_")[1])
        except: pass

    u = get_user(m.from_user.id)
    if not u:
        conn.execute("INSERT INTO users(tg_id, username, first_name, referrer_id, reg_date) VALUES(?,?,?,?,?)",
                     (m.from_user.id, m.from_user.username, m.from_user.first_name, ref_id, int(time.time())))
        conn.commit()
        u = get_user(m.from_user.id)
        # Уведомление рефереру
        if ref_id:
            try: bot.send_message(ref_id, f"🔔 По твоей ссылке пришёл новый пользователь: {m.from_user.first_name}")
            except: pass

    if u["banned"]:
        return bot.send_message(m.chat.id, "🚫 Вы забанены в этом боте.")
    if not check_bot() and not is_admin(m.from_user.id):
        return bot.send_message(m.chat.id, "🛑 Бот временно отключён. Попробуйте позже.")

    p = get_profile(m.from_user.id)
    if not p:
        show_rules(m.chat.id)
    else:
        bot.send_message(m.chat.id, "👋 С возвращением!", reply_markup=main_menu(m.from_user.id))

# ==================== ПРАВИЛА ====================
def show_rules(chat_id):
    text = (
        "📜 <b>Правила бота знакомств:</b>\n\n"
        "1. Запрещено оскорблять других пользователей.\n"
        "2. Запрещено выкладывать чужие фото.\n"
        "3. Запрещено спамить и рекламировать.\n"
        "4. Запрещён контент 18+ без согласия.\n"
        "5. За нарушение правил — блокировка без предупреждения.\n\n"
        "Нажимая «Согласен», вы подтверждаете, что согласны с правилами."
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Согласен, создать анкету", callback_data="create_profile"))
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")

# ==================== СОЗДАНИЕ АНКЕТЫ ====================
@bot.callback_query_handler(func=lambda c: c.data == "create_profile")
def create_profile(call):
    bot.answer_callback_query(call.id)
    set_state(call.from_user.id, "p_name")
    bot.send_message(call.message.chat.id, "1️⃣ <b>Как тебя зовут?</b>", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.chat.type == "private" and get_state(m.from_user.id)[0] == "p_name")
def p_name(m):
    if len(m.text) > 30: return bot.send_message(m.chat.id, "❌ Слишком длинно.")
    set_state(m.from_user.id, "p_bio", m.text)
    bot.send_message(m.chat.id, "2️⃣ <b>Расскажи о себе:</b>", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.chat.type == "private" and get_state(m.from_user.id)[0] == "p_bio")
def p_bio(m):
    if len(m.text) > 300: return bot.send_message(m.chat.id, "❌ Максимум 300 символов.")
    st = get_state(m.from_user.id)
    set_state(m.from_user.id, "p_age", f"{st[1]}|{m.text}")
    bot.send_message(m.chat.id, "3️⃣ <b>Сколько тебе лет?</b>", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.chat.type == "private" and get_state(m.from_user.id)[0] == "p_age")
def p_age(m):
    try:
        age = int(m.text)
        if age < 12 or age > 100: raise
    except:
        return bot.send_message(m.chat.id, "❌ Введи реальный возраст (12-100).")
    st = get_state(m.from_user.id)
    set_state(m.from_user.id, "p_city", f"{st[1]}|{age}")
    bot.send_message(m.chat.id, "4️⃣ <b>Из какого ты населённого пункта?</b>", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.chat.type == "private" and get_state(m.from_user.id)[0] == "p_city")
def p_city(m):
    if len(m.text) > 50: return bot.send_message(m.chat.id, "❌ Слишком длинно.")
    st = get_state(m.from_user.id)
    set_state(m.from_user.id, "p_photo", f"{st[1]}|{m.text}")
    bot.send_message(m.chat.id, "5️⃣ <b>Отправь своё фото (одно):</b>", parse_mode="HTML")

@bot.message_handler(content_types=['photo'], func=lambda m: m.chat.type == "private" and get_state(m.from_user.id)[0] == "p_photo")
def p_photo(m):
    photo_id = m.photo[-1].file_id
    st = get_state(m.from_user.id)
    data = st[1].split("|")
    if len(data) != 4: return bot.send_message(m.chat.id, "❌ Ошибка. Начни заново.")
    
    name, bio, age, city = data[0], data[1], int(data[2]), data[3]
    
    conn.execute("INSERT OR REPLACE INTO profiles(user_id, name, bio, age, city, photo_id, status) VALUES(?,?,?,?,?,?,?)",
                 (m.from_user.id, name, bio, age, city, photo_id, 'pending'))
    conn.commit()
    clear_state(m.from_user.id)
    
    if is_admin(m.from_user.id):
        conn.execute("UPDATE profiles SET status='approved' WHERE user_id=?", (m.from_user.id,))
        conn.commit()
        bot.send_message(m.chat.id, "✅ Анкета создана и сразу опубликована!", reply_markup=main_menu(m.from_user.id))
    else:
        bot.send_message(m.chat.id, "✅ Анкета отправлена на модерацию!")
        notify_moders(m.from_user)

def notify_moders(user):
    mods = conn.execute("SELECT tg_id FROM users WHERE is_moder=1 OR is_admin=1 OR username=?", (ADMIN_USERNAME,)).fetchall()
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Одобрить", callback_data=f"appr_{user.id}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"rej_{user.id}")
    )
    for (mid,) in mods:
        try: bot.send_message(mid, f"🛡 Новая анкета от {user.first_name} на модерацию.", reply_markup=markup)
        except: pass

# ==================== ПРОСМОТР АНКЕТ ====================
@bot.callback_query_handler(func=lambda c: c.data == "view_profiles")
def view_profiles(call):
    bot.answer_callback_query(call.id)
    # Выборка: VIP попадаются чаще (делим рандом на 3)
    row = conn.execute("""
        SELECT p.*, u.is_vip FROM profiles p 
        JOIN users u ON p.user_id = u.tg_id 
        WHERE p.status='approved' AND p.user_id != ? AND u.is_banned=0
        ORDER BY RANDOM() * (CASE WHEN u.is_vip=1 THEN 0.3 ELSE 1.0 END)
        LIMIT 1
    """, (call.from_user.id,)).fetchone()
    
    if not row:
        return bot.send_message(call.message.chat.id, "😔 Пока нет других анкет. Загляни позже!")
    
    uid, name, bio, age, city, photo, status, is_vip = row
    crown = " 👑" if is_vip else ""
    vip_text = "\n\n⭐ <b>У этого пользователя есть VIP!</b>" if is_vip else ""
    
    caption = f"<b>{name}{crown}, {age}</b>\n📍 {city}\n\n{bio}{vip_text}"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("❤️ Лайк", callback_data=f"like_{uid}"),
        types.InlineKeyboardButton("👎 Дальше", callback_data="view_profiles")
    )
    bot.send_photo(call.message.chat.id, photo, caption=caption, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("like_"))
def like_profile(call):
    target = int(call.data.split("_")[1])
    bot.answer_callback_query(call.id, "❤️ Лайк отправлен!")
    try:
        bot.send_message(target, f"❤️ Кто-то лайкнул твою анкету!")
    except: pass
    view_profiles(call)

# ==================== МОЯ АНКЕТА ====================
@bot.callback_query_handler(func=lambda c: c.data == "my_profile")
def my_profile(call):
    p = get_profile(call.from_user.id)
    u = get_user(call.from_user.id)
    if not p:
        return bot.send_message(call.message.chat.id, "У тебя нет анкеты. /start")
    
    crown = " 👑" if u["vip"] else ""
    caption = f"<b>{p['name']}{crown}, {p['age']}</b>\n📍 {p['city']}\n\n{p['bio']}\n\nСтатус: {p['status']}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🗑 Удалить анкету", callback_data="del_profile"))
    bot.send_photo(call.message.chat.id, p["photo"], caption=caption, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "del_profile")
def del_profile(call):
    conn.execute("DELETE FROM profiles WHERE user_id=?", (call.from_user.id,))
    conn.commit()
    bot.edit_message_caption("🗑 Анкета удалена.", call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "Напиши /start чтобы создать новую.", reply_markup=main_menu(call.from_user.id))

# ==================== VIP ====================
@bot.callback_query_handler(func=lambda c: c.data == "vip_info")
def vip_info(call):
    bot.answer_callback_query(call.id)
    text = (
        "👑 <b>VIP Статус</b>\n\n"
        "Что даёт VIP:\n"
        "• Корона 👑 рядом с именем\n"
        "• Твоя анкета показывается в 3 раза чаще\n"
        "• Пометка «У пользователя есть VIP»\n\n"
        "Для покупки VIP свяжитесь с админом: @" + ADMIN_USERNAME
    )
    bot.send_message(call.message.chat.id, text, parse_mode="HTML")

# ==================== РЕФЕРАЛКА ====================
@bot.callback_query_handler(func=lambda c: c.data == "ref_link")
def ref_link(call):
    bot.answer_callback_query(call.id)
    bot_info = bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{call.from_user.id}"
    invited = conn.execute("SELECT COUNT(*) FROM users WHERE referrer_id=?", (call.from_user.id,)).fetchone()[0]
    text = (
        f"🔗 <b>Твоя ссылка:</b>\n<code>{link}</code>\n\n"
        f"👥 Приглашено: <b>{invited}</b> чел."
    )
    bot.send_message(call.message.chat.id, text, parse_mode="HTML")

# ==================== МОДЕРАЦИЯ ====================
@bot.callback_query_handler(func=lambda c: c.data == "mod_panel")
def mod_panel(call):
    if not is_moder(call.from_user.id): return
    bot.answer_callback_query(call.id)
    pending = conn.execute("SELECT p.user_id, p.name, u.first_name FROM profiles p JOIN users u ON p.user_id=u.tg_id WHERE p.status='pending' LIMIT 5").fetchall()
    if not pending:
        return bot.send_message(call.message.chat.id, "✅ Нет анкет на модерации.")
    for uid, name, fname in pending:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Одобрить", callback_data=f"appr_{uid}"),
            types.InlineKeyboardButton("❌ Отклонить", callback_data=f"rej_{uid}")
        )
        bot.send_message(call.message.chat.id, f"Анкета: <b>{name}</b> ({fname})", reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("appr_") or c.data.startswith("rej_"))
def moderate(call):
    if not is_moder(call.from_user.id): return bot.answer_callback_query(call.id, "Нет прав", show_alert=True)
    action, target = call.data.split("_")[0], int(call.data.split("_")[1])
    status = "approved" if action == "appr" else "rejected"
    conn.execute("UPDATE profiles SET status=? WHERE user_id=?", (status, target))
    conn.commit()
    bot.edit_message_text(f"{'✅ Одобрено' if status=='approved' else '❌ Отклонено'} ({target})", call.message.chat.id, call.message.message_id)
    try: bot.send_message(target, f"Твоя анкета: {'одобрена ✅' if status=='approved' else 'отклонена ❌'}")
    except: pass

# ==================== АДМИНКА ====================
@bot.callback_query_handler(func=lambda c: c.data == "admin_panel")
def admin_panel(call):
    if not is_admin(call.from_user.id): return
    bot.answer_callback_query(call.id)
    enabled = cfg("bot_enabled") == "1"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(f"Бот: {'ВКЛ 🟢' if enabled else 'ВЫКЛ 🔴'}", callback_data="toggle_bot"))
    markup.add(types.InlineKeyboardButton("👥 Список пользователей", callback_data="admin_users"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_main"))
    bot.send_message(call.message.chat.id, "⚙️ <b>Админ-панель</b>", reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "toggle_bot")
def toggle_bot(call):
    if not is_admin(call.from_user.id): return
    new = "0" if cfg("bot_enabled") == "1" else "1"
    set_cfg("bot_enabled", new)
    bot.answer_callback_query(call.id, f"Бот теперь {'ВКЛ' if new=='1' else 'ВЫКЛ'}")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=admin_panel_markup())

def admin_panel_markup():
    enabled = cfg("bot_enabled") == "1"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(f"Бот: {'ВКЛ 🟢' if enabled else 'ВЫКЛ 🔴'}", callback_data="toggle_bot"))
    markup.add(types.InlineKeyboardButton("👥 Список пользователей", callback_data="admin_users"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_main"))
    return markup

@bot.callback_query_handler(func=lambda c: c.data == "admin_users")
def admin_users(call):
    if not is_admin(call.from_user.id): return
    users = conn.execute("SELECT tg_id, first_name, username, is_vip, is_admin, is_moder, is_banned FROM users LIMIT 30").fetchall()
    markup = types.InlineKeyboardMarkup(row_width=1)
    for uid, fname, uname, vip, adm, mod, ban in users:
        tag = "👑" if vip else ""
        if adm: tag += "⚙️"
        if mod: tag += "🛡"
        if ban: tag += "🚫"
        markup.add(types.InlineKeyboardButton(f"{tag} {fname} (ID:{uid})", callback_data=f"adm_u_{uid}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
    bot.edit_message_text("👥 <b>Список пользователей:</b>", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_u_"))
def admin_user_manage(call):
    if not is_admin(call.from_user.id): return
    uid = int(call.data.split("_")[2])
    u = get_user(uid)
    if not u: return
    ref_count = conn.execute("SELECT COUNT(*) FROM users WHERE referrer_id=?", (uid,)).fetchone()[0]
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("👑 VIP вкл/выкл", callback_data=f"t_vip_{uid}"))
    markup.add(types.InlineKeyboardButton("⚙️ Админ вкл/выкл", callback_data=f"t_adm_{uid}"))
    markup.add(types.InlineKeyboardButton("🛡 Модер вкл/выкл", callback_data=f"t_mod_{uid}"))
    markup.add(types.InlineKeyboardButton("🚫 Бан вкл/выкл", callback_data=f"t_ban_{uid}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_users"))
    
    text = (
        f"👤 <b>{u['first_name']}</b>\n"
        f"ID: <code>{u['tg_id']}</code>\n"
        f"Юзер: @{u['username'] or '—'}\n"
        f"👥 Пригласил: <b>{ref_count}</b> чел.\n\n"
        f"VIP: {'✅' if u['vip'] else '❌'} | Админ: {'✅' if u['admin'] else '❌'} | Модер: {'✅' if u['moder'] else '❌'} | Бан: {'✅' if u['banned'] else '❌'}"
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("t_"))
def admin_toggle(call):
    if not is_admin(call.from_user.id): return
    parts = call.data.split("_")
    action, uid = parts[1], int(parts[2])
    field_map = {"vip": "is_vip", "adm": "is_admin", "mod": "is_moder", "ban": "is_banned"}
    field = field_map.get(action)
    if not field: return
    
    cur = conn.execute(f"SELECT {field} FROM users WHERE tg_id=?", (uid,)).fetchone()[0]
    new_val = 0 if cur else 1
    conn.execute(f"UPDATE users SET {field}=? WHERE tg_id=?", (new_val, uid))
    conn.commit()
    admin_user_manage(call)

@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def back_main(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "Главное меню:", reply_markup=main_menu(call.from_user.id))

# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    print("Бот знакомств запущен...")
    bot.polling(none_stop=True)