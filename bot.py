import json
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest, NetworkError
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from threading import Thread
from flask import Flask

TOKEN = "8866087265:AAFulbHLhLwNcC3igxERA3-YbyWqKtSKQxY"

ADMIN_ID = 7659107145
ALIIF = "917003888"

FILE = "orders.json"
USERS_FILE = "users.json"
PRODUCTS_FILE = "products.json"
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4)
def load_products():
    if os.path.exists(PRODUCTS_FILE):
        with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_products(products):
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=4)
products = load_products()
if not products:
    products = {
    "1": "💎 100 алмаз - 10 сомонӣ",
    "2": "💎 310 алмаз - 30 сомонӣ",
    "3": "💎 520 алмаз - 50 сомонӣ",
    "4": "💎 1060 алмаз - 100 сомонӣ",
    "5": "🎟 Ваучер 1 ҳафта - 450 алмаз - 18 сомонӣ",
    "6": "🎟 Ваучер 1 моҳ - 2600 алмаз - 105 сомонӣ",
    "7": "🎟 Ваучер Лайт - 90 алмаз - 7 сомонӣ"
}

    save_products(products)

def load_orders():
    if os.path.exists(FILE):
        try:
            with open(FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_orders(data):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def create_order():
    orders = load_orders()
    return str(len(orders) + 1)


async def  start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    users = load_users()

    user_id = update.message.from_user.id

    if user_id not in users:
        users.append(user_id)
        save_users(users)
    keyboard = [
        [
            InlineKeyboardButton(
                "🛒 Хариди алмаз",
                callback_data="buy"
            )
        ]
    ]

    await update.message.reply_text(
        "🔥 DANATER FREE FIRE 🔥\n\n"
        "💎 Ба мағоза хуш омадед!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    try:
        await query.answer()
    except BadRequest:
        pass

    keyboard = []

    for k, v in products.items():
        keyboard.append(
            [
                InlineKeyboardButton(
                    v,
                    callback_data=f"product_{k}"
                )
            ]
        )

    await query.message.reply_text(
        "💎 Маҳсулотро интихоб кун:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def choose_product(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    try:
        await query.answer()
    except BadRequest:
        pass

    number = query.data.split("_")[1]

    context.user_data["product"] = products[number]
    context.user_data["step"] = "id"

    await query.message.reply_text(
        "🎮 ID-и Free Fire-атро навис:"
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.message.from_user.id != ADMIN_ID:
        return

    users = load_users()

    text = update.message.text

    count = 0

    for user_id in users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=text
            )
            count += 1
        except:
            pass

    await update.message.reply_text(
        f"✅ Рассылка фиристода шуд.\n👥 Ба {count} нафар"
    )
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("send_message"):

        await broadcast(update, context)

        context.user_data["send_message"] = False

        return
    if context.user_data.get("step") == "id":

        context.user_data["ff_id"] = update.message.text
        context.user_data["step"] = "check"

        keyboard = [
    [
        InlineKeyboardButton("💳 Алиф", callback_data="alif"),
        InlineKeyboardButton("🏦 Душанбе Сити", callback_data="dcnext")
    ]
        ]

        await update.message.reply_text(
            "Усули пардохт:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
async def dcnext(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    try:
        await query.answer()
    except BadRequest:
        pass

    context.user_data["step"] = "photo"

    await query.message.reply_text(
        "🏦 Пардохт бо Душанбе Сити\n\n"
        "📱 Рақам: +992 783 836 464\n\n"
        "📸 Чеки пардохтро ҳамчун акс фиристед."
    )
async def alif(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    try:
        await query.answer()
    except BadRequest:
        pass

    context.user_data["step"] = "photo"

    await query.message.reply_text(
        "💳 Пардохт бо Алиф\n\n"
        f"📱 Рақам: {ALIIF}\n\n"
        "Чеки пардохтро ҳамчун акс фирист."
    )


async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if context.user_data.get("step") != "photo":
        return

    order_id = create_order()

    orders = load_orders()

    orders[order_id] = {
        "client": update.message.from_user.id,
        "product": context.user_data.get("product"),
        "ff_id": context.user_data.get("ff_id")
    }

    save_orders(orders)

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Дода шуд",
                callback_data=f"done_{order_id}"
            ),
            InlineKeyboardButton(
                "❌ Рад шуд",
                callback_data=f"cancel_{order_id}"
            )
        ]
    ]

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=update.message.photo[-1].file_id,
        caption=(
            f"📩 Фармоиш #{order_id}\n\n"
            f"📦 {context.user_data.get('product')}\n"
            f"🎮 ID: {context.user_data.get('ff_id')}\n"
            f"👤 {update.message.from_user.first_name}\n"
            f"🆔 {update.message.from_user.id}"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await update.message.reply_text(
        "✅ Чек ба админ фиристода шуд."
    )


async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    try:
        await query.answer()
    except BadRequest:
        pass

    action, order_id = query.data.split("_")

    orders = load_orders()

    if order_id not in orders:
        return

    client_id = orders[order_id]["client"]


    if action == "done":

        await context.bot.send_message(
            chat_id=client_id,
            text="✅ Алмазҳо дода шуданд. Раҳмат!",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🛒 Хариди нав",
                            callback_data="buy"
                        )
                    ]
                ]
            )
        )

    else:

        await context.bot.send_message(
            chat_id=client_id,
            text="❌ Пардохт рад шуд."
        )

    await query.edit_message_caption(
        caption=query.message.caption + "\n\nИҷро шуд."
    )

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Шумо админ нестед.")
        return

    keyboard = [
        [InlineKeyboardButton("📦 Заказҳо", callback_data="admin_orders")],
        [InlineKeyboardButton("👥 Корбарон", callback_data="admin_users")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_send")],
        [InlineKeyboardButton("💰 Нархҳо", callback_data="admin_prices")],
          [InlineKeyboardButton("✏️ Иваз кардани нарх", callback_data="change_prices")]
      ]

    await update.message.reply_text(
        "👑 Панели админ",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    if query.data == "admin_orders":

        orders = load_orders()

        if not orders:
            await query.message.reply_text(
                "📦 Ҳоло заказ нест."
            )
            return

        text = "📦 Ҳамаи заказҳо:\n\n"

        for order_id, order in orders.items():

            text += (
                f"🆔 Заказ #{order_id}\n"
                f"📦 {order.get('product')}\n"
                f"🎮 ID: {order.get('ff_id')}\n"
                f"👤 User ID: {order.get('client')}\n\n"
            )

        await query.message.reply_text(text)


    elif query.data == "admin_users":

        users = load_users()

        await query.message.reply_text(
            f"👥 Корбарон: {len(users)} нафар"
        )


    elif query.data == "admin_send":

        await query.message.reply_text(
            "📢 Матни рассылкаро навис:"
        )

        context.user_data["send_message"] = True
    elif query.data.startswith("edit_price_"):

        product_id = query.data.replace("edit_price_", "")

        context.user_data["edit_price_id"] = product_id

        await query.message.reply_text(
            "💰 Нархи навро навис:"
        )
    elif query.data == "change_prices":

        await query.answer()

        keyboard = []

        for key, value in products.items():
            keyboard.append(
                [
                    InlineKeyboardButton(
                        value,
                        callback_data=f"edit_price_{key}"
                    )
                ]
            )

        await query.message.reply_text(
            "✏️ Кадом маҳсулотро иваз мекунӣ?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif query.data == "admin_prices":

        text = "💰 Нархҳои ҳозира:\n\n"

        for key, value in products.items():
            text += f"{key}. {value}\n"
        
        await query.message.reply_text(text)
app = Application.builder().token(TOKEN).build()


app.add_handler(
    CommandHandler(
        "start",
        start
    )
)
app.add_handler(
    CommandHandler(
        "admin",
        admin
    )
)
app.add_handler(
    CallbackQueryHandler(
        buy,
        pattern="^buy$"
    )
)

app.add_handler(
    CallbackQueryHandler(
        choose_product,
        pattern="^product_"
    )
)

app.add_handler(
    CallbackQueryHandler(
        alif,
        pattern="^alif$"
    )
)

app.add_handler(
    CallbackQueryHandler(
        dcnext,
        pattern="^dcnext$"
    )
)
app.add_handler(
    CallbackQueryHandler(
        admin_action,
        pattern="^(done|cancel)_"
    )
)
app.add_handler(
    CallbackQueryHandler(
        admin_menu,
        pattern="^(admin_|change_prices)"
    )
)
app.add_handler(
    MessageHandler(
        filters.PHOTO,
        get_photo
    )
)

app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        get_id
    )
)


async def error_handler(update, context):
    print(context.error)

app.add_error_handler(error_handler)

print("🔥 DANATER FREE FIRE кор карда истодааст")

web = Flask(__name__)

@web.route("/")
def home():
    return "Bot is running 24/7"


def run_web():
    web.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080))
    )


Thread(target=run_web).start()

try:
    app.run_polling(drop_pending_updates=True)
except NetworkError:
    print("NetworkError: Интернет қатъ шуд.")
