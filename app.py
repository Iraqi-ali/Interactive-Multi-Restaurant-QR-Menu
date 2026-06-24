import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
import qrcode
import database as db

app = Flask(__name__)
app.secret_key = "antigravity_secret_key_12345!"

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
QRCODES_FOLDER = os.path.join(app.root_path, 'static', 'qrcodes')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['QRCODES_FOLDER'] = QRCODES_FOLDER

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(QRCODES_FOLDER, exist_ok=True)

# Helper to check allowed files
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Init Database on start
with app.app_context():
    db.init_db()

# --- MAIN VIEWS ---

@app.route('/')
def index():
    if session.get('user_id'):
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('restaurant_dashboard'))
        
    # Fetch all active restaurants for the public directory
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM restaurants WHERE status = 'active'")
    active_restaurants = cursor.fetchall()
    conn.close()
    
    return render_template('index.html', restaurants=active_restaurants)

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username').strip()
    password = request.form.get('password')
    
    # Check user (by username or restaurant slug)
    print(f"DEBUG LOGIN: Submitted username={repr(username)}, password={repr(password)}")
    user = db.check_user(username, password)
    print(f"DEBUG LOGIN: check_user returned={repr(user)}")
                
    if user:
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        
        if user['role'] == 'admin':
            flash("مرحباً بك في لوحة الإدارة العامة.", "success")
            return redirect(url_for('admin_dashboard'))
        else:
            restaurant = db.get_restaurant_by_user(user['id'])
            if restaurant:
                if restaurant['status'] != 'active':
                    session.clear()
                    flash("عذراً، هذا الحساب معطل حالياً من قبل الإدارة العامة.", "error")
                    return redirect(url_for('index'))
                
                session['restaurant_id'] = restaurant['id']
                session['restaurant_name'] = restaurant['name']
                session['restaurant_slug'] = restaurant['slug']
                flash(f"مرحباً بك مجدداً في لوحة تحكم {restaurant['name']}.", "success")
                return redirect(url_for('restaurant_dashboard'))
            else:
                session.clear()
                flash("خطأ: لم يتم العثور على مطعم مرتبط بهذا المستخدم.", "error")
                return redirect(url_for('index'))
    else:
        flash("اسم المستخدم أو كلمة المرور غير صحيحة.", "error")
        return redirect(url_for('index', _anchor='login'))

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    password = request.form.get('password')
    name = request.form.get('name')
    slug = request.form.get('slug').lower().strip()
    
    # Validation
    if not username or not password or not name or not slug:
        flash("جميع الحقول مطلوبة لتسجيل الحساب.", "error")
        return redirect(url_for('index', _anchor='register'))
        
    # Check if slug exists
    if db.get_restaurant_by_slug(slug):
        flash("رابط المطعم (Slug) مستخدم بالفعل، يرجى اختيار رابط آخر.", "error")
        return redirect(url_for('index', _anchor='register'))
        
    # Handle Logo Upload
    logo_filename = None
    logo_file = request.files.get('logo')
    if logo_file and logo_file.filename != '':
        if allowed_file(logo_file.filename):
            ext = logo_file.filename.rsplit('.', 1)[1].lower()
            logo_filename = f"logo_{slug}_{uuid.uuid4().hex[:6]}.{ext}"
            logo_file.save(os.path.join(app.config['UPLOAD_FOLDER'], logo_filename))
        else:
            flash("نوع الملف غير مسموح به للشعار. يرجى استخدام صور فقط.", "error")
            return redirect(url_for('index', _anchor='register'))
            
    # Add User
    user_id = db.add_user(username, password, role='restaurant')
    if not user_id:
        flash("اسم المستخدم هذا مسجل بالفعل. يرجى استخدام اسم مستخدم آخر.", "error")
        # delete logo if uploaded
        if logo_filename:
            try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], logo_filename))
            except: pass
        return redirect(url_for('index', _anchor='register'))
        
    # Add Restaurant
    restaurant_id = db.create_restaurant(user_id, name, slug, logo_filename)
    if not restaurant_id:
        flash("حدث خطأ أثناء إنشاء المطعم. يرجى المحاولة لاحقاً.", "error")
        return redirect(url_for('index', _anchor='register'))
        
    # Log in user
    session['user_id'] = user_id
    session['username'] = username
    session['role'] = 'restaurant'
    session['restaurant_id'] = restaurant_id
    session['restaurant_name'] = name
    session['restaurant_slug'] = slug
    
    flash("تم تسجيل حسابك ومطعمك بنجاح! مرحباً بك.", "success")
    return redirect(url_for('restaurant_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash("تم تسجيل الخروج بنجاح.", "success")
    return redirect(url_for('index'))

# --- SUPER ADMIN VIEWS ---

@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        flash("غير مصرح لك بدخول هذه الصفحة.", "error")
        return redirect(url_for('index'))
        
    restaurants = db.get_all_restaurants()
    return render_template('admin.html', restaurants=restaurants)

@app.route('/admin/toggle-status/<int:restaurant_id>', methods=['POST'])
def admin_toggle_status(restaurant_id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    # Find restaurant
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM restaurants WHERE id = ?", (restaurant_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        new_status = 'inactive' if row['status'] == 'active' else 'active'
        db.update_restaurant_status(restaurant_id, new_status)
        flash("تم تغيير حالة المطعم بنجاح.", "success")
    else:
        flash("لم يتم العثور على المطعم.", "error")
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-restaurant/<int:restaurant_id>', methods=['POST'])
def admin_delete_restaurant(restaurant_id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    db.delete_restaurant(restaurant_id)
    flash("تم حذف المطعم وجميع البيانات التابعة له بنجاح.", "success")
    return redirect(url_for('admin_dashboard'))

# --- RESTAURANT OWNER VIEWS (DASHBOARD) ---

@app.route('/dashboard')
def restaurant_dashboard():
    if not session.get('user_id') or session.get('role') != 'restaurant':
        flash("يرجى تسجيل الدخول أولاً.", "error")
        return redirect(url_for('index', _anchor='login'))
        
    restaurant_id = session.get('restaurant_id')
    restaurant = db.get_restaurant_by_user(session['user_id'])
    
    if not restaurant or restaurant['status'] != 'active':
        session.clear()
        flash("حسابك معطل أو غير موجود.", "error")
        return redirect(url_for('index'))
        
    categories = db.get_categories(restaurant_id)
    menu_items = db.get_menu_items(restaurant_id)
    tables = db.get_tables(restaurant_id)
    
    return render_template('dashboard.html', restaurant=restaurant, categories=categories, menu_items=menu_items, tables=tables)

@app.route('/dashboard/update-settings', methods=['POST'])
def update_settings():
    if not session.get('restaurant_id'):
        return redirect(url_for('index'))
        
    restaurant_id = session['restaurant_id']
    name = request.form.get('name').strip()
    theme_name = request.form.get('theme_name')
    theme_primary_color = request.form.get('theme_primary_color')
    theme_bg_color = request.form.get('theme_bg_color')
    theme_surface_color = request.form.get('theme_surface_color')
    theme_text_color = request.form.get('theme_text_color')
    
    # Handle Logo Upload
    logo_filename = None
    logo_file = request.files.get('logo')
    if logo_file and logo_file.filename != '':
        if allowed_file(logo_file.filename):
            # Try to delete the old logo if it exists
            conn = db.get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT logo FROM restaurants WHERE id = ?", (restaurant_id,))
            row = cursor.fetchone()
            if row and row['logo']:
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], row['logo']))
                except:
                    pass
            conn.close()
            
            ext = logo_file.filename.rsplit('.', 1)[1].lower()
            logo_filename = f"logo_{session['restaurant_slug']}_{uuid.uuid4().hex[:6]}.{ext}"
            logo_file.save(os.path.join(app.config['UPLOAD_FOLDER'], logo_filename))
        else:
            flash("نوع ملف الشعار غير مدعوم.", "error")
            return redirect(url_for('restaurant_dashboard'))
            
    if name:
        db.update_restaurant_settings(
            restaurant_id, 
            name, 
            theme_name, 
            theme_primary_color, 
            theme_bg_color, 
            theme_surface_color, 
            theme_text_color, 
            logo_filename
        )
        session['restaurant_name'] = name
        flash("تم حفظ إعدادات المظهر والبيانات بنجاح.", "success")
    else:
        flash("اسم المطعم لا يمكن أن يكون فارغاً.", "error")
        
    return redirect(url_for('restaurant_dashboard'))

@app.route('/dashboard/add-category', methods=['POST'])
def add_category():
    if not session.get('restaurant_id'):
        return redirect(url_for('index'))
    name = request.form.get('name')
    if name:
        db.add_category(session['restaurant_id'], name)
        flash("تم إضافة القسم الجديد بنجاح.", "success")
    return redirect(url_for('restaurant_dashboard'))

@app.route('/dashboard/delete-category/<int:category_id>', methods=['POST'])
def delete_category(category_id):
    if not session.get('restaurant_id'):
        return redirect(url_for('index'))
    db.delete_category(category_id)
    flash("تم حذف القسم بنجاح.", "success")
    return redirect(url_for('restaurant_dashboard'))

@app.route('/dashboard/add-item', methods=['POST'])
def add_item():
    if not session.get('restaurant_id'):
        return redirect(url_for('index'))
        
    name = request.form.get('name')
    category_id = request.form.get('category_id')
    price = request.form.get('price')
    description = request.form.get('description')
    
    # Handle Image Upload
    image_filename = None
    image_file = request.files.get('image')
    if image_file and image_file.filename != '':
        if allowed_file(image_file.filename):
            ext = image_file.filename.rsplit('.', 1)[1].lower()
            image_filename = f"item_{uuid.uuid4().hex[:8]}.{ext}"
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
        else:
            flash("نوع الملف غير مسموح به لصورة الوجبة.", "error")
            return redirect(url_for('restaurant_dashboard'))
            
    if name and category_id and price:
        db.add_menu_item(category_id, name, description, float(price), image_filename)
        flash("تم إضافة الوجبة للمنيو بنجاح.", "success")
    return redirect(url_for('restaurant_dashboard'))

@app.route('/dashboard/edit-item/<int:item_id>', methods=['POST'])
def edit_item(item_id):
    if not session.get('restaurant_id'):
        return redirect(url_for('index'))
        
    name = request.form.get('name')
    price = request.form.get('price')
    description = request.form.get('description')
    available = int(request.form.get('available', 1))
    
    # Check optional image
    image_filename = None
    image_file = request.files.get('image')
    if image_file and image_file.filename != '':
        if allowed_file(image_file.filename):
            ext = image_file.filename.rsplit('.', 1)[1].lower()
            image_filename = f"item_{uuid.uuid4().hex[:8]}.{ext}"
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
            
    if name and price:
        db.update_menu_item(item_id, name, description, float(price), image_filename, available)
        flash("تم تعديل الوجبة بنجاح.", "success")
    return redirect(url_for('restaurant_dashboard'))

@app.route('/dashboard/delete-item/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    if not session.get('restaurant_id'):
        return redirect(url_for('index'))
    db.delete_menu_item(item_id)
    flash("تم حذف الوجبة بنجاح.", "success")
    return redirect(url_for('restaurant_dashboard'))

@app.route('/dashboard/add-table', methods=['POST'])
def add_table():
    if not session.get('restaurant_id'):
        return redirect(url_for('index'))
        
    table_number = request.form.get('table_number')
    if table_number:
        token = uuid.uuid4().hex
        slug = session['restaurant_slug']
        
        # Generate QR Code
        # We point it to the dynamic customer table URL
        qr_url = f"{request.host_url}r/{slug}/table/{token}"
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_filename = f"qr_{token}.png"
        qr_img.save(os.path.join(app.config['QRCODES_FOLDER'], qr_filename))
        
        db.add_table(session['restaurant_id'], table_number, token, qr_filename)
        flash(f"تم إضافة طاولة رقم {table_number} وتوليد الباركود الخاص بها.", "success")
        
    return redirect(url_for('restaurant_dashboard'))

@app.route('/dashboard/delete-table/<int:table_id>', methods=['POST'])
def delete_table(table_id):
    if not session.get('restaurant_id'):
        return redirect(url_for('index'))
        
    # Get table info to delete file
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT qr_code_path FROM tables WHERE id = ?", (table_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row and row['qr_code_path']:
        try:
            os.remove(os.path.join(app.config['QRCODES_FOLDER'], row['qr_code_path']))
        except:
            pass
            
    db.delete_table(table_id)
    flash("تم حذف الطاولة بنجاح.", "success")
    return redirect(url_for('restaurant_dashboard'))

# --- CUSTOMER PUBLIC VIEWS ---

@app.route('/r/<slug>')
def public_menu(slug):
    restaurant = db.get_restaurant_by_slug(slug)
    if not restaurant or restaurant['status'] != 'active':
        return "المطعم غير موجود أو معطل حالياً.", 404
        
    categories = db.get_categories(restaurant['id'])
    menu_items = db.get_menu_items(restaurant['id'])
    
    # We display a read-only menu layout since no table is selected
    # Mock table to pass layout check but notify user they can only browse
    mock_table = {'id': 0, 'table_number': 'تصفح فقط'}
    return render_template('menu.html', restaurant=restaurant, categories=categories, menu_items=menu_items, table=mock_table)

@app.route('/r/<slug>/table/<token>')
def public_menu_table(slug, token):
    restaurant = db.get_restaurant_by_slug(slug)
    if not restaurant or restaurant['status'] != 'active':
        return "المطعم غير موجود أو معطل حالياً.", 404
        
    table = db.get_table_by_token(token)
    if not table or table['restaurant_id'] != restaurant['id']:
        return "رمز طاولة غير صالح أو غير تابع لهذا المطعم.", 404
        
    categories = db.get_categories(restaurant['id'])
    menu_items = db.get_menu_items(restaurant['id'])
    
    return render_template('menu.html', restaurant=restaurant, categories=categories, menu_items=menu_items, table=table)

# --- BACKEND API ENDPOINTS ---

@app.route('/api/restaurant/orders')
def api_get_orders():
    if not session.get('restaurant_id'):
        return jsonify({'error': 'Unauthorized'}), 401
        
    orders = db.get_orders(session['restaurant_id'])
    orders_list = []
    
    for o in orders:
        details = db.get_order_details(o['id'])
        items_list = []
        for item in details['items']:
            items_list.append({
                'item_name': item['item_name'],
                'quantity': item['quantity'],
                'price': item['price']
            })
            
        orders_list.append({
            'id': o['id'],
            'table_number': o['table_number'],
            'total_price': o['total_price'],
            'status': o['status'],
            'created_at': o['created_at'],
            'items': items_list
        })
        
    return jsonify(orders_list)

@app.route('/api/restaurant/waiter-calls')
def api_get_waiter_calls():
    if not session.get('restaurant_id'):
        return jsonify({'error': 'Unauthorized'}), 401
        
    calls = db.get_waiter_calls(session['restaurant_id'])
    calls_list = []
    for c in calls:
        calls_list.append({
            'id': c['id'],
            'table_number': c['table_number'],
            'type': c['type'],
            'status': c['status'],
            'created_at': c['created_at']
        })
    return jsonify(calls_list)

@app.route('/api/order/create', methods=['POST'])
def api_create_order():
    data = request.json
    restaurant_id = data.get('restaurant_id')
    table_id = data.get('table_id')
    token = data.get('token')
    items = data.get('items') # list of {menu_item_id, quantity, price}
    
    if not restaurant_id or not table_id or not token or not items:
        return jsonify({'error': 'Missing fields'}), 400
        
    # Verify table token
    table = db.get_table_by_token(token)
    if not table or table['id'] != int(table_id) or table['restaurant_id'] != int(restaurant_id):
        return jsonify({'error': 'Invalid table token'}), 403
        
    # Calculate total price
    total_price = sum(item['price'] * item['quantity'] for item in items)
    
    # 1. Manage Table Session & Turnover
    session_id = table['current_session_id']
    if not session_id or table['status'] == 'available':
        # Start a brand new session
        session_id = uuid.uuid4().hex
        db.start_table_session(table_id, session_id)
    elif table['status'] == 'billing':
        # If table was billing but client ordered more, set status back to occupied
        db.set_table_status(table_id, 'occupied')
        
    try:
        order_id = db.create_order(restaurant_id, table_id, total_price, items, session_id)
        return jsonify({'success': True, 'order_id': order_id, 'session_id': session_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/order/status/<int:order_id>')
def api_order_status(order_id):
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return jsonify({'status': row['status']})
    return jsonify({'error': 'Order not found'}), 404

@app.route('/api/order/update-status/<int:order_id>', methods=['POST'])
def api_update_order_status(order_id):
    if not session.get('restaurant_id'):
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.json
    status = data.get('status')
    if status in ['pending', 'preparing', 'served', 'completed', 'paid', 'cancelled']:
        db.update_order_status(order_id, status)
        return jsonify({'success': True})
    return jsonify({'error': 'Invalid status'}), 400

@app.route('/api/waiter-call/create', methods=['POST'])
def api_create_waiter_call():
    data = request.json
    restaurant_id = data.get('restaurant_id')
    table_id = data.get('table_id')
    token = data.get('token')
    call_type = data.get('type') # 'waiter' or 'bill'
    
    if not restaurant_id or not table_id or not token or not call_type:
        return jsonify({'error': 'Missing fields'}), 400
        
    # Verify table token
    table = db.get_table_by_token(token)
    if not table or table['id'] != int(table_id) or table['restaurant_id'] != int(restaurant_id):
        return jsonify({'error': 'Invalid table token'}), 403
        
    if call_type not in ['waiter', 'bill']:
        return jsonify({'error': 'Invalid call type'}), 400
        
    # If customer calls for the bill, update table status to 'billing'
    if call_type == 'bill':
        db.set_table_status(table_id, 'billing')
        
    call_id = db.create_waiter_call(restaurant_id, table_id, call_type)
    return jsonify({'success': True, 'call_id': call_id})

@app.route('/api/waiter-call/resolve/<int:call_id>', methods=['POST'])
def api_resolve_waiter_call(call_id):
    if not session.get('restaurant_id'):
        return jsonify({'error': 'Unauthorized'}), 401
        
    db.resolve_waiter_call(call_id)
    return jsonify({'success': True})

# --- INVOICING, BILLING & ANALYTICS APIs ---

@app.route('/api/restaurant/table/invoice/<int:table_id>')
def api_get_table_invoice(table_id):
    token = request.args.get('token')
    authorized = False
    
    if session.get('restaurant_id'):
        # Check if table belongs to this restaurant
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT restaurant_id FROM tables WHERE id = ?", (table_id,))
        row = cursor.fetchone()
        conn.close()
        if row and row['restaurant_id'] == session['restaurant_id']:
            authorized = True
    elif token:
        # Check if token matches this table
        table = db.get_table_by_token(token)
        if table and table['id'] == table_id:
            authorized = True
            
    if not authorized:
        return jsonify({'error': 'Unauthorized'}), 401
        
    items = db.get_table_invoice(table_id)
    invoice_items = []
    subtotal = 0
    
    for row in items:
        invoice_items.append({
            'name': row['item_name'],
            'quantity': row['quantity'],
            'price': row['price'],
            'total': row['item_total']
        })
        subtotal += row['item_total']
        
    vat = subtotal * 0.15 # 15% VAT
    grand_total = subtotal + vat
    
    return jsonify({
        'items': invoice_items,
        'subtotal': subtotal,
        'vat': vat,
        'grand_total': grand_total
    })

@app.route('/api/restaurant/table/checkout/<int:table_id>', methods=['POST'])
def api_checkout_table(table_id):
    if not session.get('restaurant_id'):
        return jsonify({'error': 'Unauthorized'}), 401
        
    success = db.checkout_table(table_id)
    return jsonify({'success': success})

@app.route('/api/restaurant/analytics')
def api_get_analytics():
    if not session.get('restaurant_id'):
        return jsonify({'error': 'Unauthorized'}), 401
        
    analytics = db.get_sales_analytics(session['restaurant_id'])
    return jsonify(analytics)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
