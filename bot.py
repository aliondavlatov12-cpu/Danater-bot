# ============================================================
# DANATER FREE FIRE BOT — PART 1/3
# ============================================================

import os
import io
import csv
import html
import logging
import sqlite3
from datetime import datetime
from contextlib import contextmanager
from threading import Thread

from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# ============================================================
# CONFIG
# ============================================================

TOKEN = os.getenv("TOKEN", "").strip()

ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

ADMIN_USERNAME     = os.getenv("ADMIN_USERNAME", "ffxdavlatov").lstrip("@")
CHANNEL_USERNAME   = os.getenv("CHANNEL_USERNAME", "otzivi_danater1").lstrip("@")
CHANNEL_URL        = f"https://t.me/{CHANNEL_USERNAME}"

ALIF_NUMBER        = os.getenv("ALIF_NUMBER", "+992917003888")
DC_NUMBER          = os.getenv("DC_NUMBER", "+992783836464")

WHATSAPP_NUMBER    = os.getenv("WHATSAPP_NUMBER", "992783456363")
WHATSAPP_URL       = f"https://wa.me/{WHATSAPP_NUMBER}"

INSTAGRAM_URL      = os.getenv("INSTAGRAM_URL", "https://www.instagram.com/danatershop.tj")
TELEGRAM_ADMIN_URL = os.getenv("TELEGRAM_ADMIN_URL", "https://t.me/ffxdavlatov")

PORT      = int(os.getenv("PORT", "10000"))
DB_PATH   = os.getenv("DB_PATH", "data.db")
REF_BONUS_PERCENT = 4

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("DANATER")

# ============================================================
# DEFAULT PRODUCTS
# ============================================================

DEFAULT_PRODUCTS = {
    "100":   {"name": "💎 100 алмаз",     "price": 10,  "category": "diamond"},
    "310":   {"name": "💎 310 алмаз",     "price": 30,  "category": "diamond"},
    "520":   {"name": "💎 520 алмаз",     "price": 50,  "category": "diamond"},
    "1060":  {"name": "💎 1060 алмаз",    "price": 100, "category": "diamond"},
    "2180":  {"name": "💎 2180 алмаз",    "price": 200, "category": "diamond"},
    "5600":  {"name": "💎 5600 алмаз",    "price": 550, "category": "diamond"},
    "week":  {"name": "🎟 Ваучер 1 ҳафта", "price": 18,  "category": "voucher"},
    "month": {"name": "🎟 Ваучер 1 моҳ",   "price": 95,  "category": "voucher"},
    "lite":  {"name": "🎟 Ваучер Лайт",    "price": 7,   "category": "voucher"},
    "elite": {"name": "🎫 Elite Pass",    "price": 120, "category": "pass"},
    "booyah":{"name": "🎫 Booyah Pass",   "price": 60,  "category": "pass"},
}

CATEGORIES = {
    "diamond": "💎 Алмазҳо",
    "voucher": "🎟 Ваучерҳо",
    "pass":    "🎫 Pass / Elite",
}

# ============================================================
# DATABASE
# ============================================================

@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with db() as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT,
            balance REAL DEFAULT 0, referrer_id INTEGER, referred_count INTEGER DEFAULT 0,
            joined_at TEXT, updated_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, price REAL NOT NULL,
            category TEXT NOT NULL, active INTEGER DEFAULT 1)""")
        c.execute("""CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY, user_id INTEGER, customer_name TEXT, free_fire_id TEXT,
            product_id TEXT, product_name TEXT, price REAL, payment_method TEXT,
            promo_code TEXT, discount REAL DEFAULT 0, final_price REAL,
            referred_by INTEGER, status TEXT DEFAULT 'pending',
            created_at TEXT, updated_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS promos (
            code TEXT PRIMARY KEY, discount_percent INTEGER NOT NULL,
            max_uses INTEGER DEFAULT 0, used INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1, created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, order_id TEXT,
            rating INTEGER, text TEXT, created_at TEXT)""")
        conn.commit()

def seed_products():
    with db() as conn:
        c = conn.cursor()
        for pid, p in DEFAULT_PRODUCTS.items():
            c.execute("SELECT id FROM products WHERE id=?", (pid,))
            if not c.fetchone():
                c.execute("INSERT INTO products (id,name,price,category,active) VALUES (?,?,?,?,1)",
                          (pid, p["name"], p["price"], p["category"]))
        conn.commit()

# ---------- USERS ----------
def save_user(user, referrer_id=None):
    now = datetime.now().isoformat()
    with db() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE id=?", (user.id,))
        if c.fetchone():
            c.execute("""UPDATE users SET username=?, first_name=?, last_name=?, updated_at=?
                         WHERE id=?""",
                      (user.username or "", user.first_name or "", user.last_name or "", now, user.id))
        else:
            c.execute("""INSERT INTO users
                (id,username,first_name,last_name,referrer_id,referred_count,balance,joined_at,updated_at)
                VALUES (?,?,?,?,?,0,0,?,?)""",
                (user.id, user.username or "", user.first_name or "", user.last_name or "",
                 referrer_id, now, now))
        conn.commit()

def get_user(uid):
    with db() as conn:
        return conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

def users_count():
    with db() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

def all_user_ids():
    with db() as conn:
        return [r["id"] for r in conn.execute("SELECT id FROM users").fetchall()]

def all_users_detailed(limit=50):
    with db() as conn:
        return conn.execute("""SELECT id,username,first_name,balance,referred_count
                               FROM users
                               ORDER BY referred_count DESC, balance DESC LIMIT ?""",
                            (limit,)).fetchall()

def add_balance(uid, amount):
    with db() as conn:
        conn.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amount, uid))
        conn.commit()

def deduct_balance(uid, amount):
    with db() as conn:
        conn.execute("UPDATE users SET balance = balance - ? WHERE id=?", (amount, uid))
        conn.commit()

def increment_referral(ref_id):
    with db() as conn:
        conn.execute("UPDATE users SET referred_count = referred_count + 1 WHERE id=?", (ref_id,))
        conn.commit()

def get_referrals(ref_id):
    with db() as conn:
        return conn.execute("SELECT * FROM users WHERE referrer_id=? ORDER BY joined_at DESC",
                            (ref_id,)).fetchall()

def give_referral_bonus(ref_id, order_price, percent=4):
    bonus = round(float(order_price) * percent / 100, 2)
    if bonus <= 0:
        return 0
    add_balance(ref_id, bonus)
    return bonus

def referral_earned(ref_id, percent=4):
    with db() as conn:
        row = conn.execute("""SELECT COALESCE(SUM(final_price * ? / 100), 0) as s
                              FROM orders WHERE referred_by=?""",
                           (percent, ref_id)).fetchone()
        return round(row["s"] or 0, 2)

# ---------- PRODUCTS ----------
def get_products(category=None):
    with db() as conn:
        if category:
            return conn.execute(
                "SELECT * FROM products WHERE active=1 AND category=? ORDER BY price",
                (category,)).fetchall()
        return conn.execute(
            "SELECT * FROM products WHERE active=1 ORDER BY category, price").fetchall()

def get_product(pid):
    with db() as conn:
        return conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()

def search_products(q):
    q2 = f"%{q.lower()}%"
    with db() as conn:
        return conn.execute(
            "SELECT * FROM products WHERE active=1 AND (LOWER(name) LIKE ? OR LOWER(id) LIKE ?) ORDER BY price",
            (q2, q2)).fetchall()

def update_price(pid, price):
    with db() as conn:
        conn.execute("UPDATE products SET price=? WHERE id=?", (price, pid))
        conn.commit()

def add_product(pid, name, price, category):
    with db() as conn:
        conn.execute("""INSERT OR REPLACE INTO products
            (id, name, price, category, active) VALUES (?,?,?,?,1)""",
            (pid, name, price, category))
        conn.commit()

def delete_product(pid):
    with db() as conn:
        conn.execute("UPDATE products SET active=0 WHERE id=?", (pid,))
        conn.commit()

def all_products_admin():
    with db() as conn:
        return conn.execute("SELECT * FROM products ORDER BY category, price").fetchall()

# ---------- ORDERS ----------
def create_order(o):
    with db() as conn:
        conn.execute("""INSERT INTO orders
            (id,user_id,customer_name,free_fire_id,product_id,product_name,
             price,payment_method,promo_code,discount,final_price,referred_by,
             status,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'pending',?,?)""",
            (o["id"], o["user_id"], o["customer_name"], o["free_fire_id"],
             o["product_id"], o["product_name"], o["price"], o["payment_method"],
             o.get("promo_code"), o.get("discount", 0), o["final_price"],
             o.get("referred_by"), o["created_at"], o["created_at"]))
        conn.commit()

def get_order(oid):
    with db() as conn:
        return conn.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()

def update_order_status(oid, status):
    with db() as conn:
        conn.execute("UPDATE orders SET status=?, updated_at=? WHERE id=?",
                     (status, datetime.now().isoformat(), oid))
        conn.commit()

def user_orders(uid, limit=10):
    with db() as conn:
        return conn.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
                            (uid, limit)).fetchall()

def all_orders(limit=20):
    with db() as conn:
        return conn.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT ?",
                            (limit,)).fetchall()

def orders_stats():
    with db() as conn:
        c = conn.cursor()
        total     = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        done      = c.execute("SELECT COUNT(*) FROM orders WHERE status='done'").fetchone()[0]
        pending   = c.execute("SELECT COUNT(*) FROM orders WHERE status='pending'").fetchone()[0]
        cancelled = c.execute("SELECT COUNT(*) FROM orders WHERE status='cancelled'").fetchone()[0]
        revenue   = c.execute("SELECT COALESCE(SUM(final_price),0) FROM orders WHERE status='done'").fetchone()[0]
        return {"total": total, "done": done, "pending": pending,
                "cancelled": cancelled, "revenue": revenue}

def export_orders_csv():
    with db() as conn:
        rows = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ID","UserID","Customer","FF ID","Product","Price","Payment",
                "Promo","Discount","Final","ReferredBy","Status","Created"])
    for r in rows:
        w.writerow([r["id"], r["user_id"], r["customer_name"], r["free_fire_id"],
                    r["product_name"], r["price"], r["payment_method"],
                    r["promo_code"], r["discount"], r["final_price"],
                    r["referred_by"], r["status"], r["created_at"]])
    buf.seek(0)
    return buf

# ---------- PROMOS ----------
def create_promo(code, percent, max_uses=0):
    with db() as conn:
        conn.execute("""INSERT OR REPLACE INTO promos
            (code,discount_percent,max_uses,used,active,created_at)
            VALUES (?,?,?,0,1,?)""",
            (code.upper(), percent, max_uses, datetime.now().isoformat()))
        conn.commit()

def get_promo(code):
    with db() as conn:
        return conn.execute("SELECT * FROM promos WHERE code=? AND active=1",
                            (code.upper(),)).fetchone()

def use_promo(code):
    with db() as conn:
        conn.execute("UPDATE promos SET used = used + 1 WHERE code=?", (code.upper(),))
        conn.commit()

def all_promos():
    with db() as conn:
        return conn.execute("SELECT * FROM promos ORDER BY created_at DESC").fetchall()

def delete_promo(code):
    with db() as conn:
        conn.execute("DELETE FROM promos WHERE code=?", (code.upper(),))
        conn.commit()

# ---------- REVIEWS ----------
def add_review(uid, oid, rating, text):
    with db() as conn:
        conn.execute("INSERT INTO reviews (user_id,order_id,rating,text,created_at) VALUES (?,?,?,?,?)",
                     (uid, oid, rating, text, datetime.now().isoformat()))
        conn.commit()

def avg_rating(pid):
    with db() as conn:
        r = conn.execute("""SELECT AVG(r.rating) FROM reviews r
                            JOIN orders o ON o.id=r.order_id WHERE o.product_id=?""",
                         (pid,)).fetchone()
        return round(r[0], 1) if r and r[0] else None

# ============================================================
# HELPERS
# ============================================================

def is_admin(uid):
    return uid in ADMIN_IDS

def e(text):
    return html.escape(str(text))

def money(n):
    try:
        n = float(n)
        return f"{int(n)}" if n.is_integer() else f"{n:.2f}"
    except Exception:
        return str(n)

# ============================================================
# KEYBOARDS
# ============================================================

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Магазин", callback_data="shop")],
        [InlineKeyboardButton("👤 Профил", callback_data="profile")],
        [InlineKeyboardButton("📦 Фармоишҳои ман", callback_data="my_orders")],
        [InlineKeyboardButton("🎁 Реферал / Баланс", callback_data="ref")],
        [InlineKeyboardButton("ℹ️ Маълумот", callback_data="info")],
    ])

def shop_menu(is_admin_user=False):
    rows = [
        [InlineKeyboardButton("💎 Алмазҳо", callback_data="cat:diamond")],
        [InlineKeyboardButton("🎟 Ваучерҳо", callback_data="cat:voucher")],
        [InlineKeyboardButton("🎫 Pass / Elite", callback_data="cat:pass")],
        [InlineKeyboardButton("🔎 Ҷустуҷӯ", callback_data="search")],
    ]
    if is_admin_user:
        rows.append([InlineKeyboardButton("➕ Маҳсулоти нав", callback_data="admin:add_product")])
        rows.append([InlineKeyboardButton("🗑 Нест кардани маҳсулот", callback_data="admin:del_product")])
    rows.append([InlineKeyboardButton("⬅️ Меню", callback_data="menu")])
    return InlineKeyboardMarkup(rows)

def category_menu(cat):
    items = get_products(cat)
    rows = []
    for p in items:
        star = avg_rating(p["id"])
        label = f"{p['name']} — {money(p['price'])} с."
        if star:
            label += f" ⭐{star}"
        rows.append([InlineKeyboardButton(label, callback_data=f"buy:{p['id']}")])
    rows.append([InlineKeyboardButton("⬅️ Бозгашт", callback_data="shop")])
    return InlineKeyboardMarkup(rows)

def payment_keyboard(balance):
    rows = []
    if balance and balance > 0:
        rows.append([InlineKeyboardButton(
            f"💰 Аз баланс ({money(balance)} с.)", callback_data="pay:balance")])
    rows.append([InlineKeyboardButton("💳 Alif", callback_data="pay:alif")])
    rows.append([InlineKeyboardButton("💳 Dushanbe City", callback_data="pay:dc")])
    rows.append([InlineKeyboardButton("❌ Бекор", callback_data="cancel_order")])
    return InlineKeyboardMarkup(rows)

def cancel_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ Бекор", callback_data="cancel_order")]])

def order_action_keyboard(oid):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Тасдиқ", callback_data=f"order_done:{oid}"),
        InlineKeyboardButton("❌ Бекор", callback_data=f"order_cancel:{oid}"),
    ]])

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Фармоишҳо", callback_data="admin:orders")],
        [InlineKeyboardButton("👥 Корбарон", callback_data="admin:users")],
        [InlineKeyboardButton("💰 Нархҳо", callback_data="admin:prices")],
        [InlineKeyboardButton("➕ Илова маҳсулот", callback_data="admin:add_product")],
        [InlineKeyboardButton("🗑 Нест маҳсулот", callback_data="admin:del_product")],
        [InlineKeyboardButton("🎁 Промокодҳо", callback_data="admin:promos")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin:broadcast")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton("📁 Экспорт CSV", callback_data="admin:export")],
        [InlineKeyboardButton("⬅️ Меню", callback_data="menu")],
    ])

def admin_back():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Admin", callback_data="admin:menu")]])

def subscription_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Обуна шудан", url=CHANNEL_URL)],
        [InlineKeyboardButton("✅ Ман обуна шудам", callback_data="check_sub")],
    ])

# ============================================================
# SUBSCRIPTION
# ============================================================

async def is_subscribed(bot, uid):
    try:
        m = await bot.get_chat_member(f"@{CHANNEL_USERNAME}", uid)
        return str(m.status) in {"member", "administrator", "creator"}
    except TelegramError:
        return False

async def require_sub(update, context):
    user = update.effective_user
    if not user:
        return False
    if is_admin(user.id):
        return True
    if await is_subscribed(context.bot, user.id):
        return True

    txt = ("🔐 <b>Барои истифода бот ба канал обуна шавед.</b>\n\n"
           f"📢 @{e(CHANNEL_USERNAME)}")
    if update.callback_query:
        await update.callback_query.message.edit_text(
            txt, reply_markup=subscription_keyboard(), parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text(
            txt, reply_markup=subscription_keyboard(), parse_mode=ParseMode.HTML)
    return False

# ---- ҚИСМИ 1 ТАМОМ — идома дар Қисми 2 ----

# ============================================================
# DANATER FREE FIRE BOT — PART 2/3
# ============================================================

# ============================================================
# START
# ============================================================

async def start(update, context):
    user = update.effective_user
    if not user:
        return

    ref_id = None
    if context.args:
        try:
            ref_id = int(context.args[0])
            if ref_id == user.id:
                ref_id = None
        except ValueError:
            ref_id = None

    existing = get_user(user.id)

    if not existing and ref_id:
        save_user(user, referrer_id=ref_id)
        increment_referral(ref_id)
        try:
            await context.bot.send_message(
                chat_id=ref_id,
                text=("🎉 <b>Корбари нав тавассути ссылкаи шумо ворид шуд!</b>\n\n"
                      f"Ҳоло аз ҳар фармоиши ӯ <b>{REF_BONUS_PERCENT}%</b> "
                      "ба баланси шумо меравад."),
                parse_mode=ParseMode.HTML)
        except TelegramError:
            pass
    else:
        save_user(user)

    context.user_data.clear()

    if not await require_sub(update, context):
        return

    await update.message.reply_text(
        "🔥 <b>DANATER FREE FIRE</b>\n\n"
        "🛍️ <b>МАГАЗИНИ ОНЛАЙН</b>\n"
        "💎 Алмазҳо • Ваучерҳо • Pass\n\n"
        "Аз меню интихоб кунед 👇",
        reply_markup=main_menu(), parse_mode=ParseMode.HTML)


async def my_id(update, context):
    await update.message.reply_text(
        f"🆔 ID: <code>{update.effective_user.id}</code>",
        parse_mode=ParseMode.HTML)


async def promo_command(update, context):
    user = update.effective_user
    if not user:
        return
    if not context.args:
        await update.message.reply_text(
            "❌ Мисол: <code>/promo SALE10</code>", parse_mode=ParseMode.HTML)
        return
    code = context.args[0].upper()
    p = get_promo(code)
    if not p:
        await update.message.reply_text("❌ Промокод ёфт нашуд ё фаъол нест.")
        return
    if p["max_uses"] and p["used"] >= p["max_uses"]:
        await update.message.reply_text("❌ Промокод тамом шуд.")
        return
    context.user_data["promo"] = {
        "code": p["code"],
        "discount_percent": p["discount_percent"]
    }
    await update.message.reply_text(
        f"✅ Промокод <b>{e(p['code'])}</b> фаъол шуд (-{p['discount_percent']}%).",
        parse_mode=ParseMode.HTML)

# ============================================================
# USER CALLBACKS
# ============================================================

async def cb_menu(update, context):
    q = update.callback_query
    await q.answer()
    if not await require_sub(update, context):
        return
    await q.message.edit_text(
        "🔥 <b>DANATER FREE FIRE</b>\n\nАз меню интихоб кунед 👇",
        reply_markup=main_menu(), parse_mode=ParseMode.HTML)


async def cb_shop(update, context):
    q = update.callback_query
    await q.answer()
    if not await require_sub(update, context):
        return
    is_adm = is_admin(update.effective_user.id)
    await q.message.edit_text(
        "🛒 <b>МАГАЗИН</b>\n\nКатегорияро интихоб кунед:",
        reply_markup=shop_menu(is_adm), parse_mode=ParseMode.HTML)


async def cb_cat(update, context):
    q = update.callback_query
    await q.answer()
    if not await require_sub(update, context):
        return
    cat = q.data.split(":", 1)[1]
    if cat not in CATEGORIES:
        return
    await q.message.edit_text(
        f"<b>{CATEGORIES[cat]}</b>\n\nМаҳсулотро интихоб кунед:",
        reply_markup=category_menu(cat), parse_mode=ParseMode.HTML)


async def cb_buy(update, context):
    q = update.callback_query
    await q.answer()
    if not await require_sub(update, context):
        return

    pid = q.data.split(":", 1)[1]
    p = get_product(pid)
    if not p:
        await q.answer("Маҳсулот ёфт нашуд.", show_alert=True)
        return

    context.user_data.clear()
    context.user_data["product_id"] = pid
    context.user_data["state"] = "waiting_ffid"

    star = avg_rating(pid)
    star_line = f"\n⭐ Рейтинг: <b>{star}</b>/5" if star else ""

    await q.message.edit_text(
        "🛒 <b>ФАРМОИШ</b>\n\n"
        f"📦 {e(p['name'])}\n"
        f"💰 Нарх: <b>{money(p['price'])} сомонӣ</b>{star_line}\n\n"
        "🎮 <b>Free Fire ID-и худро фиристед:</b>\n"
        "Мисол: <code>123456789</code>",
        reply_markup=cancel_kb(), parse_mode=ParseMode.HTML)


async def cb_cancel(update, context):
    q = update.callback_query
    await q.answer("Бекор шуд.")
    context.user_data.clear()
    await q.message.edit_text("❌ <b>Бекор шуд.</b>",
                              reply_markup=main_menu(), parse_mode=ParseMode.HTML)


async def cb_pay(update, context):
    q = update.callback_query
    await q.answer()
    if not await require_sub(update, context):
        return

    user = update.effective_user
    method = q.data.split(":", 1)[1]
    pid = context.user_data.get("product_id")
    p = get_product(pid) if pid else None
    if not p:
        context.user_data.clear()
        await q.message.edit_text("❌ Сессия гузашт.", reply_markup=main_menu())
        return

    promo = context.user_data.get("promo")
    discount = 0
    if promo:
        discount = round(float(p["price"]) * promo["discount_percent"] / 100, 2)
    final = round(float(p["price"]) - discount, 2)

    # ---- 1) Харид бо баланс ----
    if method == "balance":
        u = get_user(user.id)
        if not u or (u["balance"] or 0) < final:
            await q.answer("❌ Баланс кофӣ нест.", show_alert=True)
            return

        deduct_balance(user.id, final)

        if promo:
            use_promo(promo["code"])

        customer_name = context.user_data.get("customer_name", "—")
        ffid = context.user_data.get("ffid", "—")

        order_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{user.id}"
        order = {
            "id": order_id, "user_id": user.id,
            "customer_name": customer_name, "free_fire_id": ffid,
            "product_id": pid, "product_name": p["name"],
            "price": float(p["price"]),
            "payment_method": "Баланс",
            "promo_code": promo["code"] if promo else None,
            "discount": discount, "final_price": final,
            "referred_by": (u["referrer_id"] if u else None),
            "created_at": datetime.now().isoformat(),
        }
        create_order(order)

        if u and u["referrer_id"]:
            bonus = give_referral_bonus(u["referrer_id"], final, REF_BONUS_PERCENT)
            if bonus > 0:
                try:
                    await context.bot.send_message(
                        chat_id=u["referrer_id"],
                        text=(f"💰 <b>+{money(bonus)} сомонӣ</b> ба баланси шумо!\n\n"
                              f"Аз фармоиши реферали шумо (<code>{user.id}</code>).\n"
                              f"Маблағи фармоиш: {money(final)} сомонӣ"),
                        parse_mode=ParseMode.HTML)
                except TelegramError:
                    pass

        await notify_admin_new_order(context, order, user)

        context.user_data.clear()
        await q.message.edit_text(
            "✅ <b>Фармоиши шумо қабул шуд!</b>\n\n"
            f"📦 {e(p['name'])}\n"
            f"💰 {money(final)} сомонӣ (аз баланс)\n"
            f"🧾 ID: <code>{order_id}</code>\n\n"
            "⏳ Администратор тасдиқ мекунад.",
            reply_markup=main_menu(), parse_mode=ParseMode.HTML)
        return

    # ---- 2/3) Alif ё DC ----
    method_name = "Alif" if method == "alif" else "Dushanbe City"
    number = ALIF_NUMBER if method == "alif" else DC_NUMBER

    context.user_data["payment_method"] = method_name
    context.user_data["final_price"] = final
    context.user_data["discount"] = discount
    context.user_data["state"] = "waiting_receipt"

    promo_line = ""
    if promo:
        promo_line = (f"\n🎁 Промокод: <b>{e(promo['code'])}</b> "
                      f"(-{promo['discount_percent']}%)\n"
                      f"💸 Танзиф: <b>{money(discount)} сомонӣ</b>")

    await q.message.edit_text(
        "💳 <b>ПАРДОХТ</b>\n\n"
        f"🏦 {method_name}\n"
        f"📱 Рақам: <code>{e(number)}</code>\n"
        f"💰 Маблағ: <b>{money(final)} сомонӣ</b>{promo_line}\n\n"
        "📸 Пас аз пардохт <b>расидро ҳамчун акс</b> фиристед.",
        reply_markup=cancel_kb(), parse_mode=ParseMode.HTML)


async def cb_my_orders(update, context):
    q = update.callback_query
    await q.answer()
    if not await require_sub(update, context):
        return

    orders = user_orders(update.effective_user.id, limit=10)
    if not orders:
        text = "📦 <b>ФАРМОИШҲОИ МАН</b>\n\nҲоло фармоиш надоред."
    else:
        lines = ["📦 <b>ФАРМОИШҲОИ МАН</b>\n"]
        st = {"pending": "⏳ Дар интизорӣ", "done": "✅ Тасдиқ шуд", "cancelled": "❌ Бекор шуд"}
        for o in orders:
            lines.append(
                f"🧾 <code>{e(o['id'])}</code>\n"
                f"📦 {e(o['product_name'])}\n"
                f"💰 {money(o['final_price'])} сомонӣ\n"
                f"📊 {st.get(o['status'], o['status'])}\n")
        text = "\n".join(lines)

    await q.message.edit_text(text, reply_markup=main_menu(), parse_mode=ParseMode.HTML)


async def cb_profile(update, context):
    q = update.callback_query
    await q.answer()
    if not await require_sub(update, context):
        return

    user = update.effective_user
    u = get_user(user.id)
    if not u:
        await q.message.edit_text("❌ Профил ёфт нашуд.")
        return

    bal = u["balance"] or 0
    refs = u["referred_count"] or 0
    ref_earned = referral_earned(user.id, REF_BONUS_PERCENT)

    orders = user_orders(user.id, limit=1000)
    total_orders = len(orders)
    done_orders = len([o for o in orders if o["status"] == "done"])
    total_spent = sum(float(o["final_price"] or 0) for o in orders if o["status"] == "done")

    username = f"@{user.username}" if user.username else "—"
    name = user.first_name or "—"

    text = (
        "👤 <b>ПРОФИЛИ ШУМО</b>\n\n"
        f"📛 Ном: <b>{e(name)}</b>\n"
        f"📱 Username: {e(username)}\n"
        f"🆔 ID: <code>{user.id}</code>\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Баланс:</b> {money(bal)} сомонӣ\n"
        f"👥 <b>Рефералҳо:</b> {refs}\n"
        f"🎁 <b>Аз рефералҳо коркард:</b> {money(ref_earned)} сомонӣ\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📦 Ҳама фармоишҳо: <b>{total_orders}</b>\n"
        f"✅ Тасдиқшуда: <b>{done_orders}</b>\n"
        f"💸 Ҳамагӣ хароҷот: <b>{money(total_spent)} сомонӣ</b>\n"
        f"🎁 Бонус аз ҳар фармоиш: <b>{REF_BONUS_PERCENT}%</b>"
    )

    await q.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎁 Реферал / Ҳавола", callback_data="ref")],
            [InlineKeyboardButton("📦 Фармоишҳои ман", callback_data="my_orders")],
            [InlineKeyboardButton("⬅️ Меню", callback_data="menu")],
        ]),
        parse_mode=ParseMode.HTML)


async def cb_ref(update, context):
    q = update.callback_query
    await q.answer()
    if not await require_sub(update, context):
        return

    uid = update.effective_user.id
    me = await context.bot.get_me()
    link = f"https://t.me/{me.username}?start={uid}"
    u = get_user(uid)
    bal = u["balance"] if u else 0
    cnt = u["referred_count"] if u else 0

    await q.message.edit_text(
        "🎁 <b>РЕФЕРАЛЬНАЯ СИСТЕМА</b>\n\n"
        f"Аз ҳар фармоиши рефералҳои шумо <b>{REF_BONUS_PERCENT}%</b> "
        "ба баланси шумо меравад.\n\n"
        f"🔗 <b>Ҳаволаи шумо:</b>\n<code>{link}</code>\n\n"
        f"👥 Рефералҳо: <b>{cnt}</b>\n"
        f"💰 Баланси шумо: <b>{money(bal)} сомонӣ</b>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Отправить ссылку", callback_data="ref_share")],
            [InlineKeyboardButton("⬅️ Меню", callback_data="menu")],
        ]),
        parse_mode=ParseMode.HTML)


async def cb_ref_share(update, context):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    me = await context.bot.get_me()
    link = f"https://t.me/{me.username}?start={uid}"
    share = f"https://t.me/share/url?url={link}&text=DANATER+Free+Fire+магазин"
    await q.message.edit_text(
        "📤 <b>ОТПРАВИТЬ ССЫЛКУ</b>\n\n"
        "Ҳаволаро ба дӯстон фиристед ва аз ҳар фармоиши онҳо "
        f"<b>{REF_BONUS_PERCENT}%</b> ба баланси шумо меравад!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Отправить ссылку", url=share)],
            [InlineKeyboardButton("⬅️ Бозгашт", callback_data="ref")],
        ]),
        parse_mode=ParseMode.HTML)


async def cb_info(update, context):
    q = update.callback_query
    await q.answer()
    if not await require_sub(update, context):
        return

    await q.message.edit_text(
        "ℹ️ <b>DANATER FREE FIRE</b>\n\n"
        f"👨‍💼 <b>Админ:</b> @{e(ADMIN_USERNAME)}\n"
        f"📱 <b>WhatsApp:</b> {e(WHATSAPP_NUMBER)}\n\n"
        "❓ Барои саволҳо ба админ нависед.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 WhatsApp", url=WHATSAPP_URL)],
            [InlineKeyboardButton("📸 Instagram", url=INSTAGRAM_URL)],
            [InlineKeyboardButton("✈️ Telegram", url=TELEGRAM_ADMIN_URL)],
            [InlineKeyboardButton("⬅️ Бозгашт", callback_data="menu")],
        ]),
        parse_mode=ParseMode.HTML)


# ============================================================
# ORDER NOTIFY
# ============================================================

async def notify_admin_new_order(context, order, user):
    username = f"@{user.username}" if user.username else "username надорад"
    ref_line = f"\n🎁 Реферал аз: <code>{order['referred_by']}</code>" if order.get("referred_by") else ""
    promo_line = ""
    if order.get("promo_code"):
        promo_line = f"\n🎟 Промокод: <b>{e(order['promo_code'])}</b> (-{order['discount']} с.)"

    text = (
        "🆕 <b>ФАРМОИШИ НАВ</b>\n\n"
        f"🧾 ID: <code>{e(order['id'])}</code>\n"
        f"📦 {e(order['product_name'])}\n"
        f"💰 Маблағ: <b>{money(order['final_price'])} сомонӣ</b>\n"
        f"🎮 FF ID: <code>{e(order['free_fire_id'])}</code>\n"
        f"👤 Ном: <b>{e(order['customer_name'])}</b>\n"
        f"📱 {e(username)}\n"
        f"🆔 TG ID: <code>{user.id}</code>\n"
        f"💳 {e(order['payment_method'])}{promo_line}{ref_line}"
    )

    kb = order_action_keyboard(order["id"])
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id, text=text, reply_markup=kb,
                parse_mode=ParseMode.HTML)
        except TelegramError as ex:
            logger.error("Admin notify failed: %s", ex)


# ============================================================
# TEXT HANDLER
# ============================================================

async def handle_text(update, context):
    user = update.effective_user
    if not user:
        return

    save_user(user)
    state = context.user_data.get("state")

    # ADMIN: edit price
    if is_admin(user.id) and state == "edit_price":
        pid = context.user_data.get("edit_price_id")
        raw = update.message.text.strip()
        if not raw.isdigit():
            await update.message.reply_text("❌ Танҳо рақам.")
            return
        price = int(raw)
        if price < 0 or price > 1000000:
            await update.message.reply_text("❌ Нарх нодуруст.")
            return
        update_price(pid, price)
        context.user_data.clear()
        await update.message.reply_text(
            f"✅ Нархи нав: <b>{price} сомонӣ</b>",
            reply_markup=admin_menu(), parse_mode=ParseMode.HTML)
        return

    # ADMIN: broadcast
    if is_admin(user.id) and state == "broadcast":
        text = update.message.text.strip()
        if not text:
            return
        context.user_data.clear()
        ids = all_user_ids()
        sent, failed = 0, 0
        await update.message.reply_text("📢 Рассылка оғоз шуд...")
        for uid in ids:
            try:
                await context.bot.send_message(chat_id=uid, text=text, parse_mode=ParseMode.HTML)
                sent += 1
            except TelegramError:
                failed += 1
        await update.message.reply_text(
            f"📢 Анҷом:\n✅ {sent}\n❌ {failed}",
            parse_mode=ParseMode.HTML)
        return

    # ADMIN: promo new
    if is_admin(user.id) and state == "promo_new":
        parts = update.message.text.strip().split()
        if len(parts) < 2:
            await update.message.reply_text("❌ Формат: КОД ПРОЦЕНТ [МАКС]")
            return
        try:
            code = parts[0].upper()
            percent = int(parts[1])
            max_uses = int(parts[2]) if len(parts) > 2 else 0
            if not (1 <= percent <= 90):
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Рақамҳо нодуруст.")
            return
        create_promo(code, percent, max_uses)
        context.user_data.clear()
        await update.message.reply_text(
            f"✅ Промокод <b>{e(code)}</b> илова шуд ({percent}%).",
            reply_markup=admin_menu(), parse_mode=ParseMode.HTML)
        return

    # ADMIN: add product
    if is_admin(user.id) and state == "add_product":
        raw = update.message.text.strip()
        parts = [x.strip() for x in raw.split("|")]
        if len(parts) != 4:
            await update.message.reply_text(
                "❌ Формат: <code>ID | НОМ | НАРХ | КАТЕГОРИЯ</code>",
                parse_mode=ParseMode.HTML)
            return
        pid, name, price_s, cat = parts
        if cat not in CATEGORIES:
            await update.message.reply_text(
                "❌ Категория нодуруст: diamond / voucher / pass")
            return
        try:
            price = float(price_s)
            if price <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Нарх нодуруст.")
            return
        add_product(pid, name, price, cat)
        context.user_data.clear()
        await update.message.reply_text(
            f"✅ Маҳсулоти нав илова шуд!\n\n"
            f"📦 {e(name)}\n"
            f"💰 {money(price)} сомонӣ\n"
            f"📂 {CATEGORIES[cat]}",
            reply_markup=admin_menu(), parse_mode=ParseMode.HTML)
        return

    # USER: search
    if state == "search":
        query = update.message.text.strip()
        context.user_data.pop("state", None)
        results = search_products(query)
        if not results:
            await update.message.reply_text(
                "❌ Ҳеҷ чиз ёфт нашуд.", reply_markup=shop_menu())
            return
        rows = []
        for p in results[:20]:
            rows.append([InlineKeyboardButton(
                f"{p['name']} — {money(p['price'])} с.",
                callback_data=f"buy:{p['id']}")])
        rows.append([InlineKeyboardButton("⬅️ Бозгашт", callback_data="shop")])
        await update.message.reply_text(
            f"🔎 Натиҷа барои «{e(query)}»:",
            reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML)
        return

    if not await require_sub(update, context):
        return

    # USER: FF ID
    if state == "waiting_ffid":
        ffid = update.message.text.strip()
        if not ffid.isdigit() or not (5 <= len(ffid) <= 20):
            await update.message.reply_text("❌ FF ID нодуруст. Танҳо рақам.")
            return
        context.user_data["ffid"] = ffid
        context.user_data["state"] = "waiting_name"
        await update.message.reply_text(
            "👤 <b>Номи худро фиристед:</b>\nМисол: Ysuf",
            parse_mode=ParseMode.HTML)
        return

    # USER: name
    if state == "waiting_name":
        name = update.message.text.strip()
        if not (2 <= len(name) <= 100):
            await update.message.reply_text("❌ Ном нодуруст.")
            return
        context.user_data["customer_name"] = name
        context.user_data["state"] = "waiting_payment"
        u = get_user(user.id)
        bal = u["balance"] if u else 0
        await update.message.reply_text(
            "💳 <b>Усули пардохтро интихоб кунед:</b>\n\n"
            "3 усул:\n"
            "1️⃣ 💰 Аз баланс\n"
            "2️⃣ 💳 Alif\n"
            "3️⃣ 💳 Dushanbe City",
            reply_markup=payment_keyboard(bal), parse_mode=ParseMode.HTML)
        return


# ============================================================
# PHOTO HANDLER (receipt)
# ============================================================

async def handle_photo(update, context):
    user = update.effective_user
    if not user:
        return
    save_user(user)

    if not await require_sub(update, context):
        return

    if context.user_data.get("state") != "waiting_receipt":
        await update.message.reply_text(
            "ℹ️ Аввал маҳсулотро интихоб кунед.", reply_markup=main_menu())
        return

    pid = context.user_data.get("product_id")
    ffid = context.user_data.get("ffid")
    cname = context.user_data.get("customer_name")
    pm = context.user_data.get("payment_method")
    final = context.user_data.get("final_price")
    discount = context.user_data.get("discount", 0)
    promo = context.user_data.get("promo")

    p = get_product(pid) if pid else None
    if not p or not ffid or not cname or not pm:
        context.user_data.clear()
        await update.message.reply_text(
            "❌ Сессия гузашт.", reply_markup=main_menu())
        return

    u = get_user(user.id)
    referred_by = u["referrer_id"] if u else None

    order_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{user.id}"
    order = {
        "id": order_id, "user_id": user.id,
        "customer_name": cname, "free_fire_id": ffid,
        "product_id": pid, "product_name": p["name"],
        "price": float(p["price"]), "payment_method": pm,
        "promo_code": promo["code"] if promo else None,
        "discount": discount, "final_price": final,
        "referred_by": referred_by,
        "created_at": datetime.now().isoformat(),
    }
    create_order(order)

    if promo:
        use_promo(promo["code"])

    if referred_by:
        bonus = give_referral_bonus(referred_by, final, REF_BONUS_PERCENT)
        if bonus > 0:
            try:
                await context.bot.send_message(
                    chat_id=referred_by,
                    text=(f"💰 <b>+{money(bonus)} сомонӣ</b> ба баланси шумо!\n\n"
                          f"Аз фармоиши реферали шумо (<code>{user.id}</code>).\n"
                          f"Маблағи фармоиш: {money(final)} сомонӣ"),
                    parse_mode=ParseMode.HTML)
            except TelegramError:
                pass

    username = f"@{user.username}" if user.username else "username надорад"
    ref_line = f"\n🎁 Реферал аз: <code>{referred_by}</code>" if referred_by else ""
    promo_line = f"\n🎟 Промокод: <b>{e(promo['code'])}</b> (-{money(discount)} с.)" if promo else ""

    admin_text = (
        "🆕 <b>ФАРМОИШИ НАВ</b>\n\n"
        f"🧾 ID: <code>{order_id}</code>\n"
        f"📦 {e(p['name'])}\n"
        f"💰 Маблағ: <b>{money(final)} сомонӣ</b>\n"
        f"🎮 FF ID: <code>{e(ffid)}</code>\n"
        f"👤 Ном: <b>{e(cname)}</b>\n"
        f"📱 {e(username)}\n"
        f"🆔 TG ID: <code>{user.id}</code>\n"
        f"💳 {e(pm)}{promo_line}{ref_line}"
    )
    kb = order_action_keyboard(order_id)
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=update.message.photo[-1].file_id,
                caption=admin_text, reply_markup=kb,
                parse_mode=ParseMode.HTML)
        except TelegramError as ex:
            logger.error("Admin photo notify failed: %s", ex)

    context.user_data.clear()
    await update.message.reply_text(
        "✅ <b>Фармоиши шумо қабул шуд!</b>\n\n"
        f"📦 {e(p['name'])}\n"
        f"💰 {money(final)} сомонӣ\n"
        f"🧾 ID: <code>{order_id}</code>\n\n"
        "⏳ Администратор расидро месанҷад.",
        reply_markup=main_menu(), parse_mode=ParseMode.HTML)



# ============================================================
# DANATER FREE FIRE BOT — PART 3/3
# ============================================================

# ============================================================
# ADMIN PANEL
# ============================================================

async def admin_command(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Дастрасӣ нест.")
        return
    await update.message.reply_text(
        "🛠️ <b>ADMIN PANEL</b>",
        reply_markup=admin_menu(), parse_mode=ParseMode.HTML)


async def admin_callback(update, context):
    q = update.callback_query
    if not is_admin(update.effective_user.id):
        await q.answer("⛔", show_alert=True)
        return

    data = q.data

    if data == "admin:menu":
        await q.answer()
        await q.message.edit_text("🛠️ <b>ADMIN PANEL</b>",
                                  reply_markup=admin_menu(), parse_mode=ParseMode.HTML)
        return

    if data == "admin:prices":
        await q.answer()
        prods = get_products()
        buttons = []
        for p in prods:
            buttons.append([InlineKeyboardButton(
                f"{p['name']} — {money(p['price'])} с.",
                callback_data=f"price:{p['id']}")])
        buttons.append([InlineKeyboardButton("⬅️ Admin", callback_data="admin:menu")])
        await q.message.edit_text(
            "💰 <b>ИВАЗ КАРДАНИ НАРХ</b>\n\nМаҳсулотро интихоб кунед:",
            reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    if data.startswith("price:"):
        await q.answer()
        pid = data.split(":", 1)[1]
        p = get_product(pid)
        if not p:
            return
        context.user_data["state"] = "edit_price"
        context.user_data["edit_price_id"] = pid
        await q.message.edit_text(
            f"💰 <b>ИВАЗ КАРДАНИ НАРХ</b>\n\n"
            f"📦 {e(p['name'])}\n"
            f"💵 Ҳозира: <b>{money(p['price'])} сомонӣ</b>\n\n"
            "Нархи навро бо рақам фиристед:",
            reply_markup=admin_back(), parse_mode=ParseMode.HTML)
        return

    if data == "admin:add_product":
        await q.answer()
        context.user_data["state"] = "add_product"
        await q.message.edit_text(
            "➕ <b>МАҲСУЛОТИ НАВ</b>\n\n"
            "Формат:\n"
            "<code>ID | НОМ | НАРХ | КАТЕГОРИЯ</code>\n\n"
            "Категорияҳо: <code>diamond</code>, <code>voucher</code>, <code>pass</code>\n\n"
            "Мисол:\n"
            "<code>m500 | 💎 500 алмаз | 45 | diamond</code>",
            reply_markup=admin_back(), parse_mode=ParseMode.HTML)
        return

    if data == "admin:del_product":
        await q.answer()
        prods = all_products_admin()
        rows = []
        for p in prods:
            status = "🟢" if p["active"] else "🔴"
            rows.append([InlineKeyboardButton(
                f"{status} {p['name']} — {money(p['price'])} с.",
                callback_data=f"delprod:{p['id']}")])
        rows.append([InlineKeyboardButton("⬅️ Admin", callback_data="admin:menu")])
        await q.message.edit_text(
            "🗑 <b>НЕСТ КАРДАНИ МАҲСУЛОТ</b>\n\nМаҳсулотро интихоб кунед:",
            reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML)
        return

    if data.startswith("delprod:"):
        pid = data.split(":", 1)[1]
        delete_product(pid)
        await q.answer("✅ Нест шуд.", show_alert=True)
        prods = all_products_admin()
        rows = []
        for p in prods:
            status = "🟢" if p["active"] else "🔴"
            rows.append([InlineKeyboardButton(
                f"{status} {p['name']} — {money(p['price'])} с.",
                callback_data=f"delprod:{p['id']}")])
        rows.append([InlineKeyboardButton("⬅️ Admin", callback_data="admin:menu")])
        await q.message.edit_text(
            "🗑 <b>НЕСТ КАРДАНИ МАҲСУЛОТ</b>",
            reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML)
        return

    if data == "admin:users":
        await q.answer()
        users = all_users_detailed(50)
        if not users:
            text = "👥 Корбарон нест."
        else:
            lines = [f"👥 <b>КОРБАРОН</b> ({users_count()} ҳамагӣ)\n"]
            for u in users:
                uname = f"@{u['username']}" if u["username"] else "—"
                lines.append(
                    f"🆔 <code>{u['id']}</code> | {e(uname)}\n"
                    f"   👤 {e(u['first_name'] or '—')}\n"
                    f"   💰 {money(u['balance'])} с. | 👥 {u['referred_count']}\n")
            text = "\n".join(lines)
        await q.message.edit_text(text, reply_markup=admin_back(), parse_mode=ParseMode.HTML)
        return

    if data == "admin:stats":
        await q.answer()
        s = orders_stats()
        await q.message.edit_text(
            "📊 <b>СТАТИСТИКА</b>\n\n"
            f"👥 Корбарон: <b>{users_count()}</b>\n"
            f"📦 Ҳама фармоишҳо: <b>{s['total']}</b>\n"
            f"⏳ Интизорӣ: <b>{s['pending']}</b>\n"
            f"✅ Тасдиқ: <b>{s['done']}</b>\n"
            f"❌ Бекор: <b>{s['cancelled']}</b>\n"
            f"💰 Даромад: <b>{money(s['revenue'])} сомонӣ</b>",
            reply_markup=admin_back(), parse_mode=ParseMode.HTML)
        return

    if data == "admin:orders":
        await q.answer()
        orders = all_orders(15)
        if not orders:
            text = "📦 Фармоиш нест."
        else:
            lines = ["📦 <b>ОХИРИН ФАРМОИШҲО</b>\n"]
            for o in orders:
                ref = f" | 🎁 {o['referred_by']}" if o["referred_by"] else ""
                lines.append(
                    f"🧾 <code>{e(o['id'])}</code>\n"
                    f"📦 {e(o['product_name'])}\n"
                    f"💰 {money(o['final_price'])} с. | {e(o['status'])}\n"
                    f"🎮 <code>{e(o['free_fire_id'])}</code>\n"
                    f"🆔 {o['user_id']}{ref}\n")
            text = "\n".join(lines)
        await q.message.edit_text(text, reply_markup=admin_back(), parse_mode=ParseMode.HTML)
        return

    if data == "admin:export":
        await q.answer()
        buf = export_orders_csv()
        fname = f"orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        try:
            await context.bot.send_document(
                chat_id=update.effective_user.id,
                document=io.BytesIO(buf.getvalue().encode("utf-8")),
                filename=fname,
                caption=f"📁 Экспорти фармоишҳо ({fname})")
        except TelegramError as ex:
            logger.error("CSV send failed: %s", ex)
        return

    if data == "admin:broadcast":
        await q.answer()
        context.user_data["state"] = "broadcast"
        await q.message.edit_text(
            "📢 <b>РАССЫЛКА</b>\n\nМатнро фиристед:",
            reply_markup=admin_back(), parse_mode=ParseMode.HTML)
        return

    if data == "admin:promos":
        await q.answer()
        promos = all_promos()
        rows = [[InlineKeyboardButton("➕ Промокод илова", callback_data="promo:new")]]
        for p in promos:
            status = "🟢" if p["active"] else "🔴"
            rows.append([InlineKeyboardButton(
                f"{status} {p['code']} — {p['discount_percent']}% "
                f"({p['used']}/{p['max_uses'] or '∞'})",
                callback_data=f"promo:view:{p['code']}")])
        rows.append([InlineKeyboardButton("⬅️ Admin", callback_data="admin:menu")])
        await q.message.edit_text(
            "🎁 <b>ПРОМОКОДҲО</b>\n\nИнтихоб кунед ё нав илова кунед:",
            reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML)
        return

    if data == "promo:new":
        await q.answer()
        context.user_data["state"] = "promo_new"
        await q.message.edit_text(
            "🎁 <b>ПРОМОКОДИ НАВ</b>\n\n"
            "Формат:\n<code>КОД ПРОЦЕНТ [МАКС_ИСТИФОДА]</code>\n\n"
            "Мисол:\n"
            "<code>SALE10 10</code>  ← 10%, бемаҳдуд\n"
            "<code>NEW20 20 100</code>  ← 20%, 100 маротиба",
            reply_markup=admin_back(), parse_mode=ParseMode.HTML)
        return

    if data.startswith("promo:view:"):
        await q.answer()
        code = data.split(":", 2)[2]
        p = get_promo(code)
        if not p:
            await q.message.edit_text("❌ Ёфт нашуд.")
            return
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 Нест кардан", callback_data=f"promo:del:{code}")],
            [InlineKeyboardButton("⬅️ Бозгашт", callback_data="admin:promos")],
        ])
        await q.message.edit_text(
            f"🎁 <b>ПРОМОКОД: {e(p['code'])}</b>\n\n"
            f"💸 Танзиф: <b>{p['discount_percent']}%</b>\n"
            f"📊 Истифода: <b>{p['used']}/{p['max_uses'] or '∞'}</b>",
            reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    if data.startswith("promo:del:"):
        code = data.split(":", 2)[2]
        delete_promo(code)
        await q.answer("Нест шуд.", show_alert=True)
        promos = all_promos()
        rows = [[InlineKeyboardButton("➕ Промокод илова", callback_data="promo:new")]]
        for p in promos:
            status = "🟢" if p["active"] else "🔴"
            rows.append([InlineKeyboardButton(
                f"{status} {p['code']} — {p['discount_percent']}% "
                f"({p['used']}/{p['max_uses'] or '∞'})",
                callback_data=f"promo:view:{p['code']}")])
        rows.append([InlineKeyboardButton("⬅️ Admin", callback_data="admin:menu")])
        await q.message.edit_text(
            "🎁 <b>ПРОМОКОДҲО</b>",
            reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML)
        return

    if data.startswith("order_done:") or data.startswith("order_cancel:"):
        await q.answer()
        action, oid = data.split(":", 1)
        o = get_order(oid)
        if not o:
            await q.message.reply_text("❌ Фармоиш ёфт нашуд.")
            return
        if action == "order_done":
            update_order_status(oid, "done")
            user_text = (f"✅ <b>Фармоиши шумо тасдиқ шуд!</b>\n\n"
                         f"📦 {e(o['product_name'])}\n"
                         f"🧾 <code>{e(oid)}</code>")
            admin_text = "✅ Тасдиқ шуд."
        else:
            update_order_status(oid, "cancelled")
            user_text = (f"❌ <b>Фармоиши шумо бекор шуд.</b>\n\n"
                         f"🧾 <code>{e(oid)}</code>")
            admin_text = "❌ Бекор шуд."

        try:
            await context.bot.send_message(
                chat_id=int(o["user_id"]), text=user_text, parse_mode=ParseMode.HTML)
        except TelegramError as ex:
            logger.warning("User notify failed: %s", ex)

        try:
            await q.message.edit_reply_markup(reply_markup=None)
        except TelegramError:
            pass
        await q.message.reply_text(admin_text)
        return


# ============================================================
# CALLBACK ROUTER
# ============================================================

async def callback_router(update, context):
    q = update.callback_query
    data = q.data or ""

    if data == "check_sub":
        await q.answer("Санҷида истодаам...")
        if await is_subscribed(context.bot, update.effective_user.id):
            await cb_menu(update, context)
        else:
            await q.message.edit_text(
                "❌ Шумо ҳоло обуна нашудаед.",
                reply_markup=subscription_keyboard(), parse_mode=ParseMode.HTML)
        return

    if data == "menu":
        await cb_menu(update, context)
    elif data == "shop":
        await cb_shop(update, context)
    elif data.startswith("cat:"):
        await cb_cat(update, context)
    elif data.startswith("buy:"):
        await cb_buy(update, context)
    elif data == "cancel_order":
        await cb_cancel(update, context)
    elif data.startswith("pay:"):
        await cb_pay(update, context)
    elif data == "my_orders":
        await cb_my_orders(update, context)
    elif data == "profile":
        await cb_profile(update, context)
    elif data == "ref":
        await cb_ref(update, context)
    elif data == "ref_share":
        await cb_ref_share(update, context)
    elif data == "info":
        await cb_info(update, context)
    elif data == "search":
        await q.answer()
        if not await require_sub(update, context):
            return
        context.user_data["state"] = "search"
        await q.message.edit_text(
            "🔎 Номи маҳсулотро нависед:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Бозгашт", callback_data="shop")]]),
            parse_mode=ParseMode.HTML)
    elif (data.startswith("admin:") or data.startswith("price:")
          or data.startswith("promo:") or data.startswith("order_")
          or data.startswith("delprod:")):
        await admin_callback(update, context)
    else:
        await q.answer("Ин амал дастгирӣ намешавад.", show_alert=True)


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(update, context):
    logger.exception("Unhandled: %s", context.error)


# ============================================================
# FLASK
# ============================================================

flask_app = Flask(__name__)

@flask_app.get("/")
def home():
    return "DANATER FREE FIRE is running", 200

@flask_app.get("/health")
def health():
    return {"status": "ok"}, 200

def run_web():
    flask_app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)


# ============================================================
# STARTUP
# ============================================================

async def post_init(application):
    try:
        await application.bot.delete_webhook(drop_pending_updates=False)
        me = await application.bot.get_me()
        logger.info("Bot: @%s | ID=%s", me.username, me.id)
    except TelegramError as ex:
        logger.error("Startup error: %s", ex)
        raise


def main():
    if not TOKEN:
        raise RuntimeError("TOKEN лозим аст.")
    if not ADMIN_IDS:
        logger.warning("ADMIN_IDS холӣ аст!")

    init_db()
    seed_products()

    Thread(target=run_web, daemon=True).start()

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", my_id))
    app.add_handler(CommandHandler("promo", promo_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)

    logger.info("🔥 DANATER bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)


if __name__ == "__main__":
    main()
# ============================================================
# END OF FILE
# ============================================================
