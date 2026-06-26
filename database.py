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
        theme_name TEXT NOT NULL DEFAULT 'classic_light', -- 'classic_light', 'modern_dark', 'luxury_gold', 'custom'
        theme_primary_color TEXT DEFAULT '#059669',
        theme_bg_color TEXT DEFAULT '#f8fafc',
        theme_surface_color TEXT DEFAULT '#ffffff',
        theme_text_color TEXT DEFAULT '#1e293b',
        currency TEXT NOT NULL DEFAULT 'IQD',
        phone TEXT DEFAULT '',
        address TEXT DEFAULT '',
        announcement TEXT DEFAULT '',
        menu_bg_image TEXT DEFAULT '',
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
        status TEXT NOT NULL DEFAULT 'available', -- 'available', 'occupied', 'billing'
        current_session_id TEXT,
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
        status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'preparing', 'served', 'paid', 'cancelled'
        session_id TEXT,
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
    
    # 9. Invoices Table (Archive)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_id INTEGER NOT NULL,
        table_id INTEGER NOT NULL,
        table_number TEXT NOT NULL,
        session_id TEXT NOT NULL,
        subtotal REAL NOT NULL,
        vat_rate REAL NOT NULL,
        vat_amount REAL NOT NULL,
        total_amount REAL NOT NULL,
        currency TEXT NOT NULL DEFAULT 'IQD',
        items_json TEXT NOT NULL, -- JSON formatted list of items
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE,
        FOREIGN KEY (table_id) REFERENCES tables(id) ON DELETE CASCADE
    )
    ''')
    
    # Run migrations for existing databases to ensure columns exist
    try:
        cursor.execute("ALTER TABLE tables ADD COLUMN status TEXT NOT NULL DEFAULT 'available'")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE tables ADD COLUMN current_session_id TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN session_id TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE tables ADD COLUMN capacity INTEGER DEFAULT 4")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE tables ADD COLUMN location TEXT DEFAULT 'الصالة الرئيسية'")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN order_type TEXT NOT NULL DEFAULT 'dine_in'")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN notes TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE restaurants ADD COLUMN theme_name TEXT NOT NULL DEFAULT 'classic_light'")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE restaurants ADD COLUMN theme_primary_color TEXT DEFAULT '#059669'")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE restaurants ADD COLUMN theme_bg_color TEXT DEFAULT '#f8fafc'")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE restaurants ADD COLUMN theme_surface_color TEXT DEFAULT '#ffffff'")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE restaurants ADD COLUMN theme_text_color TEXT DEFAULT '#1e293b'")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE restaurants ADD COLUMN currency TEXT NOT NULL DEFAULT 'IQD'")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE restaurants ADD COLUMN vat_enabled INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE restaurants ADD COLUMN vat_percentage REAL DEFAULT 15.0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE restaurants ADD COLUMN phone TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE restaurants ADD COLUMN address TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE restaurants ADD COLUMN announcement TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE restaurants ADD COLUMN menu_bg_image TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    
    # Ensure all existing restaurants have a سفري (takeaway) table
    import uuid as _uuid_mig
    cursor.execute("SELECT id FROM restaurants")
    all_restaurants = cursor.fetchall()
    for rest in all_restaurants:
        cursor.execute("SELECT id FROM tables WHERE restaurant_id = ? AND table_number = 'سفري'", (rest['id'],))
        if not cursor.fetchone():
            takeaway_token = f"takeaway_{_uuid_mig.uuid4().hex[:8]}"
            cursor.execute("INSERT INTO tables (restaurant_id, table_number, token, qr_code_path, capacity, location) VALUES (?, 'سفري', ?, NULL, 0, 'سفري')",
                           (rest['id'], takeaway_token))
    
    # Create Default Super User if not exists
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        hashed_password = generate_password_hash("admin123")
        cursor.execute("INSERT INTO users (username, password, role) VALUES ('admin', ?, 'admin')", (hashed_password,))
        
    # Seed default restaurant data if not exists
    cursor.execute("SELECT * FROM users WHERE username = 'مطعم المصطفى'")
    if not cursor.fetchone():
        # Insert restaurant user
        cursor.execute("INSERT INTO users (username, password, role) VALUES ('مطعم المصطفى', 'scrypt:32768:8:1$67SVJnhHp42IZxAK$32c99bed398564b7829192ddb4d2f80fc23dc66805ab3a77d502f9ca43ae4ff52660bc7d18539f0b64f9bb220e51e99e7a1ded0dccdc46b86166fc25c0e6bda2', 'restaurant')")
        user_id = cursor.lastrowid
        
        # Insert restaurant
        cursor.execute("""
            INSERT INTO restaurants (user_id, name, slug, logo, status, theme_name, theme_primary_color, theme_bg_color, theme_surface_color, theme_text_color, currency, vat_enabled, vat_percentage)
            VALUES (?, 'المصطفى للبرغر الممتاز', 'mostafa', 'logo_mostafa_a71302.jpg', 'active', 'custom', '#00ff00', '#222222', '#333333', '#dddddd', 'USD', 1, 15.0)
        """, (user_id,))
        restaurant_id = cursor.lastrowid
        
        # Insert categories
        cursor.execute("INSERT INTO categories (restaurant_id, name) VALUES (?, 'وجبات ساخنة')", (restaurant_id,))
        cat_hot = cursor.lastrowid
        cursor.execute("INSERT INTO categories (restaurant_id, name) VALUES (?, 'نارجيلة')", (restaurant_id,))
        cat_hookah = cursor.lastrowid
        
        # Insert menu items
        cursor.execute("INSERT INTO menu_items (category_id, name, description, price, available) VALUES (?, 'شاي', '', 500.0, 1)", (cat_hot,))
        cursor.execute("INSERT INTO menu_items (category_id, name, description, price, available) VALUES (?, 'بابلية', '', 10000.0, 1)", (cat_hookah,))
        cursor.execute("INSERT INTO menu_items (category_id, name, description, price, available) VALUES (?, 'خشب', '', 3000.0, 1)", (cat_hookah,))
        
        # Insert tables
        cursor.execute("INSERT INTO tables (restaurant_id, table_number, token, qr_code_path, capacity, location) VALUES (?, '1', 'f8519936d21746f2845c227e362b74c3', 'qr_f8519936d21746f2845c227e362b74c3.png', 4, 'الصالة الرئيسية')", (restaurant_id,))
        cursor.execute("INSERT INTO tables (restaurant_id, table_number, token, qr_code_path, capacity, location) VALUES (?, '2', '0572a4df409848009ae3886cdfee6a6b', 'qr_0572a4df409848009ae3886cdfee6a6b.png', 4, 'الصالة الرئيسية')", (restaurant_id,))
        cursor.execute("INSERT INTO tables (restaurant_id, table_number, token, qr_code_path, capacity, location) VALUES (?, '3', 'ff457df6c73a436b9482ba5279ca8b8c', 'qr_ff457df6c73a436b9482ba5279ca8b8c.png', 4, 'الصالة الرئيسية')", (restaurant_id,))
        cursor.execute("INSERT INTO tables (restaurant_id, table_number, token, qr_code_path, capacity, location) VALUES (?, 'سفري', 'takeaway_b7ba0b67', NULL, 0, 'سفري')", (restaurant_id,))
        
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
        restaurant_id = cursor.lastrowid
        
        # Auto-create a "سفري" (takeaway) table for this restaurant
        import uuid as _uuid
        takeaway_token = f"takeaway_{_uuid.uuid4().hex[:8]}"
        cursor.execute("INSERT INTO tables (restaurant_id, table_number, token, qr_code_path, capacity, location) VALUES (?, 'سفري', ?, NULL, 0, 'سفري')",
                       (restaurant_id, takeaway_token))
        
        conn.commit()
        return restaurant_id
    except sqlite3.IntegrityError:
        conn.rollback()
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
def add_table(restaurant_id, table_number, token, qr_code_path=None, capacity=4, location='الصالة الرئيسية'):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tables (restaurant_id, table_number, token, qr_code_path, capacity, location) VALUES (?, ?, ?, ?, ?, ?)",
                   (restaurant_id, table_number, token, qr_code_path, capacity, location))
    conn.commit()
    table_id = cursor.lastrowid
    conn.close()
    return table_id

def get_tables(restaurant_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tables WHERE restaurant_id = ? AND table_number != 'سفري' ORDER BY CAST(table_number AS INTEGER), table_number", (restaurant_id,))
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

def create_order(restaurant_id, table_id, total_price, items, session_id=None, order_type='dine_in', notes=None):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO orders (restaurant_id, table_id, total_price, session_id, order_type, notes) VALUES (?, ?, ?, ?, ?, ?)",
                       (restaurant_id, table_id, total_price, session_id, order_type, notes))
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

def start_table_session(table_id, session_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tables SET status = 'occupied', current_session_id = ? WHERE id = ?", (session_id, table_id))
    conn.commit()
    conn.close()

def set_table_status(table_id, status):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tables SET status = ? WHERE id = ?", (status, table_id))
    conn.commit()
    conn.close()

def get_table_invoice(table_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.name as item_name, SUM(oi.quantity) as quantity, oi.price, SUM(oi.quantity * oi.price) as item_total
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.id
        JOIN menu_items m ON oi.menu_item_id = m.id
        WHERE o.table_id = ? 
          AND o.session_id = (SELECT current_session_id FROM tables WHERE id = ?)
          AND o.status != 'cancelled'
        GROUP BY oi.menu_item_id, oi.price
    """, (table_id, table_id))
    items = cursor.fetchall()
    conn.close()
    return items

def checkout_table(table_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Get current session id
        cursor.execute("SELECT current_session_id, restaurant_id, table_number FROM tables WHERE id = ?", (table_id,))
        row = cursor.fetchone()
        if row and row['current_session_id']:
            session_id = row['current_session_id']
            restaurant_id = row['restaurant_id']
            table_number = row['table_number']
            
            # Fetch invoice items to archive
            cursor.execute("""
                SELECT m.name as item_name, SUM(oi.quantity) as quantity, oi.price, SUM(oi.quantity * oi.price) as item_total
                FROM orders o
                JOIN order_items oi ON oi.order_id = o.id
                JOIN menu_items m ON oi.menu_item_id = m.id
                WHERE o.table_id = ? 
                  AND o.session_id = ?
                  AND o.status != 'cancelled'
                GROUP BY oi.menu_item_id, oi.price
            """, (table_id, session_id))
            items_rows = cursor.fetchall()
            
            if items_rows:
                # Calculate subtotal
                subtotal = sum(item['item_total'] for item in items_rows)
                
                # Fetch VAT settings
                cursor.execute("SELECT vat_enabled, vat_percentage, currency FROM restaurants WHERE id = ?", (restaurant_id,))
                rest = cursor.fetchone()
                vat_enabled = rest['vat_enabled'] if rest else 1
                vat_percentage = rest['vat_percentage'] if rest else 15.0
                currency = rest['currency'] if rest else 'IQD'
                
                vat_amount = subtotal * (vat_percentage / 100.0) if vat_enabled == 1 else 0.0
                total_amount = subtotal + vat_amount
                
                # Create items list JSON
                items_list = []
                for item in items_rows:
                    items_list.append({
                        'name': item['item_name'],
                        'quantity': item['quantity'],
                        'price': item['price'],
                        'total': item['item_total']
                    })
                import json
                items_json = json.dumps(items_list, ensure_ascii=False)
                
                # Insert into invoices table
                cursor.execute("""
                    INSERT INTO invoices (restaurant_id, table_id, table_number, session_id, subtotal, vat_rate, vat_amount, total_amount, currency, items_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (restaurant_id, table_id, table_number, session_id, subtotal, vat_percentage if vat_enabled else 0.0, vat_amount, total_amount, currency, items_json))
                
            # 1. Update all orders of this session to 'paid'
            cursor.execute("UPDATE orders SET status = 'paid' WHERE table_id = ? AND session_id = ?", (table_id, session_id))
            # 2. Resolve waiter calls for this table
            cursor.execute("UPDATE waiter_calls SET status = 'resolved' WHERE table_id = ? AND status = 'active'", (table_id,))
        
        # 3. Reset table status to 'available' and clear session
        cursor.execute("UPDATE tables SET status = 'available', current_session_id = NULL WHERE id = ?", (table_id,))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def archive_takeaway_order(order_id):
    """Archive a single takeaway order as an invoice (since there's no table checkout for سفري)."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Get order details
        cursor.execute("""
            SELECT o.*, t.table_number, t.id as table_id 
            FROM orders o 
            JOIN tables t ON o.table_id = t.id 
            WHERE o.id = ?
        """, (order_id,))
        order = cursor.fetchone()
        
        if not order:
            return False
        
        # Fetch items for this order
        cursor.execute("""
            SELECT m.name as item_name, oi.quantity, oi.price, (oi.quantity * oi.price) as item_total
            FROM order_items oi
            JOIN menu_items m ON oi.menu_item_id = m.id
            WHERE oi.order_id = ?
        """, (order_id,))
        items_rows = cursor.fetchall()
        
        if items_rows:
            subtotal = sum(item['item_total'] for item in items_rows)
            
            # Fetch VAT settings
            cursor.execute("SELECT vat_enabled, vat_percentage, currency FROM restaurants WHERE id = ?", (order['restaurant_id'],))
            rest = cursor.fetchone()
            vat_enabled = rest['vat_enabled'] if rest else 1
            vat_percentage = rest['vat_percentage'] if rest else 15.0
            currency = rest['currency'] if rest else 'IQD'
            
            vat_amount = subtotal * (vat_percentage / 100.0) if vat_enabled == 1 else 0.0
            total_amount = subtotal + vat_amount
            
            items_list = []
            for item in items_rows:
                items_list.append({
                    'name': item['item_name'],
                    'quantity': item['quantity'],
                    'price': item['price'],
                    'total': item['item_total']
                })
            import json
            items_json = json.dumps(items_list, ensure_ascii=False)
            
            cursor.execute("""
                INSERT INTO invoices (restaurant_id, table_id, table_number, session_id, subtotal, vat_rate, vat_amount, total_amount, currency, items_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (order['restaurant_id'], order['table_id'], order['table_number'], 
                  order['session_id'] or '', subtotal, vat_percentage if vat_enabled else 0.0, 
                  vat_amount, total_amount, currency, items_json))
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_sales_analytics(restaurant_id):
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Daily Sales
    cursor.execute("""
        SELECT COALESCE(SUM(total_price), 0) FROM orders 
        WHERE restaurant_id = ? AND (status = 'paid' OR status = 'completed') 
          AND date(created_at, 'localtime') = date('now', 'localtime')
    """, (restaurant_id,))
    daily_sales = cursor.fetchone()[0]
    
    # 2. Monthly Sales
    cursor.execute("""
        SELECT COALESCE(SUM(total_price), 0) FROM orders 
        WHERE restaurant_id = ? AND (status = 'paid' OR status = 'completed') 
          AND strftime('%Y-%m', created_at, 'localtime') = strftime('%Y-%m', 'now', 'localtime')
    """, (restaurant_id,))
    monthly_sales = cursor.fetchone()[0]
    
    # 3. Weekly Sales (last 7 days)
    cursor.execute("""
        SELECT COALESCE(SUM(total_price), 0) FROM orders 
        WHERE restaurant_id = ? AND (status = 'paid' OR status = 'completed') 
          AND created_at >= date('now', '-7 days', 'localtime')
    """, (restaurant_id,))
    weekly_sales = cursor.fetchone()[0]
    
    # 4. Table Stats count
    cursor.execute("SELECT status, COUNT(*) as count FROM tables WHERE restaurant_id = ? AND table_number != 'سفري' GROUP BY status", (restaurant_id,))
    table_stats_rows = cursor.fetchall()
    table_stats = {'available': 0, 'occupied': 0, 'reserved': 0, 'billing': 0}
    for row in table_stats_rows:
        table_stats[row['status']] = row['count']
        
    # Total Tables Count
    cursor.execute("SELECT COUNT(*) FROM tables WHERE restaurant_id = ? AND table_number != 'سفري'", (restaurant_id,))
    total_tables = cursor.fetchone()[0]
    
    # Active Orders Count (pending, preparing, served, billing)
    cursor.execute("""
        SELECT COUNT(*) FROM orders 
        WHERE restaurant_id = ? AND status IN ('pending', 'preparing', 'served', 'billing')
    """, (restaurant_id,))
    active_orders_count = cursor.fetchone()[0]
    
    # 5. Sales by Category
    cursor.execute("""
        SELECT c.name as category_name, SUM(oi.quantity * oi.price) as total_sales
        FROM order_items oi
        JOIN menu_items m ON oi.menu_item_id = m.id
        JOIN categories c ON m.category_id = c.id
        JOIN orders o ON oi.order_id = o.id
        WHERE o.restaurant_id = ? AND (o.status = 'paid' OR o.status = 'completed')
        GROUP BY c.id
    """, (restaurant_id,))
    category_sales = [dict(row) for row in cursor.fetchall()]
    
    # 6. Top 5 Items
    cursor.execute("""
        SELECT m.name as item_name, SUM(oi.quantity) as total_quantity
        FROM order_items oi
        JOIN menu_items m ON oi.menu_item_id = m.id
        JOIN orders o ON oi.order_id = o.id
        WHERE o.restaurant_id = ? AND (o.status = 'paid' OR o.status = 'completed')
        GROUP BY m.id
        ORDER BY total_quantity DESC
        LIMIT 5
    """, (restaurant_id,))
    top_items = [dict(row) for row in cursor.fetchall()]
    
    # 7. Last 30 Days Sales trend
    cursor.execute("""
        SELECT date(created_at, 'localtime') as sale_date, SUM(total_price) as total_sales
        FROM orders
        WHERE restaurant_id = ? AND (status = 'paid' OR status = 'completed')
          AND created_at >= date('now', '-30 days', 'localtime')
        GROUP BY sale_date
        ORDER BY sale_date ASC
    """, (restaurant_id,))
    sales_trend = [dict(row) for row in cursor.fetchall()]
    
    # 8. Archived Invoices (last 50 for history)
    cursor.execute("""
        SELECT * FROM invoices 
        WHERE restaurant_id = ? 
        ORDER BY created_at DESC 
        LIMIT 50
    """, (restaurant_id,))
    archived_invoices = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return {
        'daily_sales': daily_sales,
        'monthly_sales': monthly_sales,
        'weekly_sales': weekly_sales,
        'table_stats': table_stats,
        'total_tables': total_tables,
        'active_orders_count': active_orders_count,
        'category_sales': category_sales,
        'top_items': top_items,
        'sales_trend': sales_trend,
        'archived_invoices': archived_invoices
    }

def get_invoice_by_id(invoice_id):
    """Retrieve a single archived invoice by its ID."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_restaurant_settings(restaurant_id, name, theme_name, primary_color, bg_color, surface_color, text_color, currency, vat_enabled=1, vat_percentage=15.0, logo=None, phone='', address='', announcement='', menu_bg_image=None):
    conn = get_db()
    cursor = conn.cursor()
    if logo:
        cursor.execute("""
            UPDATE restaurants 
            SET name = ?, theme_name = ?, theme_primary_color = ?, theme_bg_color = ?, theme_surface_color = ?, theme_text_color = ?, currency = ?, vat_enabled = ?, vat_percentage = ?, logo = ?, phone = ?, address = ?, announcement = ?
            WHERE id = ?
        """, (name, theme_name, primary_color, bg_color, surface_color, text_color, currency, vat_enabled, vat_percentage, logo, phone, address, announcement, restaurant_id))
    else:
        cursor.execute("""
            UPDATE restaurants 
            SET name = ?, theme_name = ?, theme_primary_color = ?, theme_bg_color = ?, theme_surface_color = ?, theme_text_color = ?, currency = ?, vat_enabled = ?, vat_percentage = ?, phone = ?, address = ?, announcement = ?
            WHERE id = ?
        """, (name, theme_name, primary_color, bg_color, surface_color, text_color, currency, vat_enabled, vat_percentage, phone, address, announcement, restaurant_id))
    
    if menu_bg_image is not None:
        cursor.execute("UPDATE restaurants SET menu_bg_image = ? WHERE id = ?", (menu_bg_image, restaurant_id))
    
    conn.commit()
    conn.close()

def verify_restaurant_password(restaurant_id, password):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT u.password FROM users u JOIN restaurants r ON r.user_id = u.id WHERE r.id = ?", (restaurant_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return check_password_hash(row['password'], password)
    return False
