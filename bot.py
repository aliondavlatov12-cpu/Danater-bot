import json
import os
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================================================
# ⚙️ CONFIG
# =========================================================

TOKEN = "8732944768:AAEHKgxlUO3vqPhoDCd8DrJPvkfLSOH5c4E"

CHANNEL_USERNAME = "@otzivi_danater1"
CHANNEL_URL = "https://t.me/otzivi_danater1"

# Telegram ID-и админҳоро гузор.
ADMIN_IDS = {
    7659107145
}

ORDERS_FILE = "orders.json"
USERS_FILE = "users.json"
PRICES_FILE = "prices.json"

PAYMENT_NUMBERS = {
    "alif": "+992917003888",
    "city": "+992783836464",
}

DEFAULT_PRODUCTS = {
    "100": {"name": "💎 100 алмаз", "price": 10, "category": "diamonds"},
    "310": {"name": "💎 310 алмаз", "price": 30, "category": "diamonds"},
    "520": {"name": "💎 520 алмаз", "price": 50, "category": "diamonds"},
    "1060": {"name": "💎 1060 алмаз", "price": 100, "category": "diamonds"},
    "week": {"name": "🎟 Ваучер 1 ҳафта — 450 алмаз", "price": 18, "category": "vouchers"},
    "month": {"name": "🎟 Ваучер 1 моҳ — 2600 алмаз", "price": 95, "category": "vouchers"},
    "lite": {"name": "🎟 Ваучер Лайт — 90 алмаз", "price": 7, "category": "vouchers"},
}

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# =========================================================
# 💾 STORAGE
# =========================================================

def load_json(filename, default):
    try:
        if not os.path.exists(filename):
            return default
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Read %s error: %s", filename, e)
        return default


def save_json(filename, data):
    temp = filename + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp, filename)


def load_products():
    saved = load_json(PRICES_FILE, {})
    products = json.loads(json.dumps(DEFAULT_PRODUCTS))
    if isinstance(saved, dict):
        for product_id, data in saved.items():
            if product_id in products and isinstance(data, dict):
                if isinstance(data.get("price"), int):
                    products[product_id]["price"] = data["price"]
    return products


def save_products(products):
    save_json(PRICES_FILE, products)


PRODUCTS = load_products()


# =========================================================
# 👤 USERS
# =========================================================

def save_user(user):
    users = load_json(USERS_FILE, {})

    # Backward compatibility: older bot versions may have saved users.json
    # as a list. Convert it to the new dictionary format automatically.
    if isinstance(users, list):
        converted = {}
        for item in users:
            if isinstance(item, dict) and item.get("id") is not None:
                converted[str(item["id"])] = item
        users = converted
    elif not isinstance(users, dict):
        users = {}

    users[str(user.id)] = {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "updated": datetime.now().isoformat(),
    }
    save_json(USERS_FILE, users)


def is_admin(user_id):
    return user_id in ADMIN_IDS


# =========================================================
# 🔐 SUBSCRIPTION
# =========================================================

async def is_subscribed(bot, user_id):
    try:
        member = await bot.get_chat_member(
            chat_id=CHANNEL_USERNAME,
            user_id=user_id,
        )
        if member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ):
            return True

        if (
            member.status == ChatMemberStatus.RESTRICTED
            and getattr(member, "is_member", False)
        ):
            return True

        return False
    except Exception as e:
        logger.error("Subscription check error: %s", e)
        return False


def subscription_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📢 Обуна шудан ба канал",
            url=CHANNEL_URL
        )],
        [InlineKeyboardButton(
            "✅ Ман обуна шудам",
            callback_data="check_subscription"
        )],
    ])


async def send_subscription_message(update):
    text = (
        "🔐 <b>Дастрасӣ маҳдуд аст</b>\n\n"
        "Барои истифодаи бот аввал ба канали мо обуна шавед.\n\n"
        "1️⃣ Ба канал дароед\n"
        "2️⃣ Обуна шавед\n"
        "3️⃣ «Ман обуна шудам»-ро пахш кунед\n\n"
        "⚡️ Бот обунаро фавран месанҷад."
    )

    if update.callback_query:
        await update.callback_query.message.edit_text(
            text,
            reply_markup=subscription_keyboard(),
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=subscription_keyboard(),
            parse_mode="HTML",
        )


# =========================================================
# 🏠 USER MENU
# =========================================================

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Хариди алмаз", callback_data="products")],
        [InlineKeyboardButton("📦 Фармоишҳои ман", callback_data="my_orders")],
        [InlineKeyboardButton("ℹ️ Маълумот", callback_data="info")],
    ])


async def show_main_menu(update, context):
    lines = [
        "🔥 <b>DANATER FREE FIRE</b>",
        "",
        "🛍 <b>МАГАЗИНИ ОНЛАЙН</b>",
        "💎 Алмазҳо ва ваучерҳо дар як ҷо",
        "",
        "<b>💰 НАРХҲОИ ҲОЗИРА:</b>",
    ]
    for product in PRODUCTS.values():
        lines.append(f"• {product['name']} — <b>{product['price']} сомонӣ</b>")
    lines += [
        "",
        "⚡️ Интихоб кунед ва фармоиш диҳед:",
    ]
    text = "\n".join(lines)
    if update.callback_query:
        await update.callback_query.message.edit_text(
            text, reply_markup=main_menu(), parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            text, reply_markup=main_menu(), parse_mode="HTML"
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    save_user(update.effective_user)

    if not await is_subscribed(context.bot, update.effective_user.id):
        await send_subscription_message(update)
        return

    await show_main_menu(update, context)


async def check_subscription(update, context):
    query = update.callback_query
    await query.answer()

    if not await is_subscribed(context.bot, query.from_user.id):
        await query.answer(
            "❌ Шумо ҳоло ба канал обуна нашудаед!",
            show_alert=True,
        )
        return

    await query.answer("✅ Обуна тасдиқ шуд!")
    await show_main_menu(update, context)


# =========================================================
# 💎 PRODUCTS
# =========================================================

def category_keyboard(category):
    keyboard = []
    for product_id, product in PRODUCTS.items():
        if category == "all" or product["category"] == category:
            keyboard.append([
                InlineKeyboardButton(
                    f"{product['name']} — {product['price']} сомонӣ",
                    callback_data=f"buy:{product_id}",
                )
            ])
    keyboard.append([
        InlineKeyboardButton("⬅️ Бозгашт", callback_data="menu")
    ])
    return InlineKeyboardMarkup(keyboard)


async def products(update, context):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text(
        "🛒 <b>МАГАЗИН — АЛМАЗҲО ВА ВАУЧЕРҲО</b>\n\n"
        "💎 Ҳамаи маҳсулотҳо дар як ҷо. Маҳсулоти лозимаро интихоб кунед:",
        reply_markup=category_keyboard("all"),
        parse_mode="HTML",
    )


async def vouchers(update, context):
    # Барои backward compatibility бо callback-и версияҳои кӯҳна.
    await products(update, context)


async def buy_product(update, context):
    query = update.callback_query
    await query.answer()

    product_id = query.data.split(":", 1)[1]
    product = PRODUCTS.get(product_id)

    if not product:
        await query.message.reply_text("❌ Маҳсулот ёфт нашуд.")
        return

    context.user_data["product_id"] = product_id
    await query.message.edit_text(
        "🛒 <b>ФАРМОИШ</b>\n\n"
        f"📦 {product['name']}\n"
        f"💰 Нарх: <b>{product['price']} сомонӣ</b>\n\n"
        "🎮 Free Fire ID-и худро фиристед:",
        parse_mode="HTML",
    )


# =========================================================
# 🎮 ORDER FLOW
# =========================================================

async def receive_ff_id(update, context):
    product_id = context.user_data.get("product_id")
    if not product_id:
        return

    ff_id = update.message.text.strip()
    if not ff_id.isdigit() or not (5 <= len(ff_id) <= 15):
        await update.message.reply_text(
            "❌ Free Fire ID нодуруст аст.\n"
            "Танҳо рақам, одатан 5–15 рақам фиристед."
        )
        return

    context.user_data["ff_id"] = ff_id
    product = PRODUCTS[product_id]

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Alif", callback_data="pay:alif")],
        [InlineKeyboardButton("💳 Dushanbe City", callback_data="pay:city")],
        [InlineKeyboardButton("❌ Бекор кардан", callback_data="cancel_order")],
    ])

    await update.message.reply_text(
        "✅ <b>Маълумот қабул шуд</b>\n\n"
        f"📦 {product['name']}\n"
        f"💰 {product['price']} сомонӣ\n"
        f"🎮 Free Fire ID: <code>{ff_id}</code>\n\n"
        "💳 Усули пардохтро интихоб кунед:",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


async def choose_payment(update, context):
    query = update.callback_query
    await query.answer()

    payment = query.data.split(":", 1)[1]
    product_id = context.user_data.get("product_id")
    ff_id = context.user_data.get("ff_id")

    if not product_id or not ff_id:
        await query.message.reply_text(
            "❌ Фармоиш нопурра аст. /start-ро пахш кунед."
        )
        return

    context.user_data["payment"] = payment
    product = PRODUCTS[product_id]
    payment_name = "Alif" if payment == "alif" else "Dushanbe City"
    number = PAYMENT_NUMBERS[payment]

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 Ман чекро мефиристам", callback_data="receipt_help")],
        [InlineKeyboardButton("❌ Бекор кардан", callback_data="cancel_order")],
    ])

    await query.message.edit_text(
        "💳 <b>ПАРДОХТ</b>\n\n"
        f"📦 {product['name']}\n"
        f"💰 Нарх: <b>{product['price']} сомонӣ</b>\n"
        f"🎮 Free Fire ID: <code>{ff_id}</code>\n"
        f"💳 Усул: <b>{payment_name}</b>\n"
        f"📱 Рақами пардохт: <code>{number}</code>\n\n"
        "1️⃣ Ба рақами боло пардохт кунед.\n"
        "2️⃣ Скриншоти чекро ҳамчун <b>Photo</b> фиристед.",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


async def receipt_help(update, context):
    query = update.callback_query
    await query.answer("Ҳоло скриншоти чекро фиристед.")
    await query.message.reply_text(
        "📸 Акнун скриншоти чеки пардохтро ҳамчун Photo фиристед."
    )


async def receive_receipt(update, context):
    product_id = context.user_data.get("product_id")
    ff_id = context.user_data.get("ff_id")
    payment = context.user_data.get("payment")

    if not product_id or not ff_id or not payment:
        return

    product = PRODUCTS[product_id]
    user = update.effective_user

    orders = load_json(ORDERS_FILE, [])
    if not isinstance(orders, list):
        orders = []

    order_id = (max([int(o.get("order_id", 0)) for o in orders] or [0]) + 1)
    username = f"@{user.username}" if user.username else "Надорад"
    payment_name = "Alif" if payment == "alif" else "Dushanbe City"

    order = {
        "order_id": order_id,
        "user_id": user.id,
        "username": username,
        "first_name": user.first_name,
        "ff_id": ff_id,
        "product_id": product_id,
        "product": product["name"],
        "price": product["price"],
        "payment": payment_name,
        "status": "pending",
        "created": datetime.now().isoformat(),
    }
    orders.append(order)
    save_json(ORDERS_FILE, orders)

    photo = update.message.photo[-1]
    caption = (
        "🆕 <b>ЗАКАЗИ НАВ!</b>\n\n"
        f"🧾 Заказ: <b>#{order_id}</b>\n"
        f"👤 Ном: {user.first_name}\n"
        f"🔗 Username: {username}\n"
        f"🆔 Telegram ID: <code>{user.id}</code>\n"
        f"🎮 Free Fire ID: <code>{ff_id}</code>\n\n"
        f"📦 {product['name']}\n"
        f"💰 {product['price']} сомонӣ\n"
        f"💳 Пардохт: {payment_name}\n"
        "⏳ Статус: <b>Интизорӣ</b>"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Тасдиқ", callback_data=f"admin_done:{order_id}"),
            InlineKeyboardButton("❌ Рад", callback_data=f"admin_cancel:{order_id}"),
        ],
    ])

    sent = 0
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=photo.file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            sent += 1
        except Exception as e:
            logger.error("Admin notification error: %s", e)

    await update.message.reply_text(
        "✅ <b>ФАРМОИШ ҚАБУЛ ШУД!</b>\n\n"
        f"🧾 Рақами фармоиш: <b>#{order_id}</b>\n"
        f"📦 {product['name']}\n"
        f"💰 {product['price']} сомонӣ\n\n"
        "⏳ Админ чекро месанҷад.",
        parse_mode="HTML",
    )
    context.user_data.clear()


# =========================================================
# 👨‍💼 ADMIN PANEL
# =========================================================

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Фармоишҳо", callback_data="admin_orders"),
         InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Корбарон", callback_data="admin_users"),
         InlineKeyboardButton("💰 Нархҳо", callback_data="admin_prices")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
         InlineKeyboardButton("💳 Пардохтҳо", callback_data="admin_payments")],
        [InlineKeyboardButton("🔄 Навсозии нархҳо", callback_data="admin_prices")],
    ])


async def admin_command(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Дастрасӣ манъ аст.")
        return

    await update.message.reply_text(
        "👑 <b>ПАНЕЛИ ADMIN — PROFESSIONAL V2</b>\n\n"
        "Аз меню амали лозимаро интихоб кунед:",
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )


async def admin_orders(update, context):
    query = update.callback_query
    orders = load_json(ORDERS_FILE, [])
    if not isinstance(orders, list):
        orders = []

    if not orders:
        text = "📦 <b>ФАРМОИШҲО</b>\n\nҲоло фармоиш нест."
    else:
        status_names = {
            "pending": "⏳ Интизорӣ",
            "completed": "✅ Иҷро шуд",
            "cancelled": "❌ Рад шуд",
        }
        recent = orders[-15:]
        lines = ["📦 <b>ФАРМОИШҲОИ ОХИРИН</b>\n"]
        for o in reversed(recent):
            lines.append(
                f"🧾 <b>#{o.get('order_id')}</b> — {status_names.get(o.get('status'), '❓')}\n"
                f"📦 {o.get('product')}\n"
                f"💰 {o.get('price')} сомонӣ\n"
                f"👤 {o.get('username', 'Надорад')}\n"
                f"🎮 <code>{o.get('ff_id')}</code>\n"
            )
        text = "\n".join(lines)

    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Навсозӣ", callback_data="admin_orders")],
            [InlineKeyboardButton("⬅️ Панели админ", callback_data="admin_home")],
        ]),
        parse_mode="HTML",
    )


async def admin_stats(update, context):
    query = update.callback_query
    orders = load_json(ORDERS_FILE, [])
    users = load_json(USERS_FILE, {})
    if not isinstance(orders, list):
        orders = []
    if not isinstance(users, dict):
        users = {}

    completed = [o for o in orders if o.get("status") == "completed"]
    pending = [o for o in orders if o.get("status") == "pending"]
    cancelled = [o for o in orders if o.get("status") == "cancelled"]
    revenue = sum(float(o.get("price", 0)) for o in completed)

    text = (
        "📊 <b>СТАТИСТИКА</b>\n\n"
        f"👥 Корбарон: <b>{len(users)}</b>\n"
        f"📦 Ҳамаи фармоишҳо: <b>{len(orders)}</b>\n"
        f"⏳ Интизорӣ: <b>{len(pending)}</b>\n"
        f"✅ Иҷрошуда: <b>{len(completed)}</b>\n"
        f"❌ Радшуда: <b>{len(cancelled)}</b>\n"
        f"💰 Даромади тасдиқшуда: <b>{revenue:g} сомонӣ</b>"
    )
    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Панели админ", callback_data="admin_home")]
        ]),
        parse_mode="HTML",
    )


async def admin_users(update, context):
    query = update.callback_query
    users = load_json(USERS_FILE, {})
    if not isinstance(users, dict):
        users = {}

    lines = [f"👥 <b>КОРБАРОН: {len(users)}</b>\n"]
    for u in list(users.values())[-30:]:
        username = f"@{u.get('username')}" if u.get("username") else "Надорад"
        lines.append(
            f"• {u.get('first_name', '—')} | {username} | <code>{u.get('id')}</code>"
        )

    await query.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Панели админ", callback_data="admin_home")]
        ]),
        parse_mode="HTML",
    )


async def admin_prices(update, context):
    query = update.callback_query
    keyboard = []
    text = "💰 <b>ИДОРАКУНИИ НАРХҲО</b>\n\n"

    for product_id, product in PRODUCTS.items():
        text += f"🔹 {product['name']} — <b>{product['price']} сомонӣ</b>\n"
        keyboard.append([
            InlineKeyboardButton(
                f"✏️ {product['name']}",
                callback_data=f"edit_price:{product_id}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("⬅️ Панели админ", callback_data="admin_home")
    ])

    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def edit_price_start(update, context):
    query = update.callback_query
    product_id = query.data.split(":", 1)[1]
    product = PRODUCTS.get(product_id)

    if not product:
        await query.answer("Маҳсулот ёфт нашуд.", show_alert=True)
        return

    context.user_data["edit_price_id"] = product_id
    await query.answer()
    await query.message.reply_text(
        f"✏️ Нархи нав барои:\n<b>{product['name']}</b>\n\n"
        "Танҳо рақам фиристед. Масалан: <code>25</code>",
        parse_mode="HTML",
    )


async def receive_admin_text(update, context):
    if not is_admin(update.effective_user.id):
        return

    # 1) Иваз кардани нарх
    edit_id = context.user_data.get("edit_price_id")
    if edit_id:
        raw = update.message.text.strip().replace(",", ".")
        try:
            price = float(raw)
            if price <= 0 or price > 100000:
                raise ValueError
            if price.is_integer():
                price = int(price)
        except ValueError:
            await update.message.reply_text(
                "❌ Нарх нодуруст аст. Масалан: <code>25</code>",
                parse_mode="HTML",
            )
            return

        PRODUCTS[edit_id]["price"] = price
        save_products(PRODUCTS)
        product_name = PRODUCTS[edit_id]["name"]
        context.user_data.pop("edit_price_id", None)

        await update.message.reply_text(
            "✅ <b>НАРХ ИВАЗ ШУД!</b>\n\n"
            f"📦 {product_name}\n"
            f"💰 Нархи нав: <b>{price} сомонӣ</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Дидани нархҳо", callback_data="admin_prices")],
                [InlineKeyboardButton("👑 Панели админ", callback_data="admin_home")],
            ]),
            parse_mode="HTML",
        )
        return

    # 2) Рассылка
    if context.user_data.get("broadcast_mode"):
        text = update.message.text.strip()
        if not text:
            return

        users = load_json(USERS_FILE, {})
        success = 0
        failed = 0

        await update.message.reply_text("📢 Рассылка оғоз шуд...")

        for user_id in users.keys():
            try:
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=text,
                )
                success += 1
            except Exception:
                failed += 1

        context.user_data.pop("broadcast_mode", None)

        await update.message.reply_text(
            "📢 <b>РАССЫЛКА ТАМOM ШУД</b>\n\n"
            f"✅ Расид: <b>{success}</b>\n"
            f"❌ Нарасид: <b>{failed}</b>",
            parse_mode="HTML",
        )


async def admin_broadcast_start(update, context):
    query = update.callback_query
    context.user_data["broadcast_mode"] = True
    await query.answer()
    await query.message.reply_text(
        "📢 Матни рассылкаро фиристед.\n\n"
        "❌ Барои бекор кардан: /cancel"
    )


async def cancel_command(update, context):
    context.user_data.clear()
    await update.message.reply_text("❌ Амали ҷорӣ бекор карда шуд.")


async def admin_payments(update, context):
    query = update.callback_query
    await query.message.edit_text(
        "💳 <b>ПАРДОХТҲО</b>\n\n"
        f"Alif: <code>{PAYMENT_NUMBERS['alif']}</code>\n"
        f"Dushanbe City: <code>{PAYMENT_NUMBERS['city']}</code>\n\n"
        "Барои тағйири рақамҳо онҳоро дар қисми CONFIG-и файл иваз кунед.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Панели админ", callback_data="admin_home")]
        ]),
        parse_mode="HTML",
    )


async def admin_home_callback(update, context):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    await query.message.edit_text(
        "👑 <b>ПАНЕЛИ ADMIN — PROFESSIONAL V2</b>\n\n"
        "Аз меню амали лозимаро интихоб кунед:",
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )


# =========================================================
# ✅ ORDER ACTION
# =========================================================

async def admin_order_action(update, context):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("❌ Дастрасӣ манъ аст.", show_alert=True)
        return

    await query.answer()
    action, order_id = query.data.split(":", 1)

    orders = load_json(ORDERS_FILE, [])
    found = next(
        (o for o in orders if str(o.get("order_id")) == str(order_id)),
        None,
    )

    if not found:
        await query.message.reply_text("❌ Фармоиш ёфт нашуд.")
        return

    if found.get("status") != "pending":
        await query.answer("Ин фармоиш аллакай коркард шудааст.", show_alert=True)
        return

    if action == "admin_done":
        found["status"] = "completed"
        status_text = "✅ ТАСДИҚ ШУД"
        user_text = (
            f"✅ Фармоиши <b>#{order_id}</b> тасдиқ шуд!\n\n"
            "Фармоиши шумо иҷро мешавад."
        )
    else:
        found["status"] = "cancelled"
        status_text = "❌ РАД ШУД"
        user_text = (
            f"❌ Фармоиши <b>#{order_id}</b> рад шуд.\n\n"
            "Агар савол дошта бошед, бо админ тамос гиред."
        )

    found["processed_at"] = datetime.now().isoformat()
    save_json(ORDERS_FILE, orders)

    try:
        await context.bot.send_message(
            chat_id=found["user_id"],
            text=user_text,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error("User notification error: %s", e)

    try:
        await query.message.edit_caption(
            caption=(query.message.caption or "") + f"\n\n<b>{status_text}</b>",
            parse_mode="HTML",
            reply_markup=None,
        )
    except Exception:
        pass


# =========================================================
# 📦 MY ORDERS
# =========================================================

async def my_orders(update, context):
    query = update.callback_query
    await query.answer()

    orders = load_json(ORDERS_FILE, [])
    user_orders = [
        o for o in orders
        if o.get("user_id") == query.from_user.id
    ]

    status_names = {
        "pending": "⏳ Интизорӣ",
        "completed": "✅ Иҷро шуд",
        "cancelled": "❌ Рад шуд",
    }

    if not user_orders:
        text = "📦 <b>ФАРМОИШҲОИ МАН</b>\n\nҲоло фармоиш надоред."
    else:
        lines = ["📦 <b>ФАРМОИШҲОИ МАН</b>\n"]
        for order in user_orders[-10:]:
            lines.append(
                f"🧾 #{order.get('order_id')}\n"
                f"📦 {order.get('product')}\n"
                f"💰 {order.get('price')} сомонӣ\n"
                f"📌 {status_names.get(order.get('status'), '❓')}\n"
            )
        text = "\n".join(lines)

    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Бозгашт", callback_data="menu")]
        ]),
        parse_mode="HTML",
    )


# =========================================================
# ℹ️ INFO / CANCEL
# =========================================================

async def info(update, context):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text(
        "ℹ️ <b>DANATER FREE FIRE</b>\n\n"
        "💎 Хариди алмаз\n"
        "🎟 Хариди ваучер\n"
        "💳 Alif / Dushanbe City\n"
        "📦 Пайгирии фармоиш\n"
        "🔐 Санҷиши автоматии обуна\n\n"
        "Барои саволҳо бо админ тамос гиред.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Бозгашт", callback_data="menu")]
        ]),
        parse_mode="HTML",
    )


async def cancel_order(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.message.edit_text(
        "❌ Фармоиш бекор карда шуд.\n\n"
        "Барои оғози нав /start-ро пахш кунед."
    )


# =========================================================
# 🆔 ID
# =========================================================

async def my_id(update, context):
    await update.message.reply_text(
        f"🆔 Telegram ID-и шумо:\n\n<code>{update.effective_user.id}</code>",
        parse_mode="HTML",
    )


# =========================================================
# 🔘 CALLBACK ROUTER
# =========================================================

async def callback_router(update, context):
    data = update.callback_query.data

    if data == "check_subscription":
        await check_subscription(update, context)
    elif data == "products":
        await products(update, context)
    elif data == "vouchers":
        await vouchers(update, context)
    elif data == "menu":
        await show_main_menu(update, context)
    elif data == "my_orders":
        await my_orders(update, context)
    elif data == "info":
        await info(update, context)
    elif data.startswith("buy:"):
        await buy_product(update, context)
    elif data.startswith("pay:"):
        await choose_payment(update, context)
    elif data == "receipt_help":
        await receipt_help(update, context)
    elif data == "cancel_order":
        await cancel_order(update, context)
    elif data == "admin_home":
        await admin_home_callback(update, context)
    elif data == "admin_orders":
        if is_admin(update.effective_user.id):
            await admin_orders(update, context)
    elif data == "admin_stats":
        if is_admin(update.effective_user.id):
            await admin_stats(update, context)
    elif data == "admin_users":
        if is_admin(update.effective_user.id):
            await admin_users(update, context)
    elif data == "admin_prices":
        if is_admin(update.effective_user.id):
            await admin_prices(update, context)
    elif data == "admin_broadcast":
        if is_admin(update.effective_user.id):
            await admin_broadcast_start(update, context)
    elif data == "admin_payments":
        if is_admin(update.effective_user.id):
            await admin_payments(update, context)
    elif data.startswith("edit_price:"):
        if is_admin(update.effective_user.id):
            await edit_price_start(update, context)
    elif data.startswith("admin_done:") or data.startswith("admin_cancel:"):
        await admin_order_action(update, context)


# =========================================================
# ❗ ERROR
# =========================================================

async def error_handler(update, context):
    logger.error("Exception while handling update:", exc_info=context.error)


# =========================================================
# 🚀 MAIN
# =========================================================

def main():
    if TOKEN == "PASTE_YOUR_NEW_BOT_TOKEN_HERE":
        raise RuntimeError(
            "Аввал TOKEN-и боти навро дар TOKEN гузоред."
        )

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("id", my_id))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("cancel", cancel_command))

    application.add_handler(CallbackQueryHandler(callback_router))

    application.add_handler(
        MessageHandler(filters.PHOTO, receive_receipt)
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            receive_admin_text,
        ),
        group=0,
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            receive_ff_id,
        ),
        group=1,
    )

    application.add_error_handler(error_handler)

    print("🔥 DANATER FREE FIRE — PROFESSIONAL V2 запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
    
