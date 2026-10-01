# ============================================================
# DANATER SHOP BOT — NEON ULTRA FAST & FULL EDITION (FIXED)
# ============================================================

import os
import html
import hashlib
import logging
import time
import asyncio
from datetime import datetime

from psycopg_pool import AsyncConnectionPool
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# ============================================================
# ТАНЗИМОТ
# ============================================================
TOKEN = os.getenv("TOKEN", "").strip()
ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

ADMIN_USERNAME       = os.getenv("ADMIN_USERNAME", "ffxdavlatov").lstrip("@")
CHANNEL_USERNAME     = os.getenv("CHANNEL_USERNAME", "otzivi_danater1").lstrip("@")
CHANNEL_URL          = f"https://t.me/{CHANNEL_USERNAME}"

ALIF_NUMBER          = os.getenv("ALIF_NUMBER", "+992917003888")
DC_NUMBER            = os.getenv("DC_NUMBER", "+992783836464")

INSTAGRAM_URL        = os.getenv("INSTAGRAM_URL", "https://www.instagram.com/danatershop.tj")
SUPPORT_BOT_USERNAME = os.getenv("SUPPORT_BOT_USERNAME", "DanaterShopSupportBot").lstrip("@")

DATABASE_URL         = os.getenv("DATABASE_URL", "").strip()
REF_BONUS_PERCENT    = 5

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("DANATER")

# ============================================================
# SPEED CACHE (КЭШИ СУРЪАТИ БАЛАНД)
# ============================================================
_SUB_CACHE = {}
_SUB_CACHE_TTL = 900  # 15 дақиқа

_PRODUCT_CACHE = {}
_PRODUCT_CACHE_TTL = 300  # 5 дақиқа

pool = None

async def init_db_pool():
    global pool
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL мавҷуд нест!")
    pool = AsyncConnectionPool(conninfo=DATABASE_URL, min_size=2, max_size=10, open=False)
    await pool.open()
    logger.info("⚡ Async PostgreSQL Pool бомуваффақият кушода шуд!")

# ============================================================
# МАҲСУЛОТҲОИ ПЕШФАРЗ
# ============================================================
DEFAULT_PRODUCTS = {
    "110":   {"name": "💎 110 алмаз",     "price": 10,  "category": "diamond"},
    "341":   {"name": "💎 341 алмаз",     "price": 28, "category": "diamond"},
    "572":   {"name": "💎 572 алмаз",     "price": 45, "category": "diamond"},
    "1166":  {"name": "💎 1166 алмаз",    "price": 99, "category": "diamond"},
    "2398":  {"name": "💎 2398 алмаз",    "price": 190, "category": "diamond"},
    "6160":  {"name": "💎 6160 алмаз",    "price": 550,    "category": "diamond"},
    "week":  {"name": "🎟 Ваучер 1 ҳафта", "price": 18,     "category": "voucher"},
    "month": {"name": "🎟 Ваучер 1 моҳ",  "price": 95,     "category": "voucher"},
    "lite":  {"name": "🎟 Ваучер Лайт",  "price": 7,      "category": "voucher"},
    "elite": {"name": "🎫 Elite Pass",    "price": 120,    "category": "pass"},
    "booyah":{"name": "🎫 Booyah Pass",   "price": 60,     "category": "pass"},
}

CATEGORIES = {
    "diamond": "💎 Алмазҳо",
    "voucher": "🎟 Ваучерҳо",
    "pass":    "🎫 Pass / Elite",
}

# ============================================================
# HELPERS
# ============================================================
def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

def e(text) -> str:
    return html.escape(str(text))

def money(n) -> str:
    try:
        n = float(n)
        return f"{int(n)}" if n.is_integer() else f"{n:.2f}"
    except Exception:
        return str(n)

# ============================================================
# DATABASE FUNCTIONS
# ============================================================
async def init_db():
    async with pool.connection() as conn:
        async with conn.cursor() as c:
            await c.execute("""CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY, username TEXT, first_name TEXT,
                balance DOUBLE PRECISION DEFAULT 0, referrer_id BIGINT, referred_count INTEGER DEFAULT 0,
                joined_at TEXT)""")
            
            await c.execute("""CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, price DOUBLE PRECISION NOT NULL,
                category TEXT NOT NULL, active INTEGER DEFAULT 1)""")
            
            await c.execute("""CREATE TABLE IF NOT EXISTS accounts (
                id SERIAL PRIMARY KEY, title TEXT NOT NULL, price DOUBLE PRECISION NOT NULL,
                details TEXT, active INTEGER DEFAULT 1)""")
            
            await c.execute("""CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY, user_id BIGINT, customer_name TEXT, free_fire_id TEXT,
                product_id TEXT, product_name TEXT, price DOUBLE PRECISION, payment_method TEXT,
                promo_code TEXT, final_price DOUBLE PRECISION, status TEXT DEFAULT 'pending', created_at TEXT)""")
            
            await c.execute("""CREATE TABLE IF NOT EXISTS promos (
                code TEXT PRIMARY KEY, discount_percent INTEGER NOT NULL,
                max_uses INTEGER DEFAULT 100, used INTEGER DEFAULT 0, active INTEGER DEFAULT 1)""")
            
            for pid, pdata in DEFAULT_PRODUCTS.items():
                await c.execute(
                    "INSERT INTO products (id, name, price, category, active) VALUES (%s, %s, %s, %s, 1) ON CONFLICT (id) DO NOTHING",
                    (pid, pdata["name"], pdata["price"], pdata["category"])
                )
            await conn.commit()

async def get_or_create_user(user, referrer_id=None):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with pool.connection() as conn:
        async with conn.cursor() as c:
            await c.execute("SELECT id, username, first_name, balance, referrer_id, referred_count FROM users WHERE id=%s", (user.id,))
            row = await c.fetchone()
            if row:
                return {"id": row[0], "username": row[1], "first_name": row[2], "balance": row[3], "referrer_id": row[4], "referred_count": row[5]}
            
            ref_id = referrer_id if (referrer_id and referrer_id != user.id) else None
            await c.execute(
                "INSERT INTO users (id, username, first_name, balance, referrer_id, joined_at) VALUES (%s, %s, %s, 0, %s, %s)",
                (user.id, user.username, user.first_name, ref_id, now_str)
            )
            if ref_id:
                await c.execute("UPDATE users SET referred_count = referred_count + 1 WHERE id=%s", (ref_id,))
            await conn.commit()
            return {"id": user.id, "username": user.username, "first_name": user.first_name, "balance": 0, "referrer_id": ref_id, "referred_count": 0}

async def get_products_by_category(category):
    async with pool.connection() as conn:
        async with conn.cursor() as c:
            await c.execute("SELECT id, name, price, category FROM products WHERE category=%s AND active=1 ORDER BY price ASC", (category,))
            rows = await c.fetchall()
            return [{"id": r[0], "name": r[1], "price": r[2], "category": r[3]} for r in rows]

async def get_product_fast(pid):
    now = time.monotonic()
    cached = _PRODUCT_CACHE.get(pid)
    if cached and (now - cached[0]) < _PRODUCT_CACHE_TTL:
        return cached[1]
    
    async with pool.connection() as conn:
        async with conn.cursor() as c:
            await c.execute("SELECT id, name, price, category FROM products WHERE id=%s AND active=1", (pid,))
            row = await c.fetchone()
            if row:
                res = {"id": row[0], "name": row[1], "price": row[2], "category": row[3]}
                _PRODUCT_CACHE[pid] = (now, res)
                return res
    return None

# ============================================================
# SUBSCRIPTION CHECK
# ============================================================
async def is_subscribed(bot, uid, force=False):
    now = time.monotonic()
    if not force:
        cached_at = _SUB_CACHE.get(uid)
        if cached_at and (now - cached_at) < _SUB_CACHE_TTL:
            return True
    try:
        m = await bot.get_chat_member(f"@{CHANNEL_USERNAME}", uid)
        ok = str(m.status) in {"member", "administrator", "creator"}
        if ok:
            _SUB_CACHE[uid] = now
        else:
            _SUB_CACHE.pop(uid, None)
        return ok
    except TelegramError:
        _SUB_CACHE.pop(uid, None)
        return False

async def require_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or is_admin(user.id) or await is_subscribed(context.bot, user.id):
        return True

    txt = f"🔐 <b>Барои истифодаи бот ба канали мо обуна шавед:</b>\n\n📢 @{e(CHANNEL_USERNAME)}"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Обуна шудан", url=CHANNEL_URL)],
        [InlineKeyboardButton("✅ Ман обуна шудам", callback_data="check_sub")],
    ])
    if update.callback_query:
        await update.callback_query.message.edit_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)
    return False

# ============================================================
# KEYBOARDS
# ============================================================
def main_menu(uid=0):
    kb = [
        [InlineKeyboardButton("🛒 Мағоза", callback_data="shop"), InlineKeyboardButton("🛍️ Аккаунтҳо", callback_data="marketplace")],
        [InlineKeyboardButton("👤 Профил", callback_data="profile"), InlineKeyboardButton("📦 Фармоишҳо", callback_data="my_orders")],
        [InlineKeyboardButton("🎁 Реферал", callback_data="ref"), InlineKeyboardButton("ℹ️ Маълумот", callback_data="info")],
    ]
    if is_admin(uid):
        kb.append([InlineKeyboardButton("⚙️ Админ-панел", callback_data="admin_panel")])
    return InlineKeyboardMarkup(kb)

def shop_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Алмазҳо", callback_data="cat:diamond")],
        [InlineKeyboardButton("🎟 Ваучерҳо", callback_data="cat:voucher")],
        [InlineKeyboardButton("🎫 Pass / Elite", callback_data="cat:pass")],
        [InlineKeyboardButton("⬅️ Меню", callback_data="menu")],
    ])

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Статистика", callback_data="adm_stats"), InlineKeyboardButton("📢 Рассылка", callback_data="adm_broadcast")],
        [InlineKeyboardButton("💵 Тағйири нархҳо", callback_data="adm_prices"), InlineKeyboardButton("🎟️ Промокод сохтан", callback_data="adm_add_promo")],
        [InlineKeyboardButton("➕ Иловаи аккаунт", callback_data="adm_add_acc"), InlineKeyboardButton("⬅️ Меню", callback_data="menu")]
    ])

# ============================================================
# COMMAND HANDLERS
# ============================================================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    referrer_id = int(args[0]) if args and args[0].isdigit() else None
    
    await get_or_create_user(user, referrer_id)
    if not await require_sub(update, context):
        return

    txt = f"👋 <b>Салом, {e(user.first_name)}!</b>\n\n🔥 Ба боти <b>DanaterShop</b> хуш омадед!\nАз менюи зер бахши дилхоҳро интихоб кунед 👇"
    await update.message.reply_text(txt, reply_markup=main_menu(user.id), parse_mode=ParseMode.HTML)

# ============================================================
# CALLBACK QUERY HANDLER
# ============================================================
async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    uid = q.from_user.id

    if data == "check_sub":
        if await is_subscribed(context.bot, uid, force=True):
            await q.message.edit_text("✅ Раҳмат барои обуна!", reply_markup=main_menu(uid))
        else:
            await q.answer("❌ Шумо ҳанӯз обуна нашудаед!", show_alert=True)
        return

    if not await require_sub(update, context):
        return

    # Навигация
    if data == "menu":
        await q.message.edit_text("🔥 <b>DanaterShop</b>\n\nАз меню интихоб кунед 👇", reply_markup=main_menu(uid), parse_mode=ParseMode.HTML)
    
    elif data == "shop":
        await q.message.edit_text("🛒 <b>МАҒОЗА</b>\n\nКатегорияро интихоб кунед:", reply_markup=shop_menu(), parse_mode=ParseMode.HTML)
    
    elif data.startswith("cat:"):
        cat = data.split(":")[1]
        products = await get_products_by_category(cat)
        cat_title = CATEGORIES.get(cat, "Товарҳо")
        kb = [[InlineKeyboardButton(f"{p['name']} — {money(p['price'])} TJS", callback_data=f"buy:{p['id']}")] for p in products]
        kb.append([InlineKeyboardButton("⬅️️ Орқага", callback_data="shop")])
        await q.message.edit_text(f"🛒 <b>{cat_title}</b>\n\nМаҳсулотро интихоб кунед:", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data.startswith("buy:"):
        pid = data.split(":")[1]
        prod = await get_product_fast(pid)
        if not prod:
            await q.answer("❌ Маҳсулот ёфт нашуд!", show_alert=True)
            return

        context.user_data["buy_product_id"] = pid
        context.user_data["promo_discount"] = 0
        context.user_data["promo_code"] = None
        context.user_data["state"] = "WAITING_FF_ID"

        txt = f"🛒 <b>Оформление заказа</b>\n\n📦 <b>Товар:</b> {e(prod['name'])}\n💰 <b>Цена:</b> {money(prod['price'])} TJS\n\n👇 <b>Free Fire ID-и худро фиристед (танҳо рақам):</b>"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="shop")]])
        await q.message.edit_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)

    elif data == "apply_promo":
        context.user_data["state"] = "WAITING_PROMO"
        await q.message.reply_text("🎟️ <b>Промокод-ро ворид кунед:</b>", parse_mode=ParseMode.HTML)

    elif data.startswith("pay:"):
        method = data.split(":")[1]
        pid = context.user_data.get("buy_product_id")
        ff_id = context.user_data.get("ff_id")

        if not pid or not ff_id:
            await q.answer("❌ Хатогӣ рӯй дод. Аз нав кӯшиш кунед.", show_alert=True)
            return

        prod = await get_product_fast(pid)
        discount = context.user_data.get("promo_discount", 0)
        final_price = prod['price'] * (1 - discount / 100)
        
        num = ALIF_NUMBER if method == "alif" else DC_NUMBER
        m_name = "Алиф Мобил" if method == "alif" else "Душанбе Сити"

        order_id = hashlib.md5(f"{uid}{time.time()}".encode()).hexdigest()[:8].upper()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        async with pool.connection() as conn:
            async with conn.cursor() as c:
                await c.execute(
                    """INSERT INTO orders (id, user_id, customer_name, free_fire_id, product_id, product_name, price, payment_method, promo_code, final_price, status, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)""",
                    (order_id, uid, q.from_user.first_name, ff_id, prod['id'], prod['name'], prod['price'], method, context.user_data.get("promo_code"), final_price, now_str)
                )
                await conn.commit()

        txt = (
            f"💳 <b>Оплата через {m_name}</b>\n\n"
            f"🆔 <b>Заказ:</b> <code>#{order_id}</code>\n"
            f"📦 <b>Товар:</b> {e(prod['name'])}\n"
            f"🎮 <b>Free Fire ID:</b> <code>{ff_id}</code>\n"
            f"💰 <b>Сумма:</b> <code>{money(final_price)} TJS</code>\n\n"
            f"📞 <b>Номер для перевода:</b> <code>{num}</code>\n\n"
            f"⚠️ <i>После оплаты отправьте скриншот/чек админу!</i>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👨‍💻 Чекро ба Админ фиристодан", url=f"https://t.me/{ADMIN_USERNAME}")],
            [InlineKeyboardButton("⬅️ Меню", callback_data="menu")]
        ])
        await q.message.edit_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)

        # Оведомление ба админҳо
        adm_txt = (
            f"🔔 <b>НАВ ФАРМОИШ! #{order_id}</b>\n\n"
            f"👤 <b>Корбар:</b> <a href='tg://user?id={uid}'>{e(q.from_user.first_name)}</a> (ID: <code>{uid}</code>)\n"
            f"📦 <b>Товар:</b> {e(prod['name'])}\n"
            f"🎮 <b>FF ID:</b> <code>{ff_id}</code>\n"
            f"💰 <b>Сумма:</b> {money(final_price)} TJS ({m_name})\n"
        )
        adm_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Тасдиқ кардан", callback_data=f"adm_app:{order_id}"), InlineKeyboardButton("❌ Рад кардан", callback_data=f"adm_rej:{order_id}")]
        ])
        for adm_id in ADMIN_IDS:
            try:
                await context.bot.send_message(adm_id, adm_txt, reply_markup=adm_kb, parse_mode=ParseMode.HTML)
            except Exception:
                pass

        context.user_data.clear()

    # Админ тасдиқ / рад
    elif data.startswith("adm_app:") or data.startswith("adm_rej:"):
        if not is_admin(uid):
            return
        action, order_id = data.split(":")
        status = "completed" if "app" in action else "rejected"
        
        async with pool.connection() as conn:
            async with conn.cursor() as c:
                await c.execute("SELECT user_id, product_name, final_price, status FROM orders WHERE id=%s", (order_id,))
                order = await c.fetchone()
                if not order or order[3] != "pending":
                    await q.answer("❌ Фармоиш алакай коркард шудааст!", show_alert=True)
                    return
                
                await c.execute("UPDATE orders SET status=%s WHERE id=%s", (status, order_id))
                
                # Реферальный бонус
                if status == "completed":
                    await c.execute("SELECT referrer_id FROM users WHERE id=%s", (order[0],))
                    u_row = await c.fetchone()
                    if u_row and u_row[0]:
                        bonus = order[2] * (REF_BONUS_PERCENT / 100)
                        await c.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (bonus, u_row[0]))
                        try:
                            await context.bot.send_message(u_row[0], f"🎁 Ба шумо <b>{money(bonus)} TJS</b> бонуси рефералӣ илова шуд!", parse_mode=ParseMode.HTML)
                        except Exception:
                            pass
                await conn.commit()

        st_text = "✅ Тасдиқ шуд" if status == "completed" else "❌ Рад шуд"
        await q.message.edit_text(f"{q.message.text}\n\n<b>СТАТУС: {st_text}</b>", parse_mode=ParseMode.HTML)

        # 🔔 Уведомление ба корбар
        user_msg = f"🎉 <b>Фармоиши шумо #{order_id} ({e(order[1])}) бомуваффақият иҷро шуд!</b>" if status == "completed" else f"❌ <b>Фармоиши шумо #{order_id} рад карда шуд.</b>"
        try:
            await context.bot.send_message(order[0], user_msg, parse_mode=ParseMode.HTML)
        except Exception:
            pass

    # Профиль, Реферал, Аккаунтҳо, Инфо ва Фармоишҳо
        elif data == "profile":
        u = await get_or_create_user(q.from_user)
        txt = f"👤 <b>Профили шумо:</b>\n\n🆔 <b>ID:</b> <code>{u['id']}</code>\n👤 <b>Им:</b> {e(u['first_name'])}\n💰 <b>Баланс:</b> {money(u['balance'])} TJS\n👥 <b>Дӯстони даъватшуда:</b> {u['referred_count']}"
        await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Меню", callback_data="menu")]]), parse_mode=ParseMode.HTML)

    elif data == "ref":
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={uid}"
        txt = f"🎁 <b>Системаи рефералӣ</b>\n\nДӯстони худро даъват кунед ва <b>{REF_BONUS_PERCENT}%</b> бонус гиред!\n\n🔗 <b>Линки шумо:</b>\n<code>{ref_link}</code>"
        await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Меню", callback_data="menu")]]), parse_mode=ParseMode.HTML)

    elif data == "info":
        txt = f"ℹ️ <b>Маълумот</b>\n\n📢 <b>Канал:</b> @{CHANNEL_USERNAME}\n📸 <b>Instagram:</b> {INSTAGRAM_URL}\n👨‍💻 <b>Админ:</b> @{ADMIN_USERNAME}\n🤖 <b>Поддержка:</b> @{SUPPORT_BOT_USERNAME}"
        await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Меню", callback_data="menu")]]), parse_mode=ParseMode.HTML)

    elif data == "my_orders":
        async with pool.connection() as conn:
            async with conn.cursor() as c:
                await c.execute("SELECT id, product_name, final_price, status, created_at FROM orders WHERE user_id=%s ORDER BY created_at DESC LIMIT 5", (uid,))
                rows = await c.fetchall()
        txt = "📦 <b>5 Фармоиши охирини шумо:</b>\n\n" if rows else "📦 <b>Шумо фармоиш надоред.</b>"
        for r in rows:
            st = "⏳ Коркард" if r[3] == "pending" else ("✅ Иҷро шуд" if r[3] == "completed" else "❌ Бекор шуд")
            txt += f"🔹 <b>#{r[0]}</b> | {e(r[1])}\n💰 {money(r[2])} TJS | {st}\n📅 {r[4]}\n\n"
        await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Меню", callback_data="menu")]]), parse_mode=ParseMode.HTML)

    elif data == "marketplace":
        async with pool.connection() as conn:
            async with conn.cursor() as c:
                await c.execute("SELECT id, title, price, details FROM accounts WHERE active=1")
                accs = await c.fetchall()
        if not accs:
            await q.message.edit_text("🛍️ <b>Маркетплейс</b>\n\nҲозир аккаунти озод нест.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Меню", callback_data="menu")]]), parse_mode=ParseMode.HTML)
            return
        kb = [[InlineKeyboardButton(f"{a[1]} — {money(a[2])} TJS", callback_data=f"buy_acc:{a[0]}")] for a in accs]
        kb.append([InlineKeyboardButton("⬅️ Меню", callback_data="menu")])
        await q.message.edit_text("🛍️ <b>Аккаунтҳои Free Fire:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    # Админ Панел
    elif data == "admin_panel" and is_admin(uid):
        await q.message.edit_text("⚙ <b>Админ-Панел</b>", reply_markup=admin_menu(), parse_mode=ParseMode.HTML)

    elif data == "adm_stats" and is_admin(uid):
        async with pool.connection() as conn:
            async with conn.cursor() as c:
                await c.execute("SELECT COUNT(*) FROM users"); u_cnt = (await c.fetchone())[0]
                await c.execute("SELECT COUNT(*), COALESCE(SUM(final_price),0) FROM orders WHERE status='completed'"); o_cnt, o_sum = await c.fetchone()
        await q.message.edit_text(f"📊 <b>Статистика:</b>\n\n👥 Корбарон: <b>{u_cnt}</b>\n✅ Харидҳои муваффақ: <b>{o_cnt}</b>\n💰 Даромад: <b>{money(o_sum)} TJS</b>", reply_markup=admin_menu(), parse_mode=ParseMode.HTML)

    elif data == "adm_broadcast" and is_admin(uid):
        context.user_data["state"] = "WAITING_BROADCAST"
        await q.message.reply_text("📢 <b>Матни рассылкаро фиристед:</b>", parse_mode=ParseMode.HTML)

    elif data == "adm_prices" and is_admin(uid):
        context.user_data["state"] = "WAITING_PRICE_CHANGE"
        await q.message.reply_text("💵 <b>ID-и маҳсулот ва нархи навро фиристед (Масалан: <code>110 8.5</code>):</b>", parse_mode=ParseMode.HTML)

    elif data == "adm_add_promo" and is_admin(uid):
        context.user_data["state"] = "WAITING_ADD_PROMO"
        await q.message.reply_text("🎟️ <b>Код ва фоизи скидкаро фиристед (Масалан: <code>BONUS 10</code>):</b>", parse_mode=ParseMode.HTML)

    elif data == "adm_add_acc" and is_admin(uid):
        context.user_data["state"] = "WAITING_ADD_ACC"
        await q.message.reply_text("➕ <b>Ном, нарх ва тавсифи аккаунтро фиристед (формат: Ном | Нарх | Тавсиф):</b>\n\nМасалан: <code>VIP Account | 250 | Level 65, Old skins</code>", parse_mode=ParseMode.HTML)

# ============================================================
# MESSAGE HANDLER
# ============================================================
async def msg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    text = update.message.text.strip()
    uid = update.effective_user.id

    if state == "WAITING_FF_ID":
        if not text.isdigit():
            await update.message.reply_text("❌ Free Fire ID танҳо аз рақамҳо иборат аст! Аз нав фиристед:")
            return
        context.user_data["ff_id"] = text
        context.user_data["state"] = None
        pid = context.user_data.get("buy_product_id")
        prod = await get_product_fast(pid)
        
        txt = f"✅ <b>Free Fire ID:</b> <code>{text}</code>\n📦 <b>Товар:</b> {e(prod['name'])}\n💰 <b>Нарх:</b> {money(prod['price'])} TJS\n\nНамуди пардохтро интихоб кунед:"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Алиф Мобил", callback_data="pay:alif")],
            [InlineKeyboardButton("💳 Душанбе Сити", callback_data="pay:dc")],
            [InlineKeyboardButton("🎟️ Промокод дорам", callback_data="apply_promo")],
            [InlineKeyboardButton("❌ Отмена", callback_data="shop")]
        ])
        await update.message.reply_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)

    elif state == "WAITING_PROMO":
        async with pool.connection() as conn:
            async with conn.cursor() as c:
                await c.execute("SELECT discount_percent FROM promos WHERE code=%s AND active=1 AND used < max_uses", (text.upper(),))
                row = await c.fetchone()
                if row:
                    context.user_data["promo_discount"] = row[0]
                    context.user_data["promo_code"] = text.upper()
                    await update.message.reply_text(f"✅ Промокод қабул шуд! Скидка: <b>{row[0]}%</b>\n\nЭнди тарзи пардохтро интихоб кунед:", reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("💳 Алиф Мобил", callback_data="pay:alif")],
                        [InlineKeyboardButton("💳 Душанбе Сити", callback_data="pay:dc")]
                    ]), parse_mode=ParseMode.HTML)
                else:
                    await update.message.reply_text("❌ Промокод нодуруст аст ё мӯҳлаташ гузаштааст!")

    elif state == "WAITING_BROADCAST" and is_admin(uid):
        context.user_data["state"] = None
        async with pool.connection() as conn:
            async with conn.cursor() as c:
                await c.execute("SELECT id FROM users")
                uids = [r[0] for r in await c.fetchall()]
        
        await update.message.reply_text(f"🚀 Рассылка ба {len(uids)} корбар оғоз шуд...")
        count = 0
        for user_id in uids:
            try:
                await context.bot.send_message(user_id, text, parse_mode=ParseMode.HTML)
                count += 1
                await asyncio.sleep(0.05)
            except Exception:
                pass
        await update.message.reply_text(f"✅ Рассылка ба охир расид. Расид ба: {count} кас.")

    elif state == "WAITING_PRICE_CHANGE" and is_admin(uid):
        context.user_data["state"] = None
        try:
            pid, new_price = text.split()
            new_price = float(new_price)
            async with pool.connection() as conn:
                async with conn.cursor() as c:
                    await c.execute("UPDATE products SET price=%s WHERE id=%s", (new_price, pid))
                    await conn.commit()
            _PRODUCT_CACHE.pop(pid, None) # Кэшро тоза мекунем
            await update.message.reply_text(f"✅ Нархи маҳсулоти ID {pid} ба <b>{new_price} TJS</b> тағйир ёфт!", parse_mode=ParseMode.HTML)
        except Exception:
            await update.message.reply_text("❌ Формати нодуруст. Мисол: <code>110 8.5</code>")

    elif state == "WAITING_ADD_PROMO" and is_admin(uid):
        context.user_data["state"] = None
        try:
            code, disc = text.split()
            async with pool.connection() as conn:
                async with conn.cursor() as c:
                    await c.execute("INSERT INTO promos (code, discount_percent) VALUES (%s, %s) ON CONFLICT DO NOTHING", (code.upper(), int(disc)))
                    await conn.commit()
            await update.message.reply_text(f"✅ Промокоди <b>{code.upper()}</b> бо скидкаи <b>{disc}%</b> сохта шуд!", parse_mode=ParseMode.HTML)
        except Exception:
            await update.message.reply_text("❌ Формати нодуруст. Мисол: <code>BONUS 10</code>")

    elif state == "WAITING_ADD_ACC" and is_admin(uid):
        context.user_data["state"] = None
        try:
            parts = [p.strip() for p in text.split("|")]
            title = parts[0]
            price = float(parts[1])
            details = parts[2] if len(parts) > 2 else ""
            async with pool.connection() as conn:
                async with conn.cursor() as c:
                    await c.execute("INSERT INTO accounts (title, price, details, active) VALUES (%s, %s, %s, 1)", (title, price, details))
                    await conn.commit()
            await update.message.reply_text(f"✅ Аккаунти <b>{e(title)}</b> бо нархи <b>{price} TJS</b> илова шуд!", parse_mode=ParseMode.HTML)
        except Exception:
            await update.message.reply_text("❌ Формати нодуруст! Формат: <code>Ном | Нарх | Тавсиф</code>")

# ============================================================
# STARTUP HOOK & MAIN LAUNCHER
# ============================================================
async def on_startup(app: Application):
    await init_db_pool()
    await init_db()
    logger.info("⚡ DB ва Pool бомуваффақият оғоз карда шуданд!")

def main():
    if not TOKEN:
        print("❌ TOKEN ЁФТ НАШУД!")
        return

    app = Application.builder().token(TOKEN).concurrent_updates(True).post_init(on_startup).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_handler))

    logger.info("⚡ Бот бо суръати максималӣ ва функционали пурра ба кор даромад!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
