# db.py

import sqlite3
import threading
import logging

DB_NAME = 'listings.db'
db_lock = threading.Lock()
logger = logging.getLogger(__name__)

def init_db():
    logger.info("Initializing the database.")
    with db_lock:
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    min_price INTEGER,
                    max_price INTEGER,
                    districts TEXT
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS sent_listings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listing_id TEXT,
                    user_id INTEGER,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            ''')
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error during initialization: {e}")
        finally:
            conn.close()

def get_user_filters(user_id):
    with db_lock:
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute('SELECT min_price, max_price, districts FROM users WHERE user_id=?', (user_id,))
            result = c.fetchone()
            if result:
                min_price, max_price, districts = result
                districts = districts.split(',') if districts else []
                districts = [d.strip() for d in districts if d.strip()]
                return {'min_price': min_price, 'max_price': max_price, 'districts': districts}
            else:
                return None
        except sqlite3.Error as e:
            logger.error(f"Database error when fetching user filters: {e}")
            return None
        finally:
            conn.close()

def set_user_filters(user_id, min_price=None, max_price=None, districts=None):
    with db_lock:
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute('SELECT user_id FROM users WHERE user_id=?', (user_id,))
            if c.fetchone():
                updates = []
                params = []
                if min_price is not None:
                    updates.append('min_price=?')
                    params.append(min_price)
                if max_price is not None:
                    updates.append('max_price=?')
                    params.append(max_price)
                if districts is not None:
                    districts_str = ','.join(districts)
                    updates.append('districts=?')
                    params.append(districts_str)
                params.append(user_id)
                sql = 'UPDATE users SET ' + ', '.join(updates) + ' WHERE user_id=?'
                c.execute(sql, params)
            else:
                districts_str = ','.join(districts) if districts else ''
                c.execute('INSERT INTO users (user_id, min_price, max_price, districts) VALUES (?, ?, ?, ?)',
                          (user_id, min_price, max_price, districts_str))
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error when setting user filters: {e}")
        finally:
            conn.close()

def reset_user_filters(user_id):
    with db_lock:
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute('UPDATE users SET min_price=NULL, max_price=NULL, districts=NULL WHERE user_id=?', (user_id,))
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error when resetting user filters: {e}")
        finally:
            conn.close()

def has_user_received_listing(user_id, listing_id):
    with db_lock:
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute('SELECT id FROM sent_listings WHERE user_id=? AND listing_id=?', (user_id, listing_id))
            result = c.fetchone()
            return result is not None
        except sqlite3.Error as e:
            logger.error(f"Database error when checking sent listings: {e}")
            return False
        finally:
            conn.close()

def mark_listing_as_sent(user_id, listing_id):
    with db_lock:
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute('INSERT INTO sent_listings (user_id, listing_id, sent_at) VALUES (?, ?, CURRENT_TIMESTAMP)', (user_id, listing_id))
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error when marking listing as sent: {e}")
        finally:
            conn.close()

def clean_old_sent_listings():
    with db_lock:
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute('DELETE FROM sent_listings WHERE sent_at < datetime("now", "-2 days")')
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error when cleaning old sent listings: {e}")
        finally:
            conn.close()
