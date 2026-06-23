import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Users Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'restaurant' -- 'admin' or 'restaurant'
    )
    ''')
    
    # 2. Restaurants Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS restaurants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        logo TEXT,
        status TEXT NOT NULL DEFAULT 'active', -- 'active', 'pending', 'inactive'
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')
    
    # 3. Categories Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
    )
    ''')
    
    # 4. Menu Items Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS menu_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        image_path TEXT,
        available INTEGER NOT NULL DEFAULT 1, -- 1 = True, 0 = False
        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
    )
    ''')
    
    # 5. Tables Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tables (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_id INTEGER NOT NULL,
        table_number TEXT NOT NULL,
        token TEXT UNIQUE NOT NULL,
        qr_code_path TEXT,
        FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
    )
    ''')
    
    # 6. Orders Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_id INTEGER NOT NULL,
        table_id INTEGER NOT NULL,
        total_price REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'preparing', 'completed', 'cancelled'
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE,
        FOREIGN KEY (table_id) REFERENCES tables(id) ON DELETE CASCADE
    )
    ''')
    
    # 7. Order Items Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        menu_item_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY (menu_item_id) REFERENCES menu_items(id) ON DELETE CASCADE
    )
    ''')
    
    # 8. Waiter Calls Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS waiter_calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_id INTEGER NOT NULL,
        table_id INTEGER NOT NULL,
        type TEXT NOT NULL, -- 'waiter' or 'bill'
        status TEXT NOT NULL DEFAULT 'active', -- 'active', 'resolved'
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE,
        FOREIGN KEY (table_id) REFERENCES tables(id) ON DELETE CASCADE
    )
    ''')
    
    # Create Default Super User if not exists
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        hashed_password = generate_password_hash("admin123")
        cursor.execute("INSERT INTO users (username, password, role) VALUES ('admin', ?, 'admin')", (hashed_password,))
        
    conn.commit()
    conn.close()

# User Actions
def add_user(username, password, role='restaurant'):
    conn = get_db()
    cursor = conn.cursor()
    hashed_password = generate_password_hash(password)
    try:
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                       (username, hashed_password, role))
        conn.commit()
        user_id = cursor.lastrowid
        return user_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def check_user(username, password):
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. First try checking by username
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    
    # 2. If not found, try checking by restaurant slug or restaurant name
    if not user:
        clean_name = username.lower().strip()
        cursor.execute("""
            SELECT u.* FROM users u 
            JOIN restaurants r ON r.user_id = u.id 
            WHERE LOWER(r.slug) = ? OR LOWER(r.name) = ? OR LOWER(r.name) LIKE ?
        """, (clean_name, clean_name, f"%{clean_name}%"))
        user = cursor.fetchone()
        
    conn.close()
    if user and check_password_hash(user['password'], password):
        return user
    return None

# Restaurant Actions
def create_restaurant(user_id, name, slug, logo=None):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO restaurants (user_id, name, slug, logo) VALUES (?, ?, ?, ?)",
                       (user_id, name, slug, logo))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_restaurant_by_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM restaurants WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res

def get_restaurant_by_slug(slug):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM restaurants WHERE slug = ?", (slug,))
    res = cursor.fetchone()
    conn.close()
    return res

def get_all_restaurants():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT r.*, u.username FROM restaurants r JOIN users u ON r.user_id = u.id")
    res = cursor.fetchall()
    conn.close()
    return res

def update_restaurant_status(restaurant_id, status):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE restaurants SET status = ? WHERE id = ?", (status, restaurant_id))
    conn.commit()
    conn.close()

def delete_restaurant(restaurant_id):
    conn = get_db()
    cursor = conn.cursor()
    # Get user_id first to delete the user account too
    cursor.execute("SELECT user_id FROM restaurants WHERE id = ?", (restaurant_id,))
    row = cursor.fetchone()
    if row:
        user_id = row['user_id']
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        # cascading deletes will handle categories, menu_items, tables, orders, etc.
    conn.commit()
    conn.close()

# Category Actions
def add_category(restaurant_id, name):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO categories (restaurant_id, name) VALUES (?, ?)", (restaurant_id, name))
    conn.commit()
    cat_id = cursor.lastrowid
    conn.close()
    return cat_id

def get_categories(restaurant_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM categories WHERE restaurant_id = ?", (restaurant_id,))
    res = cursor.fetchall()
    conn.close()
    return res

def delete_category(category_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    conn.commit()
    conn.close()

# Menu Item Actions
def add_menu_item(category_id, name, description, price, image_path=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO menu_items (category_id, name, description, price, image_path) VALUES (?, ?, ?, ?, ?)",
                   (category_id, name, description, price, image_path))
    conn.commit()
    item_id = cursor.lastrowid
    conn.close()
    return item_id

def get_menu_items(restaurant_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT m.*, c.name as category_name 
        FROM menu_items m 
        JOIN categories c ON m.category_id = c.id 
        WHERE c.restaurant_id = ?
    ''', (restaurant_id,))
    res = cursor.fetchall()
    conn.close()
    return res

def update_menu_item(item_id, name, description, price, image_path=None, available=1):
    conn = get_db()
    cursor = conn.cursor()
    if image_path:
        cursor.execute('''
            UPDATE menu_items 
            SET name = ?, description = ?, price = ?, image_path = ?, available = ? 
            WHERE id = ?
        ''', (name, description, price, image_path, available, item_id))
    else:
        cursor.execute('''
            UPDATE menu_items 
            SET name = ?, description = ?, price = ?, available = ? 
            WHERE id = ?
        ''', (name, description, price, available, item_id))
    conn.commit()
    conn.close()

def delete_menu_item(item_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM menu_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

# Table Actions
def add_table(restaurant_id, table_number, token, qr_code_path=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tables (restaurant_id, table_number, token, qr_code_path) VALUES (?, ?, ?, ?)",
                   (restaurant_id, table_number, token, qr_code_path))
    conn.commit()
    table_id = cursor.lastrowid
    conn.close()
    return table_id

def get_tables(restaurant_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tables WHERE restaurant_id = ? ORDER BY CAST(table_number AS INTEGER), table_number", (restaurant_id,))
    res = cursor.fetchall()
    conn.close()
    return res

def get_table_by_token(token):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tables WHERE token = ?", (token,))
    res = cursor.fetchone()
    conn.close()
    return res

def delete_table(table_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tables WHERE id = ?", (table_id,))
    conn.commit()
    conn.close()

# Order Actions
def create_order(restaurant_id, table_id, total_price, items):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO orders (restaurant_id, table_id, total_price) VALUES (?, ?, ?)",
                       (restaurant_id, table_id, total_price))
        order_id = cursor.lastrowid
        
        for item in items:
            cursor.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, price) VALUES (?, ?, ?, ?)",
                           (order_id, item['menu_item_id'], item['quantity'], item['price']))
        
        conn.commit()
        return order_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_orders(restaurant_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT o.*, t.table_number 
        FROM orders o 
        JOIN tables t ON o.table_id = t.id 
        WHERE o.restaurant_id = ? 
        ORDER BY o.created_at DESC
    ''', (restaurant_id,))
    res = cursor.fetchall()
    conn.close()
    return res

def get_order_details(order_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT oi.*, m.name as item_name 
        FROM order_items oi
        JOIN menu_items m ON oi.menu_item_id = m.id
        WHERE oi.order_id = ?
    ''', (order_id,))
    items = cursor.fetchall()
    
    cursor.execute('''
        SELECT o.*, t.table_number 
        FROM orders o 
        JOIN tables t ON o.table_id = t.id 
        WHERE o.id = ?
    ''', (order_id,))
    order = cursor.fetchone()
    
    conn.close()
    return {
        'order': order,
        'items': items
    }

def update_order_status(order_id, status):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()

# Waiter Call Actions
def create_waiter_call(restaurant_id, table_id, call_type):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO waiter_calls (restaurant_id, table_id, type) VALUES (?, ?, ?)",
                   (restaurant_id, table_id, call_type))
    conn.commit()
    call_id = cursor.lastrowid
    conn.close()
    return call_id

def get_waiter_calls(restaurant_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT w.*, t.table_number 
        FROM waiter_calls w 
        JOIN tables t ON w.table_id = t.id 
        WHERE w.restaurant_id = ? AND w.status = 'active' 
        ORDER BY w.created_at DESC
    ''', (restaurant_id,))
    res = cursor.fetchall()
    conn.close()
    return res

def resolve_waiter_call(call_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE waiter_calls SET status = 'resolved' WHERE id = ?", (call_id,))
    conn.commit()
    conn.close()
