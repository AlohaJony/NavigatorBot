import psycopg2
from config import DATABASE_URL

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    first_name VARCHAR(255),
    balance INTEGER NOT NULL DEFAULT 0,
    subscription_end TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bot_usage (
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    bot_name VARCHAR(50) NOT NULL,
    usage_date DATE NOT NULL,
    usage_count INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, bot_name, usage_date)
);

CREATE TABLE IF NOT EXISTS prices (
    bot_name VARCHAR(50) PRIMARY KEY,
    price_per_use INTEGER NOT NULL,
    free_limit_per_day INTEGER DEFAULT 0
);
""")

# Добавим начальные цены (если таблица пуста)
cur.execute("SELECT COUNT(*) FROM prices")
if cur.fetchone()[0] == 0:
    cur.execute("""
    INSERT INTO prices (bot_name, price_per_use, free_limit_per_day) VALUES
        ('downloader', 0, 999999),
        ('pdf_converter', 0, 999999),
        ('audio_extractor', 5, 3),
        ('tts', 10, 2),
        ('image_gen', 15, 3);
    """)

conn.commit()
cur.close()
conn.close()
print("Database tables created (if not existed).")
