import os
import json
import html
import logging
from datetime import datetime
from threading import Thread, Lock

from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# ============================================================
# DANATER FREE FIRE V4
# TOKEN IS READ ONLY FROM RENDER ENVIRONMENT
# ============================================================

TOKEN = os.getenv("TOKEN", "").strip()

ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "ffxdavlatov").lstrip("@")

CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "otzivi_danater1").lstrip("@")
CHANNEL_URL = f"https://t.me/{CHANNEL_USERNAME}"

ALIF_NUMBER = os.getenv("ALIF_NUMBER", "+992917003888")
DC_NUMBER = os.getenv("DC_NUMBER", "+992783836464")

WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER", "992783456363")
WHATSAPP_URL = f"https://wa.me/{WHATSAPP_NUMBER}"

INSTAGRAM_URL = os.getenv(
    "INSTAGRAM_URL",
    "https://www.instagram.com/danatershop.tj?stkn=a2E0Z3N5anU4azV0"
)
TELEGRAM_ADMIN_URL = os.getenv(
    "TELEGRAM_ADMIN_URL",
    "https://t.me/ffxdavlatov"
)

PORT = int(os.getenv("PORT", "10000"))

USERS_FILE = "users.json"
ORDERS_FILE = "orders.json"
PRICES_FILE = "prices.json"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("DANATER")

file_lock = Lock()

# ============================================================
# PRODUCTS
# ============================================================

PRODUCTS = {
    "100": {
        "name": "💎 100 алмаз",
        "price": 10,
        "category": "diamond"
    },
    "310": {
        "name": "💎 310 алмаз",
        "price": 30,
        "category": "diamond"
    },
    "520": {
        "name": "💎 520 алмаз",
        "price": 50,
        "category": "diamond"
    },
    "1060": {
        "name": "💎 1060 алмаз",
        "price": 100,
        "category": "diamond"
    },
    "2180": {
        "name": "💎 2180 алмаз",
        "price": 200,
        "category": "diamond"
    },
    "5600": {
        "name": "💎 5600 алмаз",
        "price": 550,
        "category": "diamond"
    },
    "week": {
        "name": "🎟 Ваучер 1 ҳафта — 450 алмаз",
        "price": 18,
        "category": "voucher"
    },
    "month": {
        "name": "🎟 Ваучер 1 моҳ — 2600 алмаз",
        "price": 95,
        "category": "voucher"
    },
    "lite": {
        "name": "🎟 Ваучер Лайт — 90 алмаз",
        "price": 7,
        "category": "voucher"
    }
}

# ============================================================
# JSON STORAGE
# ============================================================

def ensure_file(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)

def load_json(path, default):
    ensure_file(path, default)
    try:
        with file_lock:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        logger.exception("Failed to read %s", path)
        return default

def save_json(path, data):
    tmp = path + ".tmp"
    with file_lock:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

def load_users():
    data = load_json(USERS_FILE, {})
    # Compatibility with old users.json list format
    if isinstance(data, list):
        converted = {}
        for item in data:
            if isinstance(item, dict) and item.get("id") is not None:
                converted[str(item["id"])] = item
        data = converted
        save_json(USERS_FILE, data)
    return data if isinstance(data, dict) else {}

def save_user(user):
    users = load_users()
    users[str(user.id)] = {
        "id": user.id,
        "username": user.username or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "updated_at": datetime.now().isoformat()
    }
    save_json(USERS_FILE, users)

def load_orders():
    data = load_json(ORDERS_FILE, [])
    return data if isinstance(data, list) else []

def load_prices():
    saved = load_json(PRICES_FILE, {})
    prices = {}
    for pid, product in PRODUCTS.items():
        try:
            prices[pid] = int(saved.get(pid, product["price"]))
        except (TypeError, ValueError):
            prices[pid] = product["price"]
    save_json(PRICES_FILE, prices)
    return prices

def get_prices():
    return load_prices()

# ============================================================
# HELPERS
# ============================================================

def is_admin(user_id):
    return user_id in ADMIN_IDS

def product_name(pid):
    return PRODUCTS.get(pid, {}).get("name", "Маҳсулоти номаълум")

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Хариди алмаз", callback_data="products")],
        [InlineKeyboardButton("📦 Фармоишҳои ман", callback_data="my_orders")],
        [InlineKeyboardButton("ℹ️ Маълумот", callback_data="info")]
    ])

def back_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Бозгашт", callback_data="menu")]
    ])

def product_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 100 алмаз", callback_data="buy:100")],
        [InlineKeyboardButton("💎 310 алмаз", callback_data="buy:310")],
        [InlineKeyboardButton("💎 520 алмаз", callback_data="buy:520")],
        [InlineKeyboardButton("💎 1060 алмаз", callback_data="buy:1060")],
        [InlineKeyboardButton("💎 2180 алмаз", callback_data="buy:2180")],
        [InlineKeyboardButton("💎 5600 алмаз", callback_data="buy:5600")],
        [InlineKeyboardButton("🎟 Ваучер 1 ҳафта", callback_data="buy:week")],
        [InlineKeyboardButton("🎟 Ваучер 1 моҳ", callback_data="buy:month")],
        [InlineKeyboardButton("🎟 Ваучер Лайт", callback_data="buy:lite")],
        [InlineKeyboardButton("⬅️ Бозгашт", callback_data="menu")]
    ])

def payment_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Alif", callback_data="pay:alif")],
        [InlineKeyboardButton("💳 Dushanbe City", callback_data="pay:dc")],
        [InlineKeyboardButton("❌ Бекор кардан", callback_data="cancel_order")]
    ])

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Фармоишҳо", callback_data="admin:orders")],
        [InlineKeyboardButton("👥 Корбарон", callback_data="admin:users")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin:broadcast")],
        [InlineKeyboardButton("💰 Нархҳо", callback_data="admin:prices")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton("⬅️ Меню", callback_data="menu")]
    ])

def admin_back():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Бозгашт ба Admin", callback_data="admin:menu")]
    ])

def prices_text():
    prices = get_prices()
    return (
        "💰 <b>НАРХҲОИ ҲОЗИРА:</b>\n"
        f"💎 100 алмаз — <b>{prices['100']} сомонӣ</b>\n"
        f"💎 310 алмаз — <b>{prices['310']} сомонӣ</b>\n"
        f"💎 520 алмаз — <b>{prices['520']} сомонӣ</b>\n"
        f"💎 1060 алмаз — <b>{prices['1060']} сомонӣ</b>\n"
        f"💎 2180 алмаз — <b>{prices['2180']} сомонӣ</b>\n"
        f"💎 5600 алмаз — <b>{prices['5600']} сомонӣ</b>\n"
        f"🎟 Ваучер 1 ҳафта — <b>{prices['week']} сомонӣ</b>\n"
        f"🎟 Ваучер 1 моҳ — <b>{prices['month']} сомонӣ</b>\n"
        f"🎟 Ваучер Лайт — <b>{prices['lite']} сомонӣ</b>"
    )

# ============================================================
# SUBSCRIPTION
# ============================================================

def subscription_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Обуна шудан", url=CHANNEL_URL)],
        [InlineKeyboardButton("✅ Ман обуна шудам", callback_data="check_sub")]
    ])

async def is_subscribed(bot, user_id):
    try:
        member = await bot.get_chat_member(
            chat_id=f"@{CHANNEL_USERNAME}",
            user_id=user_id
        )
        return str(member.status) in {"member", "administrator", "creator"}
    except TelegramError as e:
        logger.warning("Subscription check failed: %s", e)
        return False

async def require_subscription(update, context):
    user = update.effective_user
    if not user:
        return False

    if is_admin(user.id):
        return True

    if await is_subscribed(context.bot, user.id):
        return True

    text = (
        "🔐 <b>Барои истифодаи бот аввал ба канали мо обуна шавед.</b>\n\n"
        f"📢 Канал: @{html.escape(CHANNEL_USERNAME)}\n\n"
        "Пас аз обуна шудан, «Ман обуна шудам»-ро пахш кунед."
    )

    if update.callback_query:
        await update.callback_query.message.edit_text(
            text,
            reply_markup=subscription_keyboard(),
            parse_mode=ParseMode.HTML
        )
    else:
        await update.effective_message.reply_text(
            text,
            reply_markup=subscription_keyboard(),
            parse_mode=ParseMode.HTML
        )
    return False

# ============================================================
# START
# ============================================================

async def start(update, context):
    user = update.effective_user
    if not user:
        return

    save_user(user)
    context.user_data.clear()

    if not await require_subscription(update, context):
        return

    await update.message.reply_text(
        "🔥 <b>DANATER FREE FIRE</b>\n\n"
        "🛍️ <b>МАГАЗИНИ ОНЛАЙН</b>\n"
        "💎 Алмазҳо ва ваучерҳо дар як ҷо\n\n"
        f"{prices_text()}\n\n"
        "⚡️ Аз меню маҳсулотро интихоб кунед:",
        reply_markup=main_menu(),
        parse_mode=ParseMode.HTML
    )

async def my_id(update, context):
    await update.message.reply_text(
        f"🆔 Telegram ID-и шумо: <code>{update.effective_user.id}</code>",
        parse_mode=ParseMode.HTML
    )

# ============================================================
# STORE
# ============================================================

async def show_menu(update, context):
    q = update.callback_query
    await q.answer()

    if not await require_subscription(update, context):
        return

    await q.message.edit_text(
        "🔥 <b>DANATER FREE FIRE</b>\n\n"
        "🛍️ <b>МАГАЗИНИ ОНЛАЙН</b>\n"
        "💎 Алмазҳо ва ваучерҳо дар як ҷо\n\n"
        f"{prices_text()}\n\n"
        "⚡️ Аз меню интихоб кунед:",
        reply_markup=main_menu(),
        parse_mode=ParseMode.HTML
    )

async def products(update, context):
    q = update.callback_query
    await q.answer()

    if not await require_subscription(update, context):
        return

    p = get_prices()
    text = (
        "🛒 <b>ХАРИДИ АЛМАЗ</b>\n\n"
        "💎 <b>АЛМАЗҲО:</b>\n"
        f"100 — {p['100']} сомонӣ\n"
        f"310 — {p['310']} сомонӣ\n"
        f"520 — {p['520']} сомонӣ\n"
        f"1060 — {p['1060']} сомонӣ\n"
        f"2180 — {p['2180']} сомонӣ\n"
        f"5600 — {p['5600']} сомонӣ\n\n"
        "🎟 <b>ВАУЧЕРҲО:</b>\n"
        f"1 ҳафта — {p['week']} сомонӣ\n"
        f"1 моҳ — {p['month']} сомонӣ\n"
        f"Лайт — {p['lite']} сомонӣ\n\n"
        "Маҳсулотро интихоб кунед:"
    )
    await q.message.edit_text(
        text,
        reply_markup=product_keyboard(),
        parse_mode=ParseMode.HTML
    )

async def buy_product(update, context):
    q = update.callback_query
    await q.answer()

    if not await require_subscription(update, context):
        return

    pid = q.data.split(":", 1)[1]
    if pid not in PRODUCTS:
        await q.answer("Маҳсулот ёфт нашуд.", show_alert=True)
        return

    context.user_data.clear()
    context.user_data["product_id"] = pid
    context.user_data["state"] = "waiting_ffid"

    price = get_prices()[pid]

    await q.message.edit_text(
        "🛒 <b>ФАРМОИШ</b>\n\n"
        f"📦 Маҳсулот: <b>{html.escape(product_name(pid))}</b>\n"
        f"💰 Нарх: <b>{price} сомонӣ</b>\n\n"
        "🎮 <b>Free Fire ID-и худро фиристед:</b>\n"
        "Мисол: <code>123456789</code>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Бекор кардан", callback_data="cancel_order")]
        ]),
        parse_mode=ParseMode.HTML
    )

async def cancel_order(update, context):
    q = update.callback_query
    await q.answer("Фармоиш бекор шуд.")
    context.user_data.clear()
    await q.message.edit_text(
        "❌ <b>Фармоиш бекор шуд.</b>",
        reply_markup=main_menu(),
        parse_mode=ParseMode.HTML
    )

# ============================================================
# USER TEXT FLOW
# ============================================================

async def handle_text(update, context):
    user = update.effective_user
    if not user:
        return

    save_user(user)
    state = context.user_data.get("state")

    # Admin price editing / broadcast are handled first.
    if is_admin(user.id) and state == "edit_price":
        pid = context.user_data.get("edit_price_id")
        raw = update.message.text.strip()

        if pid not in PRODUCTS:
            context.user_data.clear()
            await update.message.reply_text("❌ Маҳсулот ёфт нашуд.")
            return

        if not raw.isdigit():
            await update.message.reply_text("❌ Танҳо рақам фиристед. Мисол: 25")
            return

        price = int(raw)
        if price < 0 or price > 1000000:
            await update.message.reply_text("❌ Нарх нодуруст аст.")
            return

        prices = get_prices()
        prices[pid] = price
        save_json(PRICES_FILE, prices)
        context.user_data.clear()

        await update.message.reply_text(
            f"✅ <b>Нарх иваз шуд!</b>\n\n"
            f"📦 {html.escape(product_name(pid))}\n"
            f"💰 Нархи нав: <b>{price} сомонӣ</b>",
            reply_markup=admin_menu(),
            parse_mode=ParseMode.HTML
        )
        return

    if is_admin(user.id) and state == "broadcast":
        text = update.message.text.strip()
        if not text:
            await update.message.reply_text("Матн холӣ аст.")
            return

        context.user_data.clear()
        users = load_users()
        sent = 0
        failed = 0

        await update.message.reply_text("📢 Рассылка оғоз шуд...")

        for uid in users:
            try:
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=text,
                    parse_mode=ParseMode.HTML
                )
                sent += 1
            except TelegramError:
                failed += 1

        await update.message.reply_text(
            f"📢 <b>Рассылка анҷом ёфт</b>\n\n"
            f"✅ Ирсол шуд: {sent}\n"
            f"❌ Хато: {failed}",
            parse_mode=ParseMode.HTML
        )
        return

    if not await require_subscription(update, context):
        return

    if state == "waiting_ffid":
        ffid = update.message.text.strip()
        if not ffid.isdigit() or not (5 <= len(ffid) <= 20):
            await update.message.reply_text(
                "❌ Free Fire ID нодуруст аст.\nТанҳо рақам фиристед."
            )
            return

        context.user_data["ffid"] = ffid
        context.user_data["state"] = "waiting_name"

        await update.message.reply_text(
            "👤 <b>Номи худро фиристед:</b>\nМисол: Ysuf",
            parse_mode=ParseMode.HTML
        )
        return

    if state == "waiting_name":
        name = update.message.text.strip()
        if not (2 <= len(name) <= 100):
            await update.message.reply_text("❌ Ном нодуруст аст.")
            return

        context.user_data["customer_name"] = name
        context.user_data["state"] = "waiting_payment"

        await update.message.reply_text(
            "💳 <b>Усули пардохтро интихоб кунед:</b>",
            reply_markup=payment_keyboard(),
            parse_mode=ParseMode.HTML
        )

# ============================================================
# PAYMENT
# ============================================================

async def select_payment(update, context):
    q = update.callback_query
    await q.answer()

    if not await require_subscription(update, context):
        return

    method = q.data.split(":", 1)[1]
    pid = context.user_data.get("product_id")

    if pid not in PRODUCTS:
        context.user_data.clear()
        await q.message.edit_text(
            "❌ Сессияи фармоишӣ гузаштааст.",
            reply_markup=main_menu()
        )
        return

    if method == "alif":
        payment_name = "Alif"
        number = ALIF_NUMBER
    else:
        payment_name = "Dushanbe City"
        number = DC_NUMBER

    context.user_data["payment_method"] = payment_name
    context.user_data["state"] = "waiting_receipt"

    price = get_prices()[pid]

    await q.message.edit_text(
        "💳 <b>ПАРДОХТ</b>\n\n"
        f"🏦 Система: <b>{payment_name}</b>\n"
        f"📱 Рақам: <code>{html.escape(number)}</code>\n"
        f"💰 Сумма: <b>{price} сомонӣ</b>\n\n"
        "📸 Пас аз пардохт <b>расидро ҳамчун акс</b> фиристед.",
        parse_mode=ParseMode.HTML
    )

# ============================================================
# RECEIPT
# ============================================================

async def handle_photo(update, context):
    user = update.effective_user
    if not user:
        return

    save_user(user)

    if not await require_subscription(update, context):
        return

    if context.user_data.get("state") != "waiting_receipt":
        await update.message.reply_text(
            "ℹ️ Аввал маҳсулотро интихоб кунед.",
            reply_markup=main_menu()
        )
        return

    pid = context.user_data.get("product_id")
    ffid = context.user_data.get("ffid")
    customer_name = context.user_data.get("customer_name")
    payment_method = context.user_data.get("payment_method")

    if pid not in PRODUCTS or not ffid or not customer_name or not payment_method:
        context.user_data.clear()
        await update.message.reply_text(
            "❌ Сессияи фармоишӣ гузаштааст.",
            reply_markup=main_menu()
        )
        return

    price = get_prices()[pid]
    order_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{user.id}"

    order = {
        "id": order_id,
        "user_id": user.id,
        "username": user.username or "",
        "first_name": user.first_name or "",
        "customer_name": customer_name,
        "free_fire_id": ffid,
        "product_id": pid,
        "product": product_name(pid),
        "price": price,
        "payment_method": payment_method,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }

    orders = load_orders()
    orders.append(order)
    save_json(ORDERS_FILE, orders)

    username = f"@{user.username}" if user.username else "username надорад"

    admin_text = (
        "🆕 <b>ФАРМОИШИ НАВ</b>\n\n"
        f"🧾 ID: <code>{order_id}</code>\n"
        f"📦 Маҳсулот: <b>{html.escape(product_name(pid))}</b>\n"
        f"💰 Нарх: <b>{price} сомонӣ</b>\n"
        f"🎮 Free Fire ID: <code>{html.escape(ffid)}</code>\n"
        f"👤 Ном: <b>{html.escape(customer_name)}</b>\n"
        f"📱 Telegram: {html.escape(username)}\n"
        f"🆔 Telegram ID: <code>{user.id}</code>\n"
        f"💳 Пардохт: <b>{html.escape(payment_method)}</b>"
    )

        keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Тасдиқ", callback_data=f"order_done:{order_id}"),
        InlineKeyboardButton("❌ Бекор", callback_data=f"order_cancel:{order_id}")
    ]])

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=update.message.photo[-1].file_id,
                caption=admin_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        except TelegramError as e:
            logger.error("Admin notification failed: %s", e)

    context.user_data.clear()

    await update.message.reply_text(
        "✅ <b>Фармоиши шумо қабул шуд!</b>\n\n"
        f"📦 {html.escape(product_name(pid))}\n"
        f"💰 {price} сомонӣ\n"
        f"🧾 ID: <code>{order_id}</code>\n\n"
        "⏳ Администратор расидро месанҷад.",
        reply_markup=main_menu(),
        parse_mode=ParseMode.HTML
    )

# ============================================================
# MY ORDERS
# ============================================================

async def my_orders(update, context):
    q = update.callback_query
    await q.answer()

    if not await require_subscription(update, context):
        return

    orders = [
        o for o in load_orders()
        if int(o.get("user_id", 0)) == update.effective_user.id
    ]

    if not orders:
        text = "📦 <b>ФАРМОИШҲОИ МАН</b>\n\nҲоло фармоиш надоред."
    else:
        lines = ["📦 <b>ФАРМОИШҲОИ МАН</b>\n"]
        status = {
            "pending": "⏳ Дар интизорӣ",
            "done": "✅ Тасдиқ шуд",
            "cancelled": "❌ Бекор шуд"
        }
        for o in orders[-10:][::-1]:
            lines.append(
                f"🧾 <code>{html.escape(str(o.get('id', '—')))}</code>\n"
                f"📦 {html.escape(str(o.get('product', '—')))}\n"
                f"💰 {o.get('price', '—')} сомонӣ\n"
                f"📊 {status.get(o.get('status'), o.get('status', '—'))}\n"
            )
        text = "\n".join(lines)

    await q.message.edit_text(
        text,
        reply_markup=back_menu(),
        parse_mode=ParseMode.HTML
    )

# ============================================================
# INFO
# ============================================================

async def info(update, context):
    q = update.callback_query
    await q.answer()

    if not await require_subscription(update, context):
        return

    await q.message.edit_text(
        "ℹ️ <b>DANATER FREE FIRE</b>\n\n"
        f"👨‍💼 <b>Админ:</b> @{html.escape(ADMIN_USERNAME)}\n"
        f"📱 <b>WhatsApp:</b> {html.escape(WHATSAPP_NUMBER)}\n\n"
        "❓ Барои саволҳо ба админ нависед.\n"
        "🔥 Мо ҳамеша омодаи кӯмак ҳастем!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Навиштан ба WhatsApp", url=WHATSAPP_URL)],
            [InlineKeyboardButton("📸 Instagram", url=INSTAGRAM_URL)],
            [InlineKeyboardButton("✈️ Навиштан ба Telegram", url=TELEGRAM_ADMIN_URL)],
            [InlineKeyboardButton("⬅️ Бозгашт", callback_data="menu")]
        ]),
        parse_mode=ParseMode.HTML
    )

# ============================================================
# ADMIN
# ============================================================

async def admin_command(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Дастрасӣ иҷозат нест.")
        return

    await update.message.reply_text(
        "🛠️ <b>ADMIN PANEL</b>\n\nИнтихоб кунед:",
        reply_markup=admin_menu(),
        parse_mode=ParseMode.HTML
    )

async def admin_callback(update, context):
    q = update.callback_query
    if not is_admin(update.effective_user.id):
        await q.answer("⛔ Дастрасӣ иҷозат нест.", show_alert=True)
        return

    data = q.data

    if data == "admin:menu":
        await q.answer()
        await q.message.edit_text(
            "🛠️ <b>ADMIN PANEL</b>\n\nИнтихоб кунед:",
            reply_markup=admin_menu(),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "admin:prices":
        await q.answer()
        prices = get_prices()
        buttons = []
        for pid, p in PRODUCTS.items():
            buttons.append([
                InlineKeyboardButton(
                    f"{p['name']} — {prices[pid]} сомонӣ",
                    callback_data=f"price:{pid}"
                )
            ])
        buttons.append([
            InlineKeyboardButton("⬅️ Бозгашт", callback_data="admin:menu")
        ])
        await q.message.edit_text(
            "💰 <b>ИВАЗ КАРДАНИ НАРХ</b>\n\nМаҳсулотро интихоб кунед:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        return

    if data.startswith("price:"):
        await q.answer()
        pid = data.split(":", 1)[1]
        if pid not in PRODUCTS:
            await q.message.edit_text("❌ Маҳсулот ёфт нашуд.")
            return

        context.user_data["state"] = "edit_price"
        context.user_data["edit_price_id"] = pid

        await q.message.edit_text(
            f"💰 <b>ИВАЗ КАРДАНИ НАРХ</b>\n\n"
            f"📦 {html.escape(product_name(pid))}\n"
            f"💵 Нархи ҳозира: <b>{get_prices()[pid]} сомонӣ</b>\n\n"
            "Нархи навро танҳо бо рақам фиристед:",
            reply_markup=admin_back(),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "admin:users":
        await q.answer()
        users = load_users()
        await q.message.edit_text(
            f"👥 <b>КОРБАРОН</b>\n\nШумораи корбарон: <b>{len(users)}</b>",
            reply_markup=admin_back(),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "admin:stats":
        await q.answer()
        orders = load_orders()
        done = [o for o in orders if o.get("status") == "done"]
        pending = [o for o in orders if o.get("status") == "pending"]
        cancelled = [o for o in orders if o.get("status") == "cancelled"]
        revenue = sum(int(o.get("price", 0) or 0) for o in done)

        await q.message.edit_text(
            "📊 <b>СТАТИСТИКА</b>\n\n"
            f"👥 Корбарон: <b>{len(load_users())}</b>\n"
            f"📦 Ҳама фармоишҳо: <b>{len(orders)}</b>\n"
            f"⏳ Дар интизорӣ: <b>{len(pending)}</b>\n"
            f"✅ Тасдиқшуда: <b>{len(done)}</b>\n"
            f"❌ Бекоршуда: <b>{len(cancelled)}</b>\n"
            f"💰 Даромади тасдиқшуда: <b>{revenue} сомонӣ</b>",
            reply_markup=admin_back(),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "admin:orders":
        await q.answer()
        orders = load_orders()
        if not orders:
            text = "📦 <b>ФАРМОИШҲО</b>\n\nФармоиш нест."
        else:
            lines = ["📦 <b>ОХИРИН ФАРМОИШҲО</b>\n"]
            for o in orders[-10:][::-1]:
                username = f"@{o.get('username')}" if o.get("username") else "username надорад"
                lines.append(
                    f"🧾 <code>{html.escape(str(o.get('id','—')))}</code>\n"
                    f"📦 {html.escape(str(o.get('product','—')))}\n"
                    f"💰 {o.get('price','—')} сомонӣ\n"
                    f"🎮 FF ID: <code>{html.escape(str(o.get('free_fire_id','—')))}</code>\n"
                    f"👤 {html.escape(str(o.get('customer_name','—')))}\n"
                    f"📱 {html.escape(username)}\n"
                    f"🆔 TG ID: <code>{o.get('user_id','—')}</code>\n"
                    f"📊 {html.escape(str(o.get('status','—')))}\n"
                )
            text = "\n".join(lines)

        await q.message.edit_text(
            text,
            reply_markup=admin_back(),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "admin:broadcast":
        await q.answer()
        context.user_data["state"] = "broadcast"
        await q.message.edit_text(
            "📢 <b>РАССЫЛКА</b>\n\nМатни паёмро фиристед.",
            reply_markup=admin_back(),
            parse_mode=ParseMode.HTML
        )
        return

    if data.startswith("order_done:") or data.startswith("order_cancel:"):
        await q.answer()

        action, order_id = data.split(":", 1)
        orders = load_orders()
        target = next((o for o in orders if str(o.get("id")) == order_id), None)

        if not target:
            await q.message.reply_text("❌ Фармоиш ёфт нашуд.")
            return

        if action == "order_done":
            target["status"] = "done"
            user_text = (
                "✅ <b>Фармоиши шумо тасдиқ шуд!</b>\n\n"
                f"📦 {html.escape(str(target.get('product','—')))}\n"
                f"🧾 ID: <code>{html.escape(order_id)}</code>"
            )
            admin_text = "✅ Фармоиш тасдиқ шуд."
        else:
            target["status"] = "cancelled"
            user_text = (
                "❌ <b>Фармоиши шумо бекор карда шуд.</b>\n\n"
                f"🧾 ID: <code>{html.escape(order_id)}</code>"
            )
            admin_text = "❌ Фармоиш бекор шуд."

        target["updated_at"] = datetime.now().isoformat()
        save_json(ORDERS_FILE, orders)

        try:
            await context.bot.send_message(
                chat_id=int(target["user_id"]),
                text=user_text,
                parse_mode=ParseMode.HTML
            )
        except TelegramError as e:
            logger.warning("User notification failed: %s", e)

        await q.message.edit_reply_markup(reply_markup=None)
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
            await show_menu(update, context)
        else:
            await q.message.edit_text(
                "❌ <b>Шумо ҳоло ба канал обуна нашудаед.</b>\n\n"
                "Аввал обуна шавед.",
                reply_markup=subscription_keyboard(),
                parse_mode=ParseMode.HTML
            )
        return

    if data == "menu":
        await show_menu(update, context)
    elif data == "products":
        await products(update, context)
    elif data == "my_orders":
        await my_orders(update, context)
    elif data == "info":
        await info(update, context)
    elif data.startswith("buy:"):
        await buy_product(update, context)
    elif data == "cancel_order":
        await cancel_order(update, context)
    elif data.startswith("pay:"):
        await select_payment(update, context)
    elif data.startswith("admin:") or data.startswith("price:") or data.startswith("order_"):
        await admin_callback(update, context)
    else:
        await q.answer("Ин амал дастгирӣ намешавад.", show_alert=True)

# ============================================================
# ERRORS
# ============================================================

async def error_handler(update, context):
    logger.exception("Unhandled error: %s", context.error)

# ============================================================
# RENDER WEB SERVER
# ============================================================

app = Flask(__name__)

@app.get("/")
def home():
    return "DANATER FREE FIRE is running", 200

@app.get("/health")
def health():
    return {"status": "ok"}, 200

def run_web():
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

# ============================================================
# STARTUP
# ============================================================

async def post_init(application):
    try:
        await application.bot.delete_webhook(drop_pending_updates=False)
        me = await application.bot.get_me()
        logger.info("Bot connected: @%s | ID=%s", me.username, me.id)
    except TelegramError as e:
        logger.error("Telegram startup error: %s", e)
        raise

def main():
    if not TOKEN:
        raise RuntimeError(
            "TOKEN is missing. Add TOKEN to Render Environment Variables."
        )

    if not ADMIN_IDS:
        logger.warning(
            "ADMIN_IDS is empty. Add your numeric Telegram ID to Render Environment."
        )

    ensure_file(USERS_FILE, {})
    ensure_file(ORDERS_FILE, [])
    load_prices()

    Thread(target=run_web, daemon=True).start()

    application = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("id", my_id))
    application.add_handler(CommandHandler("admin", admin_command))

    application.add_handler(
        CallbackQueryHandler(callback_router)
    )

    application.add_handler(
        MessageHandler(filters.PHOTO, handle_photo)
    )

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )

    application.add_error_handler(error_handler)

    logger.info("🔥 DANATER FREE FIRE is starting...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=False
    )

if __name__ == "__main__":
    main()
