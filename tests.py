import os
import sys
import unittest
import json
import sqlite3

# Add parent path to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
import database as db

class TestQRMenuSystem(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # We will use the existing database database.db since it's already set up
        # and has data. We can inspect the existing data and insert temporary records.
        app.config['TESTING'] = True
        cls.client = app.test_client()
        
    def test_01_public_menu(self):
        print("\n--- Test 1: Public Menu Route ---")
        # Fetch existing restaurant slug
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT slug FROM restaurants LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            print("No restaurant in DB, skipping.")
            return
            
        slug = row['slug']
        print(f"Testing public menu for restaurant: {slug}")
        response = self.client.get(f'/r/{slug}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'mostafa', response.data or b'')
        print("Public menu page fetched successfully!")

    def test_02_dine_in_and_takeaway_order_flow(self):
        print("\n--- Test 2: Dine-in and Takeaway Order Flow ---")
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, slug FROM restaurants LIMIT 1")
        restaurant = cursor.fetchone()
        
        if not restaurant:
            print("No restaurant in DB, skipping.")
            conn.close()
            return
            
        restaurant_id = restaurant['id']
        slug = restaurant['slug']
        
        # Ensure we have a category and menu item
        cursor.execute("SELECT id FROM categories WHERE restaurant_id = ? LIMIT 1", (restaurant_id,))
        category = cursor.fetchone()
        if not category:
            cat_id = db.add_category(restaurant_id, "وجبات رئيسية")
        else:
            cat_id = category['id']
            
        cursor.execute("SELECT id, price FROM menu_items WHERE category_id = ? LIMIT 1", (cat_id,))
        item = cursor.fetchone()
        if not item:
            item_id = db.add_menu_item(cat_id, "برغر كلاسيك", "برغر لحم بقري مشوي", 25.0)
            item_price = 25.0
        else:
            item_id = item['id']
            item_price = item['price']
            
        # Get or create table
        cursor.execute("SELECT id, token FROM tables WHERE restaurant_id = ? AND table_number != 'سفري' LIMIT 1", (restaurant_id,))
        table = cursor.fetchone()
        if not table:
            # Add table
            import uuid
            token = uuid.uuid4().hex
            table_id = db.add_table(restaurant_id, "1", token, capacity=4, location="الصالة الرئيسية")
        else:
            table_id = table['id']
            token = table['token']
            
        conn.close()
        
        # 1. Place Dine-in Order
        order_payload = {
            "restaurant_id": restaurant_id,
            "table_id": table_id,
            "token": token,
            "order_type": "dine_in",
            "notes": "بدون بصل",
            "items": [
                {"menu_item_id": item_id, "quantity": 2, "price": item_price}
            ]
        }
        print("Sending Dine-in Order...")
        response = self.client.post('/api/order/create', 
                                    data=json.dumps(order_payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        res_data = json.loads(response.data)
        self.assertTrue(res_data['success'])
        order_id = res_data['order_id']
        print(f"Dine-in Order created successfully! ID: {order_id}")
        
        # Check order status
        response = self.client.get(f'/api/order/status/{order_id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data)['status'], 'pending')
        
        # 2. Place Takeaway Order
        takeaway_payload = {
            "restaurant_id": restaurant_id,
            "order_type": "take_away",
            "notes": "سفري مع صوص خارجي",
            "items": [
                {"menu_item_id": item_id, "quantity": 1, "price": item_price}
            ]
        }
        print("Sending Takeaway Order...")
        response = self.client.post('/api/order/create', 
                                    data=json.dumps(takeaway_payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        res_data = json.loads(response.data)
        self.assertTrue(res_data['success'])
        takeaway_order_id = res_data['order_id']
        print(f"Takeaway Order created successfully! ID: {takeaway_order_id}")
        
        # 3. Call waiter
        waiter_payload = {
            "restaurant_id": restaurant_id,
            "table_id": table_id,
            "token": token,
            "type": "waiter"
        }
        print("Calling waiter...")
        response = self.client.post('/api/waiter-call/create',
                                    data=json.dumps(waiter_payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.data)['success'])
        
        # 4. Request bill
        bill_payload = {
            "restaurant_id": restaurant_id,
            "table_id": table_id,
            "token": token,
            "type": "bill"
        }
        print("Requesting bill...")
        response = self.client.post('/api/waiter-call/create',
                                    data=json.dumps(bill_payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.data)['success'])
        
        # Check table status has been updated to 'billing'
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM tables WHERE id = ?", (table_id,))
        t_status = cursor.fetchone()['status']
        self.assertEqual(t_status, 'billing')
        print("Table status successfully updated to 'billing' upon invoice request!")
        
        # Fetch invoice details
        print("Fetching invoice...")
        response = self.client.get(f'/api/restaurant/table/invoice/{table_id}?token={token}')
        self.assertEqual(response.status_code, 200)
        invoice = json.loads(response.data)
        print("Invoice items:", invoice['items'])
        self.assertEqual(len(invoice['items']), 1)
        self.assertEqual(invoice['subtotal'], item_price * 2)
        
        # Checkout the table (waiter confirms payment)
        # We need to simulate being logged in to checkout, or check session.
        # Let's check app.py session requirement:
        # In api_checkout_table:
        # if not session.get('restaurant_id'): return jsonify({'error': 'Unauthorized'}), 401
        # We can set session using Flask test client's session transaction
        with self.client.session_transaction() as sess:
            sess['restaurant_id'] = restaurant_id
            sess['user_id'] = 2
            sess['role'] = 'restaurant'
            
        print("Confirming checkout...")
        response = self.client.post(f'/api/restaurant/table/checkout/{table_id}')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.data)['success'])
        
        # Verify table has reset to 'available'
        cursor.execute("SELECT status, current_session_id FROM tables WHERE id = ?", (table_id,))
        t_row = cursor.fetchone()
        self.assertEqual(t_row['status'], 'available')
        self.assertIsNone(t_row['current_session_id'])
        print("Table reset to available and current session cleared successfully!")
        
        # Check analytics API
        print("Testing analytics API...")
        response = self.client.get('/api/restaurant/analytics')
        self.assertEqual(response.status_code, 200)
        analytics = json.loads(response.data)
        print("Daily Sales after checkout:", analytics['daily_sales'])
        self.assertGreater(analytics['daily_sales'], 0)
        
        conn.close()

    def test_03_update_settings_and_currency_flow(self):
        print("\n--- Test 3: Update Settings and Currency Flow ---")
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM restaurants LIMIT 1")
        restaurant = cursor.fetchone()
        self.assertIsNotNone(restaurant)
        restaurant_id = restaurant['id']
        conn.close()
        
        # Log in first
        with self.client.session_transaction() as sess:
            sess['restaurant_id'] = restaurant_id
            sess['user_id'] = 2
            sess['role'] = 'restaurant'
            sess['restaurant_slug'] = 'mostafa'
            
        settings_payload = {
            "name": "المصطفى للبرغر الممتاز",
            "theme_name": "custom",
            "theme_primary_color": "#00ff00",
            "theme_bg_color": "#222222",
            "theme_surface_color": "#333333",
            "theme_text_color": "#dddddd",
            "currency": "USD"
        }
        
        print("Sending update settings request...")
        response = self.client.post('/dashboard/update-settings', data=settings_payload)
        self.assertEqual(response.status_code, 302) # redirects to dashboard
        
        # Check database directly to see if currency and name are updated
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name, currency, theme_name FROM restaurants WHERE id = ?", (restaurant_id,))
        row = cursor.fetchone()
        conn.close()
        
        self.assertEqual(row['name'], "المصطفى للبرغر الممتاز")
        self.assertEqual(row['currency'], "USD")
        self.assertEqual(row['theme_name'], "custom")
        print("Settings and Currency updated and verified in database successfully!")

    def test_04_vat_and_order_protection_flow(self):
        print("\n--- Test 4: VAT settings, Manual Paid Block, and Password Protected Cancellation ---")
        
        # 1. Reset user_id=2 password to '123456' for verification
        from werkzeug.security import generate_password_hash
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password = ? WHERE id = ?", (generate_password_hash("123456"), 2))
        conn.commit()
        
        # Get restaurant and table info
        cursor.execute("SELECT id FROM restaurants LIMIT 1")
        restaurant_id = cursor.fetchone()['id']
        
        cursor.execute("SELECT id, token FROM tables WHERE restaurant_id = ? AND table_number != 'سفري' LIMIT 1", (restaurant_id,))
        table = cursor.fetchone()
        table_id = table['id']
        token = table['token']
        
        # Get menu item
        cursor.execute("SELECT id, price FROM menu_items LIMIT 1")
        item = cursor.fetchone()
        item_id = item['id']
        item_price = item['price']
        
        # Configure VAT = 10.0% enabled on restaurant settings
        db.update_restaurant_settings(
            restaurant_id=restaurant_id,
            name="المطعم التجريبي",
            theme_name="custom",
            primary_color="#ff0000",
            bg_color="#ffffff",
            surface_color="#f0f0f0",
            text_color="#000000",
            currency="USD",
            vat_enabled=1,
            vat_percentage=10.0
        )
        
        conn.close()
        
        # Place a new Dine-in Order
        order_payload = {
            "restaurant_id": restaurant_id,
            "table_id": table_id,
            "token": token,
            "order_type": "dine_in",
            "items": [{"menu_item_id": item_id, "quantity": 1, "price": item_price}]
        }
        
        response = self.client.post('/api/order/create', 
                                    data=json.dumps(order_payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        order_id = json.loads(response.data)['order_id']
        
        # Try to manually change status to 'paid' (Forbidden)
        response = self.client.post(f'/api/order/update-status/{order_id}',
                                    data=json.dumps({"status": "paid"}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data)['error'], 'manual_paid_forbidden')
        print("Manual update to 'paid' status blocked successfully!")
        
        # Change status to 'preparing'
        response = self.client.post(f'/api/order/update-status/{order_id}',
                                    data=json.dumps({"status": "preparing"}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        # Try to cancel the order without password (Forbidden/Required)
        response = self.client.post(f'/api/order/update-status/{order_id}',
                                    data=json.dumps({"status": "cancelled"}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data)['error'], 'password_required')
        print("Cancellation of preparing order without password blocked successfully!")
        
        # Try to cancel with invalid password (Forbidden)
        response = self.client.post(f'/api/order/update-status/{order_id}',
                                    data=json.dumps({"status": "cancelled", "password": "wrongpassword"}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(json.loads(response.data)['error'], 'invalid_password')
        print("Cancellation of preparing order with wrong password blocked successfully!")
        
        # Cancel with correct password (Success)
        response = self.client.post(f'/api/order/update-status/{order_id}',
                                    data=json.dumps({"status": "cancelled", "password": "123456"}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.data)['success'])
        print("Cancellation of preparing order with correct password succeeded!")
        
        # Place another order for checkout and invoice archiving verification
        response = self.client.post('/api/order/create', 
                                    data=json.dumps(order_payload),
                                    content_type='application/json')
        order_id_2 = json.loads(response.data)['order_id']
        
        # Checkout the table
        with self.client.session_transaction() as sess:
            sess['restaurant_id'] = restaurant_id
            sess['user_id'] = 2
            sess['role'] = 'restaurant'
            
        response = self.client.post(f'/api/restaurant/table/checkout/{table_id}')
        self.assertEqual(response.status_code, 200)
        
        # Verify the archived invoice exists in the DB and matches the 10.0% VAT rate
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM invoices WHERE table_id = ? ORDER BY created_at DESC LIMIT 1", (table_id,))
        invoice = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice['vat_rate'], 10.0)
        self.assertEqual(invoice['vat_amount'], item_price * 0.1)
        self.assertEqual(invoice['total_amount'], item_price * 1.1)
        print("Archived invoice verified successfully with correct VAT calculation (10%)!")

if __name__ == '__main__':
    unittest.main()
