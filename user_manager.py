import os
import psycopg2
from psycopg2 import pool
from datetime import date, datetime
from contextlib import contextmanager
import logging
from config import DATABASE_URL

logger = logging.getLogger(__name__)

logger.info(f"DATABASE_URL raw value: {repr(DATABASE_URL)}")

connection_pool = psycopg2.pool.SimpleConnectionPool(1, 20, dsn=DATABASE_URL)

@contextmanager
def get_connection():
    conn = connection_pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        connection_pool.putconn(conn)

def get_or_create_user(user_id, username=None, first_name=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (user_id, username, first_name) VALUES (%s, %s, %s) "
                "ON CONFLICT (user_id) DO UPDATE SET "
                "username = EXCLUDED.username, first_name = EXCLUDED.first_name "
                "RETURNING balance, subscription_end",
                (user_id, username, first_name)
            )
            return cur.fetchone()

def check_and_reset_expired(user_id):
    """Проверяет, не истекла ли подписка, и если да, обнуляет баланс и subscription_end."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT subscription_end, balance FROM users WHERE user_id = %s",
                (user_id,)
            )
            row = cur.fetchone()
            if not row:
                return False
            sub_end, balance = row
            if sub_end and sub_end < datetime.now():
                cur.execute(
                    "UPDATE users SET balance = 0, subscription_end = NULL WHERE user_id = %s",
                    (user_id,)
                )
                logger.info(f"Subscription expired for user {user_id}, balance reset to 0")
                return True
    return False

def get_balance(user_id):
    check_and_reset_expired(user_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
            res = cur.fetchone()
            return res[0] if res else 0

def add_tokens(user_id, amount, description, payment_id=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET balance = balance + %s WHERE user_id = %s RETURNING balance",
                (amount, user_id)
            )
            new_balance = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO transactions (user_id, amount, description, payment_id) VALUES (%s, %s, %s, %s)",
                (user_id, amount, description, payment_id)
            )
            logger.info(f"Added {amount} tokens to user {user_id}, new balance {new_balance}, payment_id={payment_id}")
            return new_balance

def deduct_tokens(user_id, amount, description):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT balance FROM users WHERE user_id = %s FOR UPDATE", (user_id,))
            row = cur.fetchone()
            if not row or row[0] < amount:
                return False
            cur.execute(
                "UPDATE users SET balance = balance - %s WHERE user_id = %s",
                (amount, user_id)
            )
            cur.execute(
                "INSERT INTO transactions (user_id, amount, description) VALUES (%s, %s, %s)",
                (user_id, -amount, description)
            )
            return True

def check_and_use_free_limit(user_id, bot_name):
    today = date.today()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT free_limit_per_day FROM prices WHERE bot_name = %s",
                (bot_name,)
            )
            price_row = cur.fetchone()
            if not price_row:
                return False
            free_limit = price_row[0]
            if free_limit <= 0:
                return False
            cur.execute(
                "SELECT usage_count FROM bot_usage WHERE user_id = %s AND bot_name = %s AND usage_date = %s",
                (user_id, bot_name, today)
            )
            usage_row = cur.fetchone()
            used = usage_row[0] if usage_row else 0
            if used < free_limit:
                if usage_row:
                    cur.execute(
                        "UPDATE bot_usage SET usage_count = usage_count + 1 WHERE user_id = %s AND bot_name = %s AND usage_date = %s",
                        (user_id, bot_name, today)
                    )
                else:
                    cur.execute(
                        "INSERT INTO bot_usage (user_id, bot_name, usage_date, usage_count) VALUES (%s, %s, %s, 1)",
                        (user_id, bot_name, today)
                    )
                return True
            else:
                return False

def get_price(bot_name):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT price_per_use FROM prices WHERE bot_name = %s", (bot_name,))
            row = cur.fetchone()
            return row[0] if row else 0

def update_subscription_end(user_id, end_date):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET subscription_end = %s WHERE user_id = %s",
                (end_date, user_id)
            )

def transaction_exists_by_payment(payment_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM transactions WHERE payment_id = %s",
                (payment_id,)
            )
            return cur.fetchone() is not None
