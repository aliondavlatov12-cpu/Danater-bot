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


TOKEN = "8866087265:AAFulbHLhLwNcC3igxERA3-YbyWqKtSKQxY"

ADMIN_ID = 7659107145
ALIIF = "917003888"

FILE = "orders.json"


products = {
    "1": "💎 100 алмаз - 10 сомонӣ",
    "2": "💎 310 алмаз - 30 сомонӣ",
    "3": "💎 520 алмаз - 50 сомонӣ",
    "4": "💎 1060 алмаз - 100 сомонӣ",
    "5": "🎟 Ваучер 1 ҳафта - 450 алмаз - 18 сомонӣ",
    "6": "🎟 Ваучер 1 моҳ - 2600 алмаз - 105 сомонӣ"
}


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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

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


async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if context.user_data.get("step") == "id":

        context.user_data["ff_id"] = update.message.text
        context.user_data["step"] = "check"

        keyboard = [
            [
                InlineKeyboardButton(
                    "💳 Алиф",
                    callback_data="alif"
                )
            ]
        ]

        await update.message.reply_text(
            "Усули пардохт:",
            reply_markup=InlineKeyboardMarkup(keyboard)
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
        [InlineKeyboardButton("💰 Нархҳо", callback_data="admin_prices")]
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
        await query.message.reply_text(
            f"📦 Ҳамагӣ заказҳо: {len(orders)}"
        )

    elif query.data == "admin_users":
        await query.message.reply_text(
            "👥 Ин функсияро баъд илова мекунем."
        )

    elif query.data == "admin_send":
        await query.message.reply_text(
            "📢 Ин функсияро баъд илова мекунем."
        )

    elif query.data == "admin_prices":
        await query.message.reply_text(
            "💰 Ин функсияро баъд илова мекунем."
    )
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
        admin_action,
        pattern="^(done|cancel)_"
    )
)
app.add_handler(
    CallbackQueryHandler(
        admin_menu,
        pattern="^admin_"
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

try:
    app.run_polling(drop_pending_updates=True)
except NetworkError:
    print("NetworkError: Интернет қатъ шуд.")
    
