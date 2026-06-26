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
    currency = request.form.get('currency', 'IQD')
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()
    announcement = request.form.get('announcement', '').strip()
    
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
    
    # Handle Menu Background Image Upload
    menu_bg_filename = None
    menu_bg_file = request.files.get('menu_bg_image')
    if menu_bg_file and menu_bg_file.filename != '':
        if allowed_file(menu_bg_file.filename):
            # Delete old background if exists
            conn = db.get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT menu_bg_image FROM restaurants WHERE id = ?", (restaurant_id,))
            row = cursor.fetchone()
            if row and row['menu_bg_image']:
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], row['menu_bg_image']))
                except:
                    pass
            conn.close()
            
            ext = menu_bg_file.filename.rsplit('.', 1)[1].lower()
            menu_bg_filename = f"bg_{session['restaurant_slug']}_{uuid.uuid4().hex[:6]}.{ext}"
            menu_bg_file.save(os.path.join(app.config['UPLOAD_FOLDER'], menu_bg_filename))
        else:
            flash("نوع ملف الخلفية غير مدعوم.", "error")
            return redirect(url_for('restaurant_dashboard'))
    
    # Handle Menu Background Image Removal
    if request.form.get('remove_menu_bg') == '1':
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT menu_bg_image FROM restaurants WHERE id = ?", (restaurant_id,))
        row = cursor.fetchone()
        if row and row['menu_bg_image']:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], row['menu_bg_image']))
            except:
                pass
        conn.close()
        menu_bg_filename = ''  # Set to empty string to clear it
            
    vat_enabled = 1 if request.form.get('vat_enabled') == 'on' else 0
    vat_percentage_str = request.form.get('vat_percentage', '15.0')
    try:
        vat_percentage = float(vat_percentage_str)
    except ValueError:
        vat_percentage = 0.0

    if name:
        db.update_restaurant_settings(
            restaurant_id, 
            name, 
            theme_name, 
            theme_primary_color, 
            theme_bg_color, 
            theme_surface_color, 
            theme_text_color, 
            currency,
            vat_enabled,
            vat_percentage,
            logo_filename,
            phone,
            address,
            announcement,
            menu_bg_filename
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
    capacity = int(request.form.get('capacity', 4))
    location = request.form.get('location', 'الصالة الرئيسية').strip()
    
    if table_number:
        token = uuid.uuid4().hex
        slug = session['restaurant_slug']
        
        # Generate QR Code
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
        
        db.add_table(session['restaurant_id'], table_number, token, qr_filename, capacity, location)
        flash(f"تم إضافة طاولة رقم {table_number} وتوليد الباركود الخاص بها.", "success")
        
    return redirect(url_for('restaurant_dashboard'))

@app.route('/dashboard/table/update-status/<int:table_id>', methods=['POST'])
def update_table_status(table_id):
    if not session.get('restaurant_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    status = data.get('status')
    if status in ['available', 'occupied', 'reserved', 'billing']:
        db.update_table_status(table_id, status)
        return jsonify({'success': True})
    return jsonify({'error': 'Invalid status'}), 400

@app.route('/dashboard/delete-table/<int:table_id>', methods=['POST'])
def delete_table(table_id):
    if not session.get('restaurant_id'):
        return redirect(url_for('index'))
        
    # Prevent deletion of the special سفري (takeaway) table
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT table_number, qr_code_path FROM tables WHERE id = ? AND restaurant_id = ?", (table_id, session['restaurant_id']))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        flash("الطاولة غير موجودة.", "error")
        return redirect(url_for('restaurant_dashboard'))
    
    if row['table_number'] == 'سفري':
        flash("لا يمكن حذف طاولة السفري (الطلبات الخارجية). هذه الطاولة ضرورية لعمل النظام.", "error")
        return redirect(url_for('restaurant_dashboard'))
    
    if row['qr_code_path']:
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
                'id': item['id'],
                'item_name': item['item_name'],
                'quantity': item['quantity'],
                'price': item['price']
            })
            
        orders_list.append({
            'id': o['id'],
            'table_number': o['table_number'],
            'total_price': o['total_price'],
            'status': o['status'],
            'order_type': o['order_type'],
            'notes': o['notes'],
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
    order_type = data.get('order_type', 'dine_in')
    
    if not restaurant_id or not items:
        return jsonify({'error': 'Missing fields'}), 400
        
    session_id = None
    
    if order_type == 'take_away':
        # Find or create a mock 'سفري' table for this restaurant
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tables WHERE restaurant_id = ? AND table_number = 'سفري'", (restaurant_id,))
        row = cursor.fetchone()
        if row:
            table_id = row['id']
        else:
            mock_token = f"takeaway_{uuid.uuid4().hex[:8]}"
            table_id = db.add_table(restaurant_id, 'سفري', mock_token, qr_code_path=None, capacity=0, location='سفري')
        conn.close()
        session_id = f"takeaway_{uuid.uuid4().hex[:8]}"
    else:
        if not table_id or not token:
            return jsonify({'error': 'Missing fields for dine-in'}), 400
        # Verify table token
        table = db.get_table_by_token(token)
        if not table or table['id'] != int(table_id) or table['restaurant_id'] != int(restaurant_id):
            return jsonify({'error': 'Invalid table token'}), 403
            
        session_id = table['current_session_id']
        if not session_id or table['status'] == 'available':
            session_id = uuid.uuid4().hex
            db.start_table_session(table_id, session_id)
        elif table['status'] == 'billing':
            db.set_table_status(table_id, 'occupied')
            
    # Calculate total price
    total_price = sum(item['price'] * item['quantity'] for item in items)
    notes = data.get('notes')
    
    try:
        order_id = db.create_order(restaurant_id, table_id, total_price, items, session_id, order_type, notes)
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
    password = data.get('password')
    
    if status == 'paid':
        # Check if this is a takeaway order - allow direct paid status for سفري orders
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT order_type, restaurant_id FROM orders WHERE id = ?", (order_id,))
        order_check = cursor.fetchone()
        conn.close()
        
        if order_check and order_check['order_type'] == 'take_away':
            # Allow direct paid for takeaway orders, but verify restaurant ownership
            if order_check['restaurant_id'] != session.get('restaurant_id'):
                return jsonify({'error': 'Unauthorized'}), 401
            # Archive this order as an invoice before marking paid
            try:
                db.archive_takeaway_order(order_id)
            except Exception as e:
                return jsonify({'error': 'archive_failed', 'message': str(e)}), 500
        else:
            return jsonify({'error': 'manual_paid_forbidden', 'message': 'لا يمكن تغيير حالة الطلب إلى مدفوع يدوياً. يرجى تصفية حساب الطاولة بالكامل من قسم الطاولات.'}), 400
        
    if status == 'cancelled':
        # Check current status of the order
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT status, restaurant_id FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        conn.close()
        
        if order:
            current_status = order['status']
            # Restricted statuses: billing (بانتظار الدفع), served (تم التقديم), paid (مدفوع)
            if current_status in ['preparing', 'served', 'billing', 'paid']:
                if not password:
                    return jsonify({'error': 'password_required', 'message': 'إلغاء الطلب بعد التحضير أو طلب الفاتورة أو الدفع غير مسموح إلا بإدخال الرمز السري للمطعم.'}), 400
                
                # Verify password
                if not db.verify_restaurant_password(order['restaurant_id'], password):
                    return jsonify({'error': 'invalid_password', 'message': 'الرمز السري للمطعم غير صحيح. لا يمكن إلغاء الطلب.'}), 403
                    
    if status in ['pending', 'preparing', 'served', 'billing', 'paid', 'cancelled', 'completed']:
        db.update_order_status(order_id, status)
        # If cancelled, the cancel_order function in db already resets table if needed.
        # But since we're using update_order_status directly here (not cancel_order),
        # we need to also handle the table reset for 'cancelled' status
        if status == 'cancelled':
            # Use cancel_order which handles the table reset logic
            db.cancel_order(order_id)
            return jsonify({'success': True})
        return jsonify({'success': True})
    return jsonify({'error': 'Invalid status'}), 400

# --- CUSTOMER CANCEL ORDER (no login, token-based) ---
@app.route('/api/order/cancel/<int:order_id>', methods=['POST'])
def api_customer_cancel_order(order_id):
    """Customer can cancel their own order if status is 'pending' only."""
    data = request.json
    token = data.get('token')
    table_id = data.get('table_id')
    
    # Verify the order belongs to this table/token
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.*, t.token as table_token 
        FROM orders o 
        JOIN tables t ON o.table_id = t.id 
        WHERE o.id = ?
    """, (order_id,))
    order = cursor.fetchone()
    conn.close()
    
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    
    # Verify token matches the table
    if order['table_token'] != token or str(order['table_id']) != str(table_id):
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Only allow cancellation when order is 'pending'
    if order['status'] != 'pending':
        return jsonify({'error': 'cannot_cancel', 'message': 'لا يمكن إلغاء الطلب بعد بدء تحضيره. يرجى التواصل مع النادل.'}), 400
    
    db.cancel_order(order_id)
    return jsonify({'success': True, 'message': 'تم إلغاء الطلب بنجاح.'})

# --- CASHIER MODIFY ORDER ITEMS ---
@app.route('/api/order/item/delete/<int:order_item_id>', methods=['POST'])
def api_delete_order_item(order_item_id):
    """Cashier can delete a specific item from an order before preparation."""
    if not session.get('restaurant_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json or {}
    password = data.get('password')
    
    # Get the order this item belongs to
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT oi.*, o.status as order_status, o.restaurant_id, o.table_id
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE oi.id = ?
    """, (order_item_id,))
    item_info = cursor.fetchone()
    conn.close()
    
    if not item_info:
        return jsonify({'error': 'Item not found'}), 404
    
    if item_info['restaurant_id'] != session.get('restaurant_id'):
        return jsonify({'error': 'Unauthorized'}), 403
    
    current_status = item_info['order_status']
    
    # Restricted statuses require password
    if current_status in ['billing', 'served', 'paid']:
        if not password:
            return jsonify({'error': 'password_required', 'message': 'تعديل الطلب في هذه الحالة (بانتظار الدفع / تم التقديم / مدفوع) يتطلب الرمز السري للمطعم.'}), 400
        if not db.verify_restaurant_password(item_info['restaurant_id'], password):
            return jsonify({'error': 'invalid_password', 'message': 'الرمز السري للمطعم غير صحيح.'}), 403
    
    try:
        db.delete_order_item(order_item_id)
        return jsonify({'success': True, 'message': 'تم حذف الوجبة من الطلب بنجاح.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/order/item/update/<int:order_item_id>', methods=['POST'])
def api_update_order_item_quantity(order_item_id):
    """Cashier can update quantity of a specific item in an order."""
    if not session.get('restaurant_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json or {}
    new_quantity = data.get('quantity')
    password = data.get('password')
    
    if new_quantity is None or new_quantity < 0:
        return jsonify({'error': 'Invalid quantity'}), 400
    
    # Get the order this item belongs to
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT oi.*, o.status as order_status, o.restaurant_id, o.table_id
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE oi.id = ?
    """, (order_item_id,))
    item_info = cursor.fetchone()
    conn.close()
    
    if not item_info:
        return jsonify({'error': 'Item not found'}), 404
    
    if item_info['restaurant_id'] != session.get('restaurant_id'):
        return jsonify({'error': 'Unauthorized'}), 403
    
    current_status = item_info['order_status']
    
    # Restricted statuses require password
    if current_status in ['billing', 'served', 'paid']:
        if not password:
            return jsonify({'error': 'password_required', 'message': 'تعديل الطلب في هذه الحالة (بانتظار الدفع / تم التقديم / مدفوع) يتطلب الرمز السري للمطعم.'}), 400
        if not db.verify_restaurant_password(item_info['restaurant_id'], password):
            return jsonify({'error': 'invalid_password', 'message': 'الرمز السري للمطعم غير صحيح.'}), 403
    
    try:
        if new_quantity == 0:
            # Delete the item entirely
            db.delete_order_item(order_item_id)
            return jsonify({'success': True, 'message': 'تم حذف الوجبة من الطلب (الكمية أصبحت صفر).'})
        else:
            db.update_order_item_quantity(order_item_id, new_quantity)
            return jsonify({'success': True, 'message': 'تم تحديث كمية الوجبة بنجاح.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- CUSTOMER FULL INVOICE VIEW ---
@app.route('/api/table/full-invoice/<int:table_id>')
def api_full_table_invoice(table_id):
    """Get complete invoice for customer view with all details."""
    token = request.args.get('token')
    
    if not token:
        return jsonify({'error': 'Token required'}), 400
    
    # Verify table token
    table = db.get_table_by_token(token)
    if not table or table['id'] != table_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    invoice_data = db.get_full_table_invoice(table_id)
    if not invoice_data:
        return jsonify({'error': 'Table not found'}), 404
    
    return jsonify(invoice_data)

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
    restaurant_id = None
    
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT restaurant_id FROM tables WHERE id = ?", (table_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        restaurant_id = row['restaurant_id']
        
    if session.get('restaurant_id'):
        if restaurant_id == session['restaurant_id']:
            authorized = True
    elif token:
        # Check if token matches this table
        table = db.get_table_by_token(token)
        if table and table['id'] == table_id:
            authorized = True
            
    if not authorized or not restaurant_id:
        return jsonify({'error': 'Unauthorized'}), 401
        
    # Get restaurant VAT settings
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT vat_enabled, vat_percentage FROM restaurants WHERE id = ?", (restaurant_id,))
    rest = cursor.fetchone()
    conn.close()
    
    vat_enabled = rest['vat_enabled'] if rest else 1
    vat_percentage = rest['vat_percentage'] if rest else 15.0
    
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
        
    vat = subtotal * (vat_percentage / 100.0) if vat_enabled == 1 else 0.0
    grand_total = subtotal + vat
    
    return jsonify({
        'items': invoice_items,
        'subtotal': subtotal,
        'vat': vat,
        'vat_percentage': vat_percentage if vat_enabled == 1 else 0.0,
        'grand_total': grand_total
    })

@app.route('/api/restaurant/table/checkout/<int:table_id>', methods=['POST'])
def api_checkout_table(table_id):
    if not session.get('restaurant_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Check if there are any active orders for this table
    items = db.get_table_invoice(table_id)
    if not items or len(items) == 0:
        # No active orders — just reset the table silently
        db.set_table_status(table_id, 'available')
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE tables SET current_session_id = NULL WHERE id = ?", (table_id,))
        cursor.execute("UPDATE waiter_calls SET status = 'resolved' WHERE table_id = ? AND status = 'active'", (table_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'table_already_empty'})
        
    success = db.checkout_table(table_id)
    return jsonify({'success': success})

@app.route('/api/restaurant/tables-status')
def api_tables_status():
    if not session.get('restaurant_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, table_number, status, current_session_id FROM tables WHERE restaurant_id = ? AND table_number != 'سفري'", (session['restaurant_id'],))
    tables = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(tables)

@app.route('/api/restaurant/analytics')
def api_get_analytics():
    if not session.get('restaurant_id'):
        return jsonify({'error': 'Unauthorized'}), 401
        
    analytics = db.get_sales_analytics(session['restaurant_id'])
    return jsonify(analytics)

@app.route('/dashboard/export-sales')
def export_sales():
    if not session.get('restaurant_id'):
        return redirect(url_for('index'))
        
    restaurant_id = session['restaurant_id']
    month = request.args.get('month') # e.g. '06'
    year = request.args.get('year') # e.g. '2026'
    
    if not month or not year:
        flash("يرجى تحديد الشهر والسنة للتصدير.", "error")
        return redirect(url_for('restaurant_dashboard'))
        
    # Query invoices for this month and year
    conn = db.get_db()
    cursor = conn.cursor()
    
    query_date = f"{year}-{month}%"
    cursor.execute("""
        SELECT * FROM invoices 
        WHERE restaurant_id = ? 
          AND created_at LIKE ?
        ORDER BY created_at DESC
    """, (restaurant_id, query_date))
    invoices = cursor.fetchall()
    conn.close()
    
    # Prepare CSV data
    import csv
    import io
    from flask import Response
    
    output = io.StringIO()
    # UTF-8 BOM for Excel compatibility with Arabic
    output.write('\ufeff')
    writer = csv.writer(output)
    
    # Headers
    writer.writerow([
        'رقم الفاتورة',
        'رقم الطاولة',
        'تاريخ وتوقيت الفاتورة',
        'المجموع الفرعي',
        'قيمة الضريبة',
        'نسبة الضريبة (%)',
        'الإجمالي الكلي',
        'العملة',
        'الوجبات المطلوبة والكميات'
    ])
    
    # Rows
    for inv in invoices:
        import json
        try:
            items = json.loads(inv['items_json'])
            items_str = ", ".join([f"{item['name']} (x{item['quantity']})" for item in items])
        except Exception:
            items_str = ""
            
        writer.writerow([
            inv['id'],
            inv['table_number'],
            inv['created_at'],
            inv['subtotal'],
            inv['vat_amount'],
            inv['vat_rate'],
            inv['total_amount'],
            inv['currency'],
            items_str
        ])
        
    csv_data = output.getvalue()
    output.close()
    
    filename = f"sales_report_{year}_{month}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-disposition": f"attachment; filename={filename}",
            "Content-Type": "text/csv; charset=utf-8"
        }
    )

# --- PRINT ARCHIVED INVOICE ---

@app.route('/api/restaurant/invoice/<int:invoice_id>')
def api_get_invoice(invoice_id):
    """Get full details of an archived invoice (for printing/review)."""
    if not session.get('restaurant_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    invoice = db.get_invoice_by_id(invoice_id)
    if not invoice:
        return jsonify({'error': 'Invoice not found'}), 404
    
    # Verify the invoice belongs to this restaurant
    if invoice['restaurant_id'] != session['restaurant_id']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Parse items JSON
    import json
    try:
        items = json.loads(invoice['items_json'])
    except Exception:
        items = []
    
    # Get restaurant info for the header
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name, logo, currency FROM restaurants WHERE id = ?", (invoice['restaurant_id'],))
    rest = cursor.fetchone()
    conn.close()
    
    return jsonify({
        'id': invoice['id'],
        'table_number': invoice['table_number'],
        'created_at': invoice['created_at'],
        'subtotal': invoice['subtotal'],
        'vat_rate': invoice['vat_rate'],
        'vat_amount': invoice['vat_amount'],
        'total_amount': invoice['total_amount'],
        'currency': invoice['currency'],
        'items': items,
        'restaurant_name': rest['name'] if rest else '',
        'restaurant_logo': rest['logo'] if rest else None
    })

@app.route('/dashboard/invoice/<int:invoice_id>/print')
def print_invoice(invoice_id):
    """Render a printable invoice page."""
    if not session.get('restaurant_id'):
        flash("يرجى تسجيل الدخول أولاً.", "error")
        return redirect(url_for('index'))
    
    invoice = db.get_invoice_by_id(invoice_id)
    if not invoice or invoice['restaurant_id'] != session['restaurant_id']:
        flash("الفاتورة غير موجودة أو غير مصرح بها.", "error")
        return redirect(url_for('restaurant_dashboard'))
    
    # Parse items JSON
    import json
    try:
        items = json.loads(invoice['items_json'])
    except Exception:
        items = []
    
    # Get restaurant info
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name, logo, currency FROM restaurants WHERE id = ?", (invoice['restaurant_id'],))
    rest = cursor.fetchone()
    conn.close()
    
    return render_template('print_invoice.html', 
                           invoice=invoice, 
                           items=items, 
                           restaurant=rest)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
