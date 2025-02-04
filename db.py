# db.py

import sqlite3
import threading
import logging
import dateutil.parser

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
                    districts TEXT,
                    is_active INTEGER DEFAULT 0,
                    from_owner INTEGER DEFAULT 0,
                    use_total_price INTEGER DEFAULT 0
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
            # Add the new listings table
            c.execute('''
                    CREATE TABLE IF NOT EXISTS listings (
                        id TEXT PRIMARY KEY,
                        title TEXT,
                        url TEXT,
                        price TEXT,
                        rent_additional TEXT,
                        location TEXT,
                        region_id TEXT,
                        region_name TEXT,
                        region_normalized_name TEXT,
                        district_id TEXT,
                        district_name TEXT,
                        area TEXT,
                        rooms TEXT,
                        is_business INTEGER,
                        description TEXT,
                        listing_time TIMESTAMP
                    )
                ''')
            c.execute('''
                        CREATE TABLE IF NOT EXISTS listing_log (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            listing_id TEXT,
                            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            c.execute('SELECT min_price, max_price, districts, from_owner, use_total_price FROM users WHERE user_id=?', (user_id,))
            result = c.fetchone()
            if result:
                min_price, max_price, districts, from_owner, use_total_price = result
                districts = districts.split(',') if districts else []
                districts = [d.strip() for d in districts if d.strip()]
                return {
                    'min_price': min_price,
                    'max_price': max_price,
                    'districts': districts,
                    'from_owner': bool(from_owner),
                    'use_total_price': bool(use_total_price)
                }
            else:
                return None
        except sqlite3.Error as e:
            logger.error(f"Database error when fetching user filters: {e}")
            return None
        finally:
            conn.close()

def set_user_filters(user_id, min_price=None, max_price=None, districts=None, from_owner=None, use_total_price=None):
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
                if from_owner is not None:
                    updates.append('from_owner=?')
                    params.append(int(from_owner))
                if use_total_price is not None:
                    updates.append('use_total_price=?')
                    params.append(int(use_total_price))
                params.append(user_id)
                sql = 'UPDATE users SET ' + ', '.join(updates) + ' WHERE user_id=?'
                c.execute(sql, params)
            else:
                districts_str = ','.join(districts) if districts else ''
                c.execute('INSERT INTO users (user_id, min_price, max_price, districts, is_active, from_owner, use_total_price) VALUES (?, ?, ?, ?, 0, ?, ?)',
                          (user_id, min_price, max_price, districts_str, int(from_owner or 0), int(use_total_price or 0)))
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
            c.execute('SELECT id FROM sent_listings WHERE user_id=? AND listing_id=? AND sent_at > datetime("now", "-2 days")', (user_id, listing_id))
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

def clean_old_listings():
    with db_lock:
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute('DELETE FROM listings WHERE listing_time < datetime("now", "-1 days")')
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error when cleaning old listings: {e}")
        finally:
            conn.close()

def set_user_active(user_id, is_active):
    with db_lock:
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute('UPDATE users SET is_active=? WHERE user_id=?', (int(is_active), user_id))
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error when setting user active status: {e}")
        finally:
            conn.close()

def get_active_users():
    with db_lock:
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute('SELECT user_id FROM users WHERE is_active=1')
            result = c.fetchall()
            return [row[0] for row in result]
        except sqlite3.Error as e:
            logger.error(f"Database error when fetching active users: {e}")
            return []
        finally:
            conn.close()

def save_listings_to_db(listings):
    with db_lock:
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            for listing in listings:
                c.execute('SELECT 1 FROM listings WHERE id=?', (listing.get('id'),))
                if not c.fetchone():
                    c.execute('''
                        INSERT INTO listings (
                            id, title, url, price, rent_additional, location,
                            region_id, region_name, region_normalized_name,
                            district_id, district_name, area, rooms,
                            is_business, description, listing_time
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        listing.get('id'),
                        listing.get('title'),
                        listing.get('url'),
                        listing.get('price'),
                        listing.get('rent_additional'),
                        listing.get('location'),
                        listing.get('region_id'),
                        listing.get('region_name'),
                        listing.get('region_normalized_name'),
                        listing.get('district_id'),
                        listing.get('district_name'),
                        listing.get('area'),
                        listing.get('rooms'),
                        int(listing.get('is_business', False)),
                        listing.get('description'),
                        listing.get('listing_time').isoformat() if listing.get('listing_time') else None
                    ))
                    c.execute('INSERT INTO listing_log (listing_id) VALUES (?)', (listing.get('id'),))
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error when saving listings: {e}")
        finally:
            conn.close()

def get_listings_from_db():
    with db_lock:
        try:
            conn = sqlite3.connect(DB_NAME)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM listings WHERE listing_time > datetime("now", "-1 days")')
            rows = c.fetchall()
            listings = []
            for row in rows:
                listing = dict(row)
                listing['is_business'] = bool(listing['is_business'])
                # Parse listing_time back to datetime object
                if listing.get('listing_time'):
                    listing['listing_time'] = dateutil.parser.parse(listing['listing_time'])
                listings.append(listing)
            return listings
        except sqlite3.Error as e:
            logger.error(f"Database error when fetching listings: {e}")
            return []
        finally:
            conn.close()

def get_new_listings_count():
    with db_lock:
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM listing_log')
            count = c.fetchone()[0]
            return count
        except sqlite3.Error as e:
            logger.error(f"Database error when counting new listings: {e}")
            return 0
        finally:
            conn.close()

def get_latest_listing_time():
    with db_lock:
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute('SELECT MAX(listing_time) FROM listings')
            result = c.fetchone()
            if result and result[0]:
                return dateutil.parser.parse(result[0])
            else:
                return None
        except sqlite3.Error as e:
            logger.error(f"Database error when getting latest listing time: {e}")
            return None
        finally:
            conn.close()
