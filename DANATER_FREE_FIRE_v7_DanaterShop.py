# ============================================================
# DANATER FREE FIRE BOT — PART 1/3
# ============================================================

import os
import io
import csv
import html
import logging
import sqlite3
import json
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
REF_BONUS_PERCENT = 5

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
    "week":  {"name": "🎟 Ваучер 1 ҳафта — 450 алмаз", "price": 18,  "category": "voucher"},
    "month": {"name": "🎟 Ваучер 1 моҳ — 2600 алмаз", "price": 95,  "category": "voucher"},
    "lite":  {"name": "🎟 Ваучер Лайт — 90 алмаз", "price": 7,   "category": "voucher"},
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
        try:
            c.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'tg'")
        except sqlite3.OperationalError:
            pass
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
        c.execute("""CREATE TABLE IF NOT EXISTS account_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            username TEXT, owner_name TEXT, ff_id TEXT, torsy TEXT, emotions TEXT,
            binding TEXT, evolutions TEXT, price REAL NOT NULL, guarantor TEXT,
            photos TEXT NOT NULL, status TEXT DEFAULT 'pending',
            created_at TEXT, updated_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS ff_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            brand TEXT NOT NULL,
            model TEXT NOT NULL,
            general INTEGER NOT NULL,
            red_dot INTEGER NOT NULL,
            scope_2x INTEGER NOT NULL,
            scope_4x INTEGER NOT NULL,
            sniper INTEGER NOT NULL,
            free_look INTEGER NOT NULL,
            fire_button INTEGER NOT NULL,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(platform, brand, model)
        )""")
        conn.commit()

def seed_products():
    with db() as conn:
        c = conn.cursor()
        for pid, p in DEFAULT_PRODUCTS.items():
            c.execute("SELECT id FROM products WHERE id=?", (pid,))
            if not c.fetchone():
                c.execute("INSERT INTO products (id,name,price,category,active) VALUES (?,?,?,?,1)",
                          (pid, p["name"], p["price"], p["category"]))

        # Keep the displayed reward amount correct for the built-in voucher products
        # without overwriting admin-edited prices.
        voucher_names = {
            "week": "🎟 Ваучер 1 ҳафта — 450 алмаз",
            "month": "🎟 Ваучер 1 моҳ — 2600 алмаз",
            "lite": "🎟 Ваучер Лайт — 90 алмаз",
        }
        for pid, name in voucher_names.items():
            c.execute("UPDATE products SET name=? WHERE id=?", (name, pid))

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

# ---------- ACCOUNT MARKETPLACE ----------
def create_account_listing(data):
    now = datetime.now().isoformat()
    with db() as conn:
        cur = conn.execute("""INSERT INTO account_listings
            (user_id,username,owner_name,ff_id,torsy,emotions,binding,evolutions,price,guarantor,photos,status,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,'pending',?,?)""",
            (data["user_id"], data.get("username", ""), data.get("owner_name", ""),
             data.get("ff_id", ""), data.get("torsy", ""), data.get("emotions", ""),
             data.get("binding", ""), data.get("evolutions", ""), float(data["price"]),
             data.get("guarantor", ADMIN_USERNAME), json.dumps(data.get("photos", [])), now, now))
        conn.commit()
        return cur.lastrowid

def get_account_listing(aid):
    with db() as conn:
        row = conn.execute("SELECT * FROM account_listings WHERE id=?", (aid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["photos"] = json.loads(d.get("photos") or "[]")
    except (TypeError, json.JSONDecodeError):
        d["photos"] = []
    return d

def account_listings(status=None, limit=50):
    with db() as conn:
        if status:
            rows = conn.execute("SELECT * FROM account_listings WHERE status=? ORDER BY created_at DESC LIMIT ?", (status, limit)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM account_listings ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    out=[]
    for row in rows:
        d=dict(row)
        try: d["photos"]=json.loads(d.get("photos") or "[]")
        except (TypeError, json.JSONDecodeError): d["photos"]=[]
        out.append(d)
    return out

def update_account_status(aid, status):
    with db() as conn:
        conn.execute("UPDATE account_listings SET status=?, updated_at=? WHERE id=?", (status, datetime.now().isoformat(), aid))
        conn.commit()

def account_status_label(status):
    return {"pending":"⏳ Дар интизорӣ", "approved":"✅ Тасдиқшуда", "sold":"💰 Фурӯхта шуд", "cancelled":"❌ Бекор шуд"}.get(status, status)

# ---------- FREE FIRE SETTINGS ----------
# A broad smartphone catalog (smartphones only; keypad phones are intentionally excluded).
# Values are starting presets, not a guarantee of automatic headshots. Device response, FPS,
# refresh rate, screen protector and play style can require +/- 2-5 points.
PHONE_CATALOG = {
    "android": {
        "Samsung": "Galaxy A05,A05s,A06,A14,A15,A16,A24,A25,A26,A34,A35,A36,A54,A55,A56,S20,S20 FE,S21,S21 FE,S22,S22 Plus,S22 Ultra,S23,S23 FE,S23 Plus,S23 Ultra,S24,S24 FE,S24 Plus,S24 Ultra,S25,S25 Edge,S25 Plus,S25 Ultra,S26,S26 Plus,S26 Ultra,M12,M13,M14,M15,M16,M23,M33,M34,M35,M52,M53,M54,M55,F13,F14,F15,F23,F34,F54,Z Flip3,Z Flip4,Z Flip5,Z Flip6,Z Fold3,Z Fold4,Z Fold5,Z Fold6",
        "Xiaomi": "Mi 10,Mi 10T,Mi 11,Mi 11T,Mi 11T Pro,Mi 12,Mi 12 Pro,Mi 13,Mi 13 Pro,Mi 14,Mi 14 Ultra,Mi 15,Mi 15 Ultra,Xiaomi 12T,Xiaomi 13T,Xiaomi 14T,Xiaomi 15T",
        "Redmi": "Redmi 9,9A,9C,10,10C,10 2022,12,12C,13C,13,13 5G,14C,14C 5G,Note 9,Note 10,Note 10 Pro,Note 11,Note 11 Pro,Note 12,Note 12 Pro,Note 13,Note 13 Pro,Note 13 Pro Plus,Note 14,Note 14 Pro,Note 14 Pro Plus",
        "POCO": "C40,C50,C51,C55,C61,C65,M3,M4 Pro,M5,M5s,M6,M6 Pro,M7,M7 Pro,X3 NFC,X3 Pro,X4 Pro,X5,X5 Pro,X6,X6 Pro,X7,X7 Pro,F3,F4,F5,F5 Pro,F6,F6 Pro,F7,F7 Pro",
        "TECNO": "Spark 7,Spark 8,Spark 9,Spark 10,Spark 10 Pro,Spark 20,Spark 20 Pro,Spark 20C,Spark 30,Spark 30 Pro,Spark 40,Spark Go 2022,Spark Go 2023,Spark Go 2024,Spark Go 1,Camon 18,Camon 19,Camon 20,Camon 20 Pro,Camon 30,Camon 30 Pro,Camon 40,Camon 40 Pro,Pova 4,Pova 5,Pova 5 Pro,Pova 6,Pova 6 Pro,Pova 7,Pova 7 Pro",
        "Infinix": "Hot 10,Hot 11,Hot 12,Hot 20,Hot 30,Hot 40,Hot 50,Hot 50 Pro,Hot 60,Note 10,Note 11,Note 12,Note 30,Note 40,Note 50,GT 10 Pro,GT 20 Pro,GT 30 Pro,Zero 20,Zero 30,Zero 40",
        "HONOR": "X5,X5 Plus,X6,X6a,X7,X7a,X7b,X8,X8a,X8b,X9a,X9b,90 Lite,90,90 Pro,200 Lite,200,200 Pro,Magic5 Lite,Magic5 Pro,Magic6 Lite,Magic6 Pro,Magic7 Lite,Magic7 Pro,Magic V2,Magic V3",
        "Huawei": "P30,P30 Pro,P40,P40 Pro,P50,P50 Pro,P60,P60 Pro,Pura 70,Pura 70 Pro,Mate 20,Mate 30,Mate 40,Mate 50,Mate 60,Mate 70,Nova 7,Nova 8,Nova 9,Nova 10,Nova 11,Nova 12,Nova 13",
        "OPPO": "A15,A16,A17,A18,A38,A39,A40,A54,A57,A58,A59,A60,A74,A76,A77,A78,A79,A80,Reno 5,Reno 6,Reno 7,Reno 8,Reno 9,Reno 10,Reno 11,Reno 12,Reno 13,Find X3,Find X5,Find X6,Find X7,Find X8",
        "vivo": "Y12,Y15,Y16,Y17,Y20,Y21,Y22,Y27,Y28,Y33,Y35,Y36,Y37,Y38,Y39,Y50,Y55,Y56,Y58,V20,V21,V23,V25,V27,V29,V30,V40,V50,X60,X70,X80,X90,X100,X200",
        "realme": "C11,C12,C15,C21,C25,C30,C31,C33,C35,C51,C53,C55,C61,C63,C65,C67,C71,C75,C75x,9i,9 Pro,10,10 Pro,11,11 Pro,12,12 Pro,13,13 Pro,GT Neo 2,GT Neo 3,GT Neo 5,GT 5,GT 6,GT 7",
        "OnePlus": "Nord,Nord N10,Nord N20,Nord N30,Nord CE 2,Nord CE 3,Nord CE 4,Nord CE 5,8,8T,9,9 Pro,10 Pro,11,11R,12,12R,13,13R,13 Pro",
        "Motorola": "Moto E7,Moto E13,Moto E14,Moto E22,Moto E32,Moto E40,Moto G20,Moto G22,Moto G31,Moto G32,Moto G42,Moto G52,Moto G53,Moto G54,Moto G55,Moto G62,Moto G72,Moto G73,Moto G84,Moto G85,Edge 20,Edge 30,Edge 40,Edge 50,Edge 60",
        "Google Pixel": "Pixel 4,Pixel 4a,Pixel 5,Pixel 5a,Pixel 6,Pixel 6a,Pixel 6 Pro,Pixel 7,Pixel 7a,Pixel 7 Pro,Pixel 8,Pixel 8a,Pixel 8 Pro,Pixel 9,Pixel 9a,Pixel 9 Pro,Pixel 9 Pro XL,Pixel 10,Pixel 10 Pro",
        "ASUS": "ROG Phone 3,ROG Phone 5,ROG Phone 6,ROG Phone 7,ROG Phone 8,ROG Phone 9,Zenfone 8,Zenfone 9,Zenfone 10,Zenfone 11,Zenfone 12",
        "Sony": "Xperia 1 II,Xperia 1 III,Xperia 1 IV,Xperia 1 V,Xperia 1 VI,Xperia 1 VII,Xperia 5 II,Xperia 5 III,Xperia 5 IV,Xperia 5 V,Xperia 10 III,Xperia 10 IV,Xperia 10 V,Xperia 10 VI",
        "Nothing": "Phone 1,Phone 2,Phone 2a,Phone 3,CMF Phone 1",
        "Nubia": "RedMagic 6,RedMagic 7,RedMagic 8,RedMagic 9,RedMagic 10,RedMagic 11,Z40,Z50,Z60",
        "Lenovo": "Legion Phone Duel,Legion Phone Duel 2,Legion Y70,Legion Y90",
        "ZTE": "Axon 30,Axon 40,Axon 50,Axon 60,Blade A31,Blade A51,Blade A71,Blade V40,Blade V50",
        "TCL": "10L,20L,20 Pro,30,30 Plus,40,40 XL,50,50 5G",
        "Nokia": "Nokia 2.4,Nokia 3.4,Nokia 5.3,Nokia 5.4,Nokia 6.2,Nokia 7.2,Nokia 8.3,Nokia C10,Nokia C20,Nokia C21,Nokia C22,Nokia C32,Nokia G10,Nokia G11,Nokia G21,Nokia G22,Nokia G42,Nokia G50",
        "Meizu": "17,18,20,21,Note 9,Note 10",
        "Sharp": "Aquos R5G,Aquos R6,Aquos R7,Aquos R8,Aquos R9,Zero 5G",
        "Fairphone": "Fairphone 3,Fairphone 4,Fairphone 5,Fairphone 6",
        "itel": "A48,A49,A60,A70,P17,P18,P36,P40,P55",
        "Black Shark": "Black Shark 2,Black Shark 3,Black Shark 4,Black Shark 5,Black Shark 6,Black Shark 7",
        "HTC": "U11,U12+,U20,Desire 20,Desire 21,Desire 22,Desire 23",
        "LG": "V30,V40,V50,V60,G7,G8,G8X,K40,K50,K51,K52",
        "Microsoft": "Surface Duo,Surface Duo 2",
        "Doogee": "S35,S40,S59,S61,S89,S100,V20,V30,V30T",
        "Ulefone": "Armor 9,Armor 10,Armor 12,Armor 17,Armor 21,Armor 22,Note 12,Note 16",
        "Oukitel": "C21,C22,C25,C31,C35,WP19,WP21,WP22,WP30",
        "Blackview": "A60,A80,A90,A95,BL5000,BL8800,BV5200,BV6200,BV9300",
        "UMIDIGI": "A9,A11,A13,A15,Bison,Bison GT,Bison X10,G5,G6",
        "Alcatel": "1,1B,1S,3,3X,5,7",
        "Coolpad": "Cool 10,Cool 12A,Cool 20,Cool 30,Cool S",
        "Lava": "Z2,Z3,Z4,Z6,Agni 2,Blaze 2,Blaze 3",
        "Micromax": "IN 1,IN 2b,IN 2c,IN Note 1,IN Note 2",
        "iQOO": "Z3,Z5,Z6,Z7,Z9,Z10,Neo 6,Neo 7,Neo 8,Neo 9,Neo 10,11,12,13",
        "Blackview": "A60,A80,A90,A95,BL5000,BL8800,BV5200,BV6200,BV9300",
    },
    "ios": {
        "iPhone": "iPhone 6s,iPhone 6s Plus,iPhone 7,iPhone 7 Plus,iPhone 8,iPhone 8 Plus,iPhone X,iPhone XR,iPhone XS,iPhone XS Max,iPhone 11,iPhone 11 Pro,iPhone 11 Pro Max,iPhone SE 2020,iPhone 12,iPhone 12 mini,iPhone 12 Pro,iPhone 12 Pro Max,iPhone 13,iPhone 13 mini,iPhone 13 Pro,iPhone 13 Pro Max,iPhone SE 2022,iPhone 14,iPhone 14 Plus,iPhone 14 Pro,iPhone 14 Pro Max,iPhone 15,iPhone 15 Plus,iPhone 15 Pro,iPhone 15 Pro Max,iPhone 16,iPhone 16 Plus,iPhone 16 Pro,iPhone 16 Pro Max,iPhone 16e,iPhone 17,iPhone 17 Air,iPhone 17 Pro,iPhone 17 Pro Max"
    }
}

def _preset_for_model(platform, brand, model):
    # Free Fire currently uses a 0–200 sensitivity scale in many current clients.
    # These are tuned starting profiles, not an automatic-headshot guarantee.
    m=(brand+' '+model).lower()
    h=int(hashlib.sha256(m.encode('utf-8')).hexdigest()[:8],16)
    d=(h % 7) - 3  # stable model-specific variation: -3..+3
    if platform == 'ios':
        if 'pro max' in m or 'pro max' in model.lower(): base=(176,171,161,151,96,140,46)
        elif 'pro' in m: base=(178,173,163,153,97,141,46)
        elif any(x in m for x in ('se','mini','xr','xs','11','12')): base=(184,179,169,158,100,145,48)
        else: base=(180,175,165,155,98,142,47)
    elif any(x in m for x in ('rog phone','redmagic','legion','black shark','gt 7','gt 6','s25','s26','s24 ultra','s23 ultra','pixel 10','pixel 9 pro')):
        base=(176,171,161,151,94,140,46)
    elif any(x in m for x in ('a0','c1','c2','c3','spark go','hot 10','hot 11','nokia c','itel a','moto e','blade a3','blade a5')):
        base=(194,187,177,165,109,172,52)
    elif any(x in m for x in ('pro','ultra','plus','t pro','x pro','note 13 pro','note 14 pro','poco f','poco x6','poco x7')):
        base=(183,177,167,156,99,145,49)
    else:
        base=(188,182,172,160,105,150,50)
    # Different phones get slightly different profiles while staying in practical ranges.
    vals=[base[0]+d, base[1]+d, base[2]+d, base[3]+d, base[4], base[5]+d, base[6]]
    vals[0]=max(0,min(200,vals[0])); vals[1]=max(0,min(200,vals[1])); vals[2]=max(0,min(200,vals[2])); vals[3]=max(0,min(200,vals[3])); vals[5]=max(0,min(200,vals[5]))
    return tuple(vals)

DEFAULT_FF_SETTINGS = []
for _platform, _brands in PHONE_CATALOG.items():
    for _brand, _models in _brands.items():
        for _model in [x.strip() for x in _models.split(',') if x.strip()]:
            DEFAULT_FF_SETTINGS.append((_platform, _brand, _model, *_preset_for_model(_platform, _brand, _model)))

def seed_ff_settings():
    with db() as conn:
        for row in DEFAULT_FF_SETTINGS:
            conn.execute("""INSERT OR IGNORE INTO ff_settings
                (platform,brand,model,general,red_dot,scope_2x,scope_4x,sniper,free_look,fire_button,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", row + (datetime.now().isoformat(), datetime.now().isoformat()))
        conn.commit()

def get_ff_platforms():
    with db() as conn:
        return conn.execute("SELECT DISTINCT platform FROM ff_settings ORDER BY CASE platform WHEN 'android' THEN 1 WHEN 'ios' THEN 2 ELSE 3 END").fetchall()

def get_ff_brands(platform):
    with db() as conn:
        return conn.execute("SELECT DISTINCT brand FROM ff_settings WHERE platform=? ORDER BY brand", (platform,)).fetchall()

def get_ff_models(platform, brand):
    with db() as conn:
        return conn.execute("SELECT * FROM ff_settings WHERE platform=? AND brand=? ORDER BY model", (platform, brand)).fetchall()

def get_ff_setting(setting_id):
    with db() as conn:
        return conn.execute("SELECT * FROM ff_settings WHERE id=?", (setting_id,)).fetchone()

def add_ff_setting(platform, brand, model, values):
    now=datetime.now().isoformat()
    with db() as conn:
        conn.execute("""INSERT INTO ff_settings
            (platform,brand,model,general,red_dot,scope_2x,scope_4x,sniper,free_look,fire_button,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(platform,brand,model) DO UPDATE SET
              general=excluded.general, red_dot=excluded.red_dot, scope_2x=excluded.scope_2x,
              scope_4x=excluded.scope_4x, sniper=excluded.sniper, free_look=excluded.free_look,
              fire_button=excluded.fire_button, updated_at=excluded.updated_at""",
            (platform, brand, model, *values, now, now))
        conn.commit()

def delete_ff_setting(setting_id):
    with db() as conn:
        conn.execute("DELETE FROM ff_settings WHERE id=?", (setting_id,))
        conn.commit()

def all_ff_settings():
    with db() as conn:
        return conn.execute("SELECT * FROM ff_settings ORDER BY platform, brand, model").fetchall()

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
# LANGUAGE / LOCALIZATION
# ============================================================
LANGS = {"tg": "🇹🇯 Тоҷикӣ", "ru": "🇷🇺 Русский"}
TEXTS = {
    "tg": {
        "shop":"🛒 Магазин","profile":"👤 Профил","orders":"📦 Фармоишҳои ман",
        "ref":"🎁 Реферал / Баланс","promo":"🎟 Активировать промокод","ff":"🎯 Настройки Free Fire",
        "buy_account":"🛍 Хариди аккаунт","sell_account":"💰 Фурӯши аккаунт","info":"ℹ️ Маълумот",
        "language":"🌐 Забон","menu":"⬅️ Меню","back":"⬅️ Бозгашт",
        "android":"🤖 Android","ios":"🍎 iPhone / iOS","language_choose":"🌐 <b>ЗАБОНРО ИНТИХОБ КУН</b>\n\nКадом забон ба ту қулай аст?",
        "choose_platform":"📱 Аввал системаи телефонро интихоб кун:","choose_brand":"Брендро интихоб кун:","choose_model":"Модели телефонро интихоб кун:",
        "settings_note":"⚡ Ин настройкаҳо старт-профил барои headshot мебошанд. Агар aim боло/поён равад, 2–5 пункт тағйир деҳ.",
    },
    "ru": {
        "shop":"🛒 Магазин","profile":"👤 Профиль","orders":"📦 Мои заказы",
        "ref":"🎁 Реферал / Баланс","promo":"🎟 Активировать промокод","ff":"🎯 Настройки Free Fire",
        "buy_account":"🛍 Купить аккаунт","sell_account":"💰 Продать аккаунт","info":"ℹ️ Информация",
        "language":"🌐 Язык","menu":"⬅️ Меню","back":"⬅️ Назад",
        "android":"🤖 Android","ios":"🍎 iPhone / iOS","language_choose":"🌐 <b>ВЫБЕРИ ЯЗЫК</b>\n\nКакой язык тебе удобнее?",
        "choose_platform":"📱 Сначала выбери систему телефона:","choose_brand":"Выбери бренд:","choose_model":"Выбери модель телефона:",
        "settings_note":"⚡ Это стартовый профиль для хедшотов. Если прицел уходит выше/ниже, меняй по 2–5 пунктов.",
    }
}
def get_lang(uid):
    row=get_user(uid)
    try:
        return row["language"] if row and row["language"] in LANGS else "tg"
    except Exception:
        return "tg"
def set_lang(uid, lang):
    if lang not in LANGS: return
    with db() as conn: conn.execute("UPDATE users SET language=? WHERE id=?", (lang, uid))
def tr(uid,key):
    lang=get_lang(uid); return TEXTS[lang].get(key, TEXTS["tg"].get(key,key))
def lang_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🇷🇺 Русский",callback_data="lang:ru"),InlineKeyboardButton("🇹🇯 Тоҷикӣ",callback_data="lang:tg")],[InlineKeyboardButton("⬅️ Меню",callback_data="menu")]])

# ============================================================
# KEYBOARDS
# ============================================================

def main_menu(uid=None):
    uid = uid or 0
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tr(uid,"shop"), callback_data="shop")],
        [InlineKeyboardButton(tr(uid,"profile"), callback_data="profile")],
        [InlineKeyboardButton(tr(uid,"orders"), callback_data="my_orders")],
        [InlineKeyboardButton(tr(uid,"ref"), callback_data="ref")],
        [InlineKeyboardButton(tr(uid,"promo"), callback_data="promo_user")],
        [InlineKeyboardButton(tr(uid,"ff"), callback_data="ffsettings")],
        [InlineKeyboardButton(tr(uid,"buy_account"), callback_data="accounts:buy")],
        [InlineKeyboardButton(tr(uid,"sell_account"), callback_data="accounts:sell")],
        [InlineKeyboardButton(tr(uid,"info"), callback_data="info")],
        [InlineKeyboardButton(tr(uid,"language"), callback_data="language")],
    ])

def shop_menu(is_admin_user=False, uid=0):
    lang=get_lang(uid)
    rows=[
        [InlineKeyboardButton("💎 Алмазы" if lang=="ru" else "💎 Алмазҳо",callback_data="cat:diamond")],
        [InlineKeyboardButton("🎟 Ваучеры" if lang=="ru" else "🎟 Ваучерҳо",callback_data="cat:voucher")],
        [InlineKeyboardButton("🎫 Pass / Elite",callback_data="cat:pass")],
        [InlineKeyboardButton("🔎 Поиск" if lang=="ru" else "🔎 Ҷустуҷӯ",callback_data="search")],
    ]
    if is_admin_user:
        rows += [[InlineKeyboardButton("➕ Маҳсулоти нав",callback_data="admin:add_product")],[InlineKeyboardButton("🗑 Нест кардани маҳсулот",callback_data="admin:del_product")]]
    rows.append([InlineKeyboardButton(tr(uid,"menu"),callback_data="menu")])
    return InlineKeyboardMarkup(rows)

def category_menu(cat, uid=0):
    items=get_products(cat); rows=[]
    for p in items:
        star=avg_rating(p["id"]); label=f"{p['name']} — {money(p['price'])} с."
        if star: label += f" ⭐{star}"
        rows.append([InlineKeyboardButton(label,callback_data=f"buy:{p['id']}")])
    rows.append([InlineKeyboardButton(tr(uid,"back"),callback_data="shop")])
    return InlineKeyboardMarkup(rows)

def account_cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Бекор", callback_data="cancel_account")]])

def account_photos_done_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Суратҳо тайёр", callback_data="account:photos_done")],
        [InlineKeyboardButton("❌ Бекор", callback_data="cancel_account")]
    ])

def account_admin_keyboard(aid):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Тасдиқ", callback_data=f"account_approve:{aid}"),
        InlineKeyboardButton("❌ Бекор", callback_data=f"account_cancel:{aid}")
    ]])

def account_buy_keyboard(aid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 Харидани аккаунт", callback_data=f"account_buy:{aid}")],
        [InlineKeyboardButton("⬅️ Аккаунтҳо", callback_data="accounts:buy")]
    ])

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
        [InlineKeyboardButton("💰 Аккаунтҳои фурӯш", callback_data="admin:accounts")],
        [InlineKeyboardButton("👥 Корбарон", callback_data="admin:users")],
        [InlineKeyboardButton("💰 Нархҳо", callback_data="admin:prices")],
        [InlineKeyboardButton("➕ Илова маҳсулот", callback_data="admin:add_product")],
        [InlineKeyboardButton("🗑 Нест маҳсулот", callback_data="admin:del_product")],
        [InlineKeyboardButton("🎁 Промокодҳо", callback_data="admin:promos")],
        [InlineKeyboardButton("🎯 FF Настройки", callback_data="admin:ffsettings")],
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
        "🔥 <b>DanaterShop</b>\n\n"
        "🛍️ <b>МАГАЗИНИ ОНЛАЙН</b>\n"
        "💎 Алмазҳо • Ваучерҳо • Pass\n\n"
        "Аз меню интихоб кунед 👇",
        reply_markup=main_menu(update.effective_user.id), parse_mode=ParseMode.HTML)


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

async def cb_language(update, context):
    q=update.callback_query; await q.answer()
    await q.message.edit_text(tr(q.from_user.id,"language_choose"),reply_markup=lang_keyboard(),parse_mode=ParseMode.HTML)

async def cb_set_language(update, context, lang):
    q=update.callback_query; set_lang(q.from_user.id,lang); await q.answer("✅")
    await q.message.edit_text("✅ Язык переключён на русский." if lang=="ru" else "✅ Забон ба тоҷикӣ гузошта шуд.",reply_markup=main_menu(q.from_user.id),parse_mode=ParseMode.HTML)

async def cb_ffsettings(update, context):
    q=update.callback_query; await q.answer()
    if not await require_sub(update, context): return
    rows=[[InlineKeyboardButton(tr(q.from_user.id,"android"),callback_data="ffplatform:android")],[InlineKeyboardButton(tr(q.from_user.id,"ios"),callback_data="ffplatform:ios")],[InlineKeyboardButton(tr(q.from_user.id,"menu"),callback_data="menu")]]
    await q.message.edit_text("🎯 <b>FREE FIRE SETTINGS</b> 🔥\n\n"+tr(q.from_user.id,"choose_platform"),reply_markup=InlineKeyboardMarkup(rows),parse_mode=ParseMode.HTML)

async def cb_ffplatform(update, context):
    q=update.callback_query; await q.answer()
    if not await require_sub(update, context): return
    platform=q.data.split(":",1)[1]
    brands=get_ff_brands(platform)
    rows=[[InlineKeyboardButton(f"📱 {b['brand']}", callback_data=f"ffbrand:{platform}:{b['brand']}")] for b in brands]
    rows.append([InlineKeyboardButton("⬅️ Бозгашт", callback_data="ffsettings")])
    title="🤖 ANDROID" if platform=="android" else "🍎 IPHONE / IOS"
    await q.message.edit_text(f"🎯 <b>{title}</b>\n\nМодели/брендро интихоб кунед:", reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML)

async def cb_ffbrand(update, context):
    q=update.callback_query; await q.answer()
    if not await require_sub(update, context): return
    _,platform,brand=q.data.split(":",2)
    models=get_ff_models(platform, brand)
    rows=[[InlineKeyboardButton(f"📱 {m['model']}", callback_data=f"ffmodel:{m['id']}")] for m in models]
    rows.append([InlineKeyboardButton("⬅️ Бозгашт", callback_data=f"ffplatform:{platform}")])
    await q.message.edit_text(f"📱 <b>{e(brand)}</b>\n\nМодели телефонро интихоб кунед:", reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML)

async def cb_ffmodel(update, context):
    q=update.callback_query; await q.answer()
    if not await require_sub(update, context): return
    sid=int(q.data.split(":",1)[1])
    s=get_ff_setting(sid)
    if not s:
        await q.answer("Настройка ёфт нашуд.", show_alert=True); return
    platform=s["platform"]
    text=(f"🔥 <b>FREE FIRE SETTINGS</b>\n\n"
          f"📱 <b>{e(s['brand'])} {e(s['model'])}</b>\n"
          f"━━━━━━━━━━━━━━\n"
          f"🎯 General: <b>{s['general']}</b>\n"
          f"🔴 Red Dot: <b>{s['red_dot']}</b>\n"
          f"🔭 2X Scope: <b>{s['scope_2x']}</b>\n"
          f"🔭 4X Scope: <b>{s['scope_4x']}</b>\n"
          f"🎯 Sniper Scope: <b>{s['sniper']}</b>\n"
          f"👀 Free Look: <b>{s['free_look']}</b>\n"
          f"🔘 Fire Button: <b>{s['fire_button']}%</b>\n\n"
          "💡 Ин preset барои aim/headshot ҳамчун нуқтаи оғоз аст; агар DPI, FPS ё услуби бозии шумо дигар бошад, каме танзим кунед.")
    await q.message.edit_text(text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Моделҳо", callback_data=f"ffbrand:{platform}:{s['brand']}")],
        [InlineKeyboardButton("🏠 Меню", callback_data="menu")],
    ]), parse_mode=ParseMode.HTML)

async def cb_promo_user(update, context):
    q=update.callback_query; await q.answer()
    if not await require_sub(update, context): return
    context.user_data["state"]="promo_user"
    await q.message.edit_text("🎟 <b>АКТИВИРОВАТЬ ПРОМОКОД</b>\n\nКоди промокодро фиристед:\nМисол: <code>SALE10</code>", reply_markup=cancel_kb(), parse_mode=ParseMode.HTML)

async def cb_accounts_buy(update, context):
    q=update.callback_query; await q.answer()
    if not await require_sub(update, context): return
    items=account_listings("approved", 30)
    if not items:
        await q.message.edit_text("🛍 <b>ХАРИДИ АККАУНТ</b>\n\nҲоло аккаунти тасдиқшуда барои фурӯш нест.", reply_markup=main_menu(update.effective_user.id), parse_mode=ParseMode.HTML)
        return
    rows=[]
    for a in items:
        rows.append([InlineKeyboardButton(f"🎮 Аккаунт #{a['id']} — {money(a['price'])} с.", callback_data=f"account_view:{a['id']}")])
    rows.append([InlineKeyboardButton("⬅️ Меню", callback_data="menu")])
    await q.message.edit_text("🛍 <b>АККАУНТҲО БАРОИ ФУРӮШ</b>\n\nАккаунтро интихоб кунед:", reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML)

async def cb_account_view(update, context):
    q=update.callback_query; await q.answer()
    a=get_account_listing(int(q.data.split(":",1)[1]))
    if not a or a["status"]!="approved":
        await q.answer("Ин аккаунт дастрас нест.", show_alert=True); return
    text=(f"🎮 <b>АККАУНТ #{a['id']}</b>\n\n"
          f"👕 Торсы: <b>{e(a['torsy'])}</b>\n😎 Эмоцияҳо: <b>{e(a['emotions'])}</b>\n"
          f"🔗 Привязка: <b>{e(a['binding'])}</b>\n⚡ Эволюция: <b>{e(a['evolutions'])}</b>\n"
          f"💰 Нарх: <b>{money(a['price'])} сомонӣ</b>\n👤 Владелец: <b>{e(a['owner_name'])}</b>\n"
          f"🛡 Гарант: <b>{e(a['guarantor'])}</b>\n\n📸 Суратҳо: {len(a['photos'])}")
    if a["photos"]:
        try:
            await q.message.delete()
        except TelegramError: pass
        for i,pid in enumerate(a["photos"]):
            try:
                await context.bot.send_photo(chat_id=q.from_user.id, photo=pid, caption=text if i==0 else None, reply_markup=account_buy_keyboard(a["id"]) if i==len(a["photos"])-1 else None, parse_mode=ParseMode.HTML if i==0 else None)
            except TelegramError: pass
    else:
        await q.message.edit_text(text, reply_markup=account_buy_keyboard(a["id"]), parse_mode=ParseMode.HTML)

async def cb_account_buy(update, context):
    q=update.callback_query; await q.answer()
    a=get_account_listing(int(q.data.split(":",1)[1]))
    if not a or a["status"]!="approved":
        await q.answer("Ин аккаунт аллакай дастрас нест.", show_alert=True); return
    u=update.effective_user
    uname=f"@{u.username}" if u.username else "—"
    msg=(f"🛍 <b>Дархости хариди аккаунт #{a['id']}</b>\n\n"
         f"💰 Нарх: <b>{money(a['price'])} сомонӣ</b>\n"
         f"👤 Харидор: {e(uname)}\n🆔 ID: <code>{u.id}</code>")
    for admin_id in ADMIN_IDS:
        try: await context.bot.send_message(admin_id, msg, parse_mode=ParseMode.HTML)
        except TelegramError: pass
    await q.message.reply_text("✅ Дархости шумо ба админ фиристода шуд. Барои харид админ бо шумо тамос мегирад.", reply_markup=main_menu(update.effective_user.id), parse_mode=ParseMode.HTML)

async def cb_account_cancel_user(update, context):
    q=update.callback_query; await q.answer("Бекор шуд.")
    context.user_data.clear()
    await q.message.edit_text("❌ <b>Фурӯши аккаунт бекор шуд.</b>", reply_markup=main_menu(update.effective_user.id), parse_mode=ParseMode.HTML)

async def cb_accounts_sell(update, context):
    q=update.callback_query; await q.answer()
    if not await require_sub(update, context): return
    context.user_data.clear(); context.user_data["state"]="account_photos"; context.user_data["account_photos"]=[]
    await q.message.edit_text("💰 <b>ФУРӮШИ АККАУНТ</b>\n\n📸 Суратҳои аккаунтатонро фиристед. Метавонед якчанд сурат фиристед.\n\nБаъд аз ҳамаи суратҳо тугмаи <b>«Суратҳо тайёр»</b>-ро пахш кунед.", reply_markup=account_photos_done_kb(), parse_mode=ParseMode.HTML)

async def cb_account_photos_done(update, context):
    q=update.callback_query; await q.answer()
    photos=context.user_data.get("account_photos",[])
    if not photos:
        await q.answer("Аввал ҳадди ақал 1 сурат фиристед.", show_alert=True); return
    context.user_data["state"]="account_ffid"
    await q.message.edit_text("🎮 <b>Free Fire ID-и аккаунтро фиристед:</b>", reply_markup=account_cancel_kb(), parse_mode=ParseMode.HTML)

async def cb_account_submit(update, context):
    q=update.callback_query; await q.answer()
    if not await require_sub(update, context): return
    d=context.user_data
    photos=d.get("account_photos",[])
    required=["account_ff_id","account_torsy","account_emotions","account_binding","account_evolutions","account_price","account_owner"]
    if not photos or any(k not in d for k in required):
        await q.answer("Маълумот пурра нест.", show_alert=True); return
    u=update.effective_user; uname=f"@{u.username}" if u.username else "—"
    aid=create_account_listing({"user_id":u.id,"username":uname,"owner_name":d["account_owner"],"ff_id":d["account_ff_id"],"torsy":d["account_torsy"],"emotions":d["account_emotions"],"binding":d["account_binding"],"evolutions":d["account_evolutions"],"price":d["account_price"],"guarantor":"@"+ADMIN_USERNAME,"photos":photos})
    caption=(f"🆕 <b>ДАРХОСТИ НАВИ ФУРӮШИ АККАУНТ #{aid}</b>\n\n"
             f"👤 Фурӯшанда: {e(uname)}\n🆔 Telegram ID: <code>{u.id}</code>\n"
             f"🎮 FF ID: <code>{e(d['account_ff_id'])}</code>\n👕 Торсы: <b>{e(d['account_torsy'])}</b>\n"
             f"😎 Эмоцияҳо: <b>{e(d['account_emotions'])}</b>\n🔗 Привязка: <b>{e(d['account_binding'])}</b>\n"
             f"⚡ Эволюция: <b>{e(d['account_evolutions'])}</b>\n💰 Нарх: <b>{money(d['account_price'])} сомонӣ</b>\n"
             f"👤 Владелец: <b>{e(d['account_owner'])}</b>\n🛡 Гарант: <b>@{e(ADMIN_USERNAME)}</b>\n📸 Суратҳо: {len(photos)}")
    for admin_id in ADMIN_IDS:
        for i,pid in enumerate(photos):
            try:
                await context.bot.send_photo(chat_id=admin_id, photo=pid, caption=caption if i==0 else None, reply_markup=account_admin_keyboard(aid) if i==0 else None, parse_mode=ParseMode.HTML if i==0 else None)
            except TelegramError as ex: logger.error("Account photo notify failed: %s", ex)
    context.user_data.clear()
    await q.message.edit_text("✅ <b>Ариза қабул шуд!</b>\n\n⏳ Суратҳо ва маълумоти аккаунт ба админ фиристода шуд. Пас аз тасдиқ аккаунт дар бахши «Хариди аккаунт» пайдо мешавад.", reply_markup=main_menu(update.effective_user.id), parse_mode=ParseMode.HTML)

async def cb_menu(update, context):
    q = update.callback_query
    await q.answer()
    if not await require_sub(update, context):
        return
    await q.message.edit_text(
        "🔥 <b>DanaterShop</b>\n\nАз меню интихоб кунед 👇",
        reply_markup=main_menu(update.effective_user.id), parse_mode=ParseMode.HTML)


async def cb_shop(update, context):
    q = update.callback_query
    await q.answer()
    if not await require_sub(update, context):
        return
    is_adm = is_admin(update.effective_user.id)
    await q.message.edit_text(
        "🛒 <b>МАГАЗИН</b>\n\nКатегорияро интихоб кунед:",
        reply_markup=shop_menu(is_adm, update.effective_user.id), parse_mode=ParseMode.HTML)


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
        reply_markup=category_menu(cat, update.effective_user.id), parse_mode=ParseMode.HTML)


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

    # Diamond amount is shown explicitly for vouchers/passes when configured.
    reward_map = {
        "week": "450 алмаз",
        "month": "2600 алмаз",
        "lite": "90 алмаз",
    }
    reward_line = f"\n💎 Мегиред: <b>{reward_map[pid]}</b>" if pid in reward_map else ""

    await q.message.edit_text(
        "🛒 <b>ФАРМОИШ</b>\n\n"
        f"📦 {e(p['name'])}{reward_line}\n"
        f"💰 Нарх: <b>{money(p['price'])} сомонӣ</b>{star_line}\n\n"
        "🎮 <b>Free Fire ID-и худро фиристед:</b>\n"
        "Мисол: <code>123456789</code>",
        reply_markup=cancel_kb(), parse_mode=ParseMode.HTML)


async def cb_cancel(update, context):
    q = update.callback_query
    await q.answer("Бекор шуд.")
    context.user_data.clear()
    await q.message.edit_text("❌ <b>Бекор шуд.</b>",
                              reply_markup=main_menu(update.effective_user.id), parse_mode=ParseMode.HTML)


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
        await q.message.edit_text("❌ Сессия гузашт.", reply_markup=main_menu(update.effective_user.id))
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
            reply_markup=main_menu(update.effective_user.id), parse_mode=ParseMode.HTML)
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

    await q.message.edit_text(text, reply_markup=main_menu(update.effective_user.id), parse_mode=ParseMode.HTML)


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
        "ℹ️ <b>DanaterShop</b>\n\n"
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

    # ADMIN: add/update Free Fire setting
    if is_admin(user.id) and state == "ff_setting_add":
        parts=[x.strip() for x in update.message.text.strip().split("|")]
        if len(parts) != 10:
            await update.message.reply_text(
                "❌ Формат нодуруст.\n\n"
                "<code>platform | brand | model | general | red_dot | 2x | 4x | sniper | free_look | fire_button</code>\n\n"
                "Мисол:\n<code>android | Samsung | Galaxy A56 | 195 | 185 | 180 | 170 | 145 | 175 | 50</code>",
                reply_markup=admin_back(), parse_mode=ParseMode.HTML)
            return
        platform,brand,model,*nums=parts
        platform=platform.lower()
        if platform not in {"android","ios"} or not brand or not model:
            await update.message.reply_text("❌ Platform бояд android ё ios бошад ва brand/model холӣ набошад.")
            return
        try:
            values=[int(x) for x in nums]
        except ValueError:
            await update.message.reply_text("❌ Ҳамаи 7 параметри охир бояд рақам бошанд.")
            return
        if not all(0 <= x <= 200 for x in values[:6]) or not 1 <= values[6] <= 100:
            await update.message.reply_text("❌ Sensitivity: 0–200, Fire Button: 1–100%.")
            return
        add_ff_setting(platform,brand,model,values)
        context.user_data.clear()
        await update.message.reply_text(
            f"✅ Настройка илова/нав шуд!\n\n📱 {e(brand)} {e(model)}\n"
            f"🎯 General: {values[0]} | 🔴 Red Dot: {values[1]} | 2X: {values[2]} | 4X: {values[3]}\n"
            f"🎯 Sniper: {values[4]} | 👀 Free Look: {values[5]} | 🔘 Fire Button: {values[6]}%",
            reply_markup=admin_menu(), parse_mode=ParseMode.HTML)
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

    # USER: promo activation
    if state == "promo_user":
        code=update.message.text.strip().upper()
        p=get_promo(code)
        if not p:
            await update.message.reply_text("❌ Промокод ёфт нашуд ё фаъол нест.")
            return
        if p["max_uses"] and p["used"] >= p["max_uses"]:
            await update.message.reply_text("❌ Промокод тамом шуд.")
            return
        context.user_data["promo"]={"code":p["code"],"discount_percent":p["discount_percent"]}
        context.user_data.pop("state",None)
        await update.message.reply_text(f"✅ Промокод <b>{e(p['code'])}</b> фаъол шуд (-{p['discount_percent']}%).", reply_markup=main_menu(update.effective_user.id), parse_mode=ParseMode.HTML)
        return

    # USER: account sale flow
    if state == "account_ffid":
        v=update.message.text.strip()
        if not v.isdigit() or not (5<=len(v)<=20):
            await update.message.reply_text("❌ Free Fire ID нодуруст."); return
        context.user_data["account_ff_id"]=v; context.user_data["state"]="account_torsy"
        await update.message.reply_text("👕 <b>Торсы чандто?</b>", reply_markup=account_cancel_kb(), parse_mode=ParseMode.HTML); return
    if state == "account_torsy":
        context.user_data["account_torsy"]=update.message.text.strip(); context.user_data["state"]="account_emotions"
        await update.message.reply_text("😎 <b>Эмоцияҳо чандто?</b>", reply_markup=account_cancel_kb(), parse_mode=ParseMode.HTML); return
    if state == "account_emotions":
        context.user_data["account_emotions"]=update.message.text.strip(); context.user_data["state"]="account_binding"
        await update.message.reply_text("🔗 <b>Привязкаи аккаунт чист?</b>\nМисол: Facebook / Google / VK / Guest", reply_markup=account_cancel_kb(), parse_mode=ParseMode.HTML); return
    if state == "account_binding":
        context.user_data["account_binding"]=update.message.text.strip(); context.user_data["state"]="account_evolutions"
        await update.message.reply_text("⚡ <b>Эволюцияҳо чандто?</b>", reply_markup=account_cancel_kb(), parse_mode=ParseMode.HTML); return
    if state == "account_evolutions":
        context.user_data["account_evolutions"]=update.message.text.strip(); context.user_data["state"]="account_price"
        await update.message.reply_text("💰 <b>Нархи аккаунтро бо сомонӣ нависед:</b>", reply_markup=account_cancel_kb(), parse_mode=ParseMode.HTML); return
    if state == "account_price":
        raw=update.message.text.strip().replace(",", ".")
        try: price=float(raw)
        except ValueError:
            await update.message.reply_text("❌ Нарх нодуруст. Масалан: 500"); return
        if price<=0 or price>1000000:
            await update.message.reply_text("❌ Нарх нодуруст."); return
        context.user_data["account_price"]=price; context.user_data["state"]="account_owner"
        await update.message.reply_text("👤 <b>Номи владелецро нависед:</b>", reply_markup=account_cancel_kb(), parse_mode=ParseMode.HTML); return
    if state == "account_owner":
        owner=update.message.text.strip()
        if not owner: await update.message.reply_text("❌ Ном холӣ буда наметавонад."); return
        context.user_data["account_owner"]=owner; context.user_data["state"]="account_submit"
        await update.message.reply_text("🛡 <b>Гарант:</b> @ffxdavlatov\n\nМаълумот тайёр аст. Барои фиристодан ба админ тугмаи поёнро пахш кунед.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📤 Фиристодан ба админ", callback_data="account:submit")],[InlineKeyboardButton("❌ Бекор", callback_data="cancel_account")]]), parse_mode=ParseMode.HTML); return

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

    # USER: account sale photos
    if context.user_data.get("state") == "account_photos":
        pid=update.message.photo[-1].file_id
        photos=context.user_data.setdefault("account_photos",[])
        if len(photos)>=10:
            await update.message.reply_text("❌ Максимум 10 сурат.", reply_markup=account_photos_done_kb()); return
        photos.append(pid)
        await update.message.reply_text(f"📸 Сурат қабул шуд: <b>{len(photos)}/10</b>", reply_markup=account_photos_done_kb(), parse_mode=ParseMode.HTML)
        return

    if context.user_data.get("state") != "waiting_receipt":
        await update.message.reply_text(
            "ℹ️ Аввал маҳсулотро интихоб кунед.", reply_markup=main_menu(update.effective_user.id))
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
            "❌ Сессия гузашт.", reply_markup=main_menu(update.effective_user.id))
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
        reply_markup=main_menu(update.effective_user.id), parse_mode=ParseMode.HTML)



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

    if data == "admin:ffsettings":
        await q.answer()
        rows=[
            [InlineKeyboardButton("➕ Илова / иваз кардани настройка", callback_data="admin:ffsettings_add")],
        ]
        settings=all_ff_settings()
        for s in settings[:80]:
            icon="🍎" if s["platform"]=="ios" else "🤖"
            rows.append([InlineKeyboardButton(f"{icon} {s['brand']} {s['model']}", callback_data=f"admin:ffsettings_view:{s['id']}")])
        rows.append([InlineKeyboardButton("⬅️ Admin", callback_data="admin:menu")])
        await q.message.edit_text(
            f"🎯 <b>FREE FIRE SETTINGS</b>\n\n📱 Настройкаҳо: <b>{len(settings)}</b>",
            reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML)
        return

    if data == "admin:ffsettings_add":
        await q.answer()
        context.user_data["state"]="ff_setting_add"
        await q.message.edit_text(
            "➕ <b>НАСТРОЙКАИ НАВИ FREE FIRE</b>\n\n"
            "Як сатр фиристед бо <b>|</b> ҷудо карда: \n"
            "<code>platform | brand | model | general | red_dot | 2x | 4x | sniper | free_look | fire_button</code>\n\n"
            "Platform: <code>android</code> ё <code>ios</code>\n"
            "Sensitivity: 0–200\nFire Button: 1–100%\n\n"
            "Мисол:\n<code>android | Samsung | Galaxy A56 | 195 | 185 | 180 | 170 | 145 | 175 | 50</code>",
            reply_markup=admin_back(), parse_mode=ParseMode.HTML)
        return

    if data.startswith("admin:ffsettings_view:"):
        await q.answer()
        sid=int(data.rsplit(":",1)[1])
        st=get_ff_setting(sid)
        if not st:
            await q.message.edit_text("❌ Настройка ёфт нашуд.", reply_markup=admin_back()); return
        text=(f"🎯 <b>{e(st['brand'])} {e(st['model'])}</b>\n\n"
              f"Platform: <code>{e(st['platform'])}</code>\n"
              f"General: <b>{st['general']}</b>\nRed Dot: <b>{st['red_dot']}</b>\n"
              f"2X: <b>{st['scope_2x']}</b>\n4X: <b>{st['scope_4x']}</b>\n"
              f"Sniper: <b>{st['sniper']}</b>\nFree Look: <b>{st['free_look']}</b>\n"
              f"Fire Button: <b>{st['fire_button']}%</b>")
        await q.message.edit_text(text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Иваз кардан", callback_data="admin:ffsettings_add")],
            [InlineKeyboardButton("🗑 Нест кардан", callback_data=f"admin:ffsettings_delete:{sid}")],
            [InlineKeyboardButton("⬅️ Рӯйхат", callback_data="admin:ffsettings")],
        ]), parse_mode=ParseMode.HTML)
        return

    if data.startswith("admin:ffsettings_delete:"):
        await q.answer()
        sid=int(data.rsplit(":",1)[1])
        if not get_ff_setting(sid):
            await q.answer("Настройка ёфт нашуд.",show_alert=True); return
        delete_ff_setting(sid)
        await q.answer("✅ Настройка нест шуд.",show_alert=True)
        settings=all_ff_settings()
        rows=[[InlineKeyboardButton("➕ Илова / иваз кардан",callback_data="admin:ffsettings_add")]]
        for srow in settings[:100]:
            icon="🍎" if srow["platform"]=="ios" else "🤖"
            rows.append([InlineKeyboardButton(f"{icon} {srow['brand']} {srow['model']}",callback_data=f"admin:ffsettings_view:{srow['id']}")])
        rows.append([InlineKeyboardButton("⬅️ Admin",callback_data="admin:menu")])
        await q.message.edit_text(f"🎯 <b>FREE FIRE SETTINGS</b>\n\n📱 Настройкаҳо: <b>{len(settings)}</b>",reply_markup=InlineKeyboardMarkup(rows),parse_mode=ParseMode.HTML)
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

    if data == "admin:accounts":
        await q.answer()
        items=account_listings("pending",50)
        if not items:
            await q.message.edit_text("💰 <b>АККАУНТҲО</b>\n\nАризаи нав нест.", reply_markup=admin_back(), parse_mode=ParseMode.HTML); return
        rows=[]
        for a in items:
            rows.append([InlineKeyboardButton(f"⏳ #{a['id']} — {money(a['price'])} с.", callback_data=f"admin_account_view:{a['id']}")])
        rows.append([InlineKeyboardButton("⬅️ Admin", callback_data="admin:menu")])
        await q.message.edit_text("💰 <b>АРИЗАҲОИ ФУРӮШИ АККАУНТ</b>", reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML); return

    if data.startswith("admin_account_view:"):
        await q.answer(); a=get_account_listing(int(data.split(":",1)[1]))
        if not a: await q.message.edit_text("❌ Ёфт нашуд.", reply_markup=admin_back()); return
        caption=(f"💰 <b>АККАУНТ #{a['id']}</b>\n\n👤 {e(a['username'])}\n🆔 <code>{a['user_id']}</code>\n🎮 FF ID: <code>{e(a['ff_id'])}</code>\n"
                 f"👕 Торсы: {e(a['torsy'])}\n😎 Эмоцияҳо: {e(a['emotions'])}\n🔗 Привязка: {e(a['binding'])}\n⚡ Эволюция: {e(a['evolutions'])}\n"
                 f"💰 Нарх: {money(a['price'])} с.\n👤 Владелец: {e(a['owner_name'])}\n🛡 Гарант: {e(a['guarantor'])}")
        for i,pid in enumerate(a['photos']):
            try: await context.bot.send_photo(chat_id=q.from_user.id, photo=pid, caption=caption if i==0 else None, reply_markup=account_admin_keyboard(a['id']) if i==0 else None, parse_mode=ParseMode.HTML if i==0 else None)
            except TelegramError: pass
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

    if data.startswith("account_approve:") or data.startswith("account_cancel:"):
        await q.answer()
        action, aid_s=data.split(":",1); aid=int(aid_s); a=get_account_listing(aid)
        if not a: await q.answer("Аккаунт ёфт нашуд.", show_alert=True); return
        if action=="account_approve":
            update_account_status(aid,"approved")
            status_text="✅ <b>Аккаунт тасдиқ шуд!</b>"
            user_text=f"✅ <b>Аккаунти шумо #{aid} тасдиқ шуд!</b>\n\nҲоло он дар бахши 🛍 <b>Хариди аккаунт</b> намоиш дода мешавад."
        else:
            update_account_status(aid,"cancelled")
            status_text="❌ <b>Ариза бекор шуд.</b>"
            user_text=f"❌ <b>Аризаи фурӯши аккаунти #{aid} бекор карда шуд.</b>"
        try: await context.bot.send_message(chat_id=int(a["user_id"]), text=user_text, reply_markup=main_menu(update.effective_user.id), parse_mode=ParseMode.HTML)
        except TelegramError: pass
        try: await q.message.edit_reply_markup(reply_markup=None)
        except TelegramError: pass
        await q.message.reply_text(status_text, parse_mode=ParseMode.HTML)
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

    if data == "language":
        await cb_language(update, context)
    elif data.startswith("lang:"):
        await cb_set_language(update, context, data.split(":",1)[1])
    elif data == "menu":
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
    elif data == "promo_user":
        await cb_promo_user(update, context)
    elif data == "ffsettings":
        await cb_ffsettings(update, context)
    elif data.startswith("ffplatform:"):
        await cb_ffplatform(update, context)
    elif data.startswith("ffbrand:"):
        await cb_ffbrand(update, context)
    elif data.startswith("ffmodel:"):
        await cb_ffmodel(update, context)
    elif data == "accounts:buy":
        await cb_accounts_buy(update, context)
    elif data == "accounts:sell":
        await cb_accounts_sell(update, context)
    elif data == "account:photos_done":
        await cb_account_photos_done(update, context)
    elif data == "account:submit":
        await cb_account_submit(update, context)
    elif data == "cancel_account":
        await cb_account_cancel_user(update, context)
    elif data.startswith("account_view:"):
        await cb_account_view(update, context)
    elif data.startswith("account_buy:"):
        await cb_account_buy(update, context)
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
          or data.startswith("delprod:") or data.startswith("account_approve:")
          or data.startswith("account_cancel:") or data.startswith("admin_account_view:")):
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
    return "DanaterShop is running", 200

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
    seed_ff_settings()

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

    logger.info("🔥 DanaterShop bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)


if __name__ == "__main__":
    main()
# ============================================================
# END OF FILE
# ============================================================
