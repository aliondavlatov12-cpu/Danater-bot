import json
import os
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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


logging.basicConfig(level=logging.INFO)


def load_orders():
    if os.path.exists(FILE):
        with open(FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_orders(data):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def create_order():
    orders = load_orders()
    return str(len(orders) + 1)


def shop_button():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🛒 Хариди алмаз",
                callback_data="buy"
            )
        ]
    ])


async def answer_safe(query):
    try:
        await query.answer()
    except:
        pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🔥 DANATER FREE FIRE 🔥\n\n"
        "💎 Ба мағозаи алмаз хуш омадед!",
        reply_markup=shop_button()
    )


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await answer_safe(query)

    keyboard = []

    for key, value in products.items():
        keyboard.append([
            InlineKeyboardButton(
                value,
                callback_data=f"product_{key}"
            )
        ])

    await query.message.reply_text(
        "💎 Алмазро интихоб кун:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def choose_product(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await answer_safe(query)

    product_id = query.data.split("_")[1]

    context.user_data["product"] = products[product_id]
    context.user_data["step"] = "id"

    await query.message.reply_text(
        "🎮 ID-и Free Fire-ро навис:"
    )


async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if context.user_data.get("step") != "id":
        return

    context.user_data["ff_id"] = update.message.text
    context.user_data["step"] = "check"

    await update.message.reply_text(
        "💳 Пардохт бо Алиф\n\n"
        f"📱 Рақам: {ALIIF}\n\n"
        "Чеки пардохтро ҳамчун акс ё файл фирист."
    )    
async def get_check(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if context.user_data.get("step") != "check":
        return

    order_id = create_order()

    orders = load_orders()

    orders[order_id] = {
        "client": update.message.from_user.id,
        "name": update.message.from_user.first_name,
        "product": context.user_data.get("product"),
        "ff_id": context.user_data.get("ff_id")
    }

    save_orders(orders)

    buttons = InlineKeyboardMarkup([
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
    ])

    caption = (
        f"📩 Заказ #{order_id}\n\n"
        f"📦 {orders[order_id]['product']}\n"
        f"🎮 ID: {orders[order_id]['ff_id']}\n"
        f"👤 {orders[order_id]['name']}\n"
        f"🆔 Telegram ID: {orders[order_id]['client']}"
    )

    if update.message.photo:

        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=update.message.photo[-1].file_id,
            caption=caption,
            reply_markup=buttons
        )

    elif update.message.document:

        await context.bot.send_document(
            chat_id=ADMIN_ID,
            document=update.message.document.file_id,
            caption=caption,
            reply_markup=buttons
        )

    await update.message.reply_text(
        "✅ Чек ба админ фиристода шуд."
    )


async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await answer_safe(query)

    action, order_id = query.data.split("_")

    orders = load_orders()

    if order_id not in orders:
        return

    client_id = orders[order_id]["client"]


    if action == "done":

        await context.bot.send_message(
            chat_id=client_id,
            text=(
                "✅ Алмазҳо дода шуданд!\n\n"
                "🙏 Ташаккур барои харид аз DANATER FREE FIRE"
            ),
            reply_markup=shop_button()
        )

    elif action == "cancel":

        await context.bot.send_message(
            chat_id=client_id,
            text=(
                "❌ Пардохт рад карда шуд."
            ),
            reply_markup=shop_button()
        )


    try:
        await query.edit_message_caption(
            caption=query.message.caption +
            "\n\n✅ Коркард шуд."
        )
    except:
        pass



app = (
    Application.builder()
    .token(TOKEN)
    .connect_timeout(30)
    .read_timeout(30)
    .write_timeout(30)
    .pool_timeout(30)
    .build()
)


app.add_handler(
    CommandHandler(
        "start",
        start
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
        admin_action,
        pattern="^(done|cancel)_"
    )
)


app.add_handler(
    MessageHandler(
        filters.PHOTO | filters.Document.ALL,
        get_check
    )
)


app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        get_id
    )
)


print("🔥 DANATER FREE FIRE кор карда истодааст")


app.run_polling()