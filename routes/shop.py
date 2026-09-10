import traceback
from datetime import datetime, timedelta
import json
import requests
import re
import urllib.parse
import base64

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from config import Config
from utils.data import (
    get_all_categories,
    get_cart,
    get_category_icon,
    get_sample_products,
    load_bundles,
    load_products,
    save_order_to_supabase,
    update_product_stock,
)

shop_bp = Blueprint('shop', __name__)


# ============================================================
# WHATSAPP NOTIFICATION HELPER
# ============================================================

def send_whatsapp_notification(order_data, customer_name, order_id, total):
    """Send order notification via WhatsApp"""
    try:
        items_text = ""
        for item in order_data.get('items', []):
            items_text += f"  • {item.get('name')} x{item.get('quantity')} = KSh {item.get('total', 0):,.2f}\n"
        
        net_revenue = order_data.get('net_revenue', 0)
        shipping = order_data.get('shipping', 0)
        tax = order_data.get('tax', 0)
        discount = order_data.get('discount', 0)
        subtotal = order_data.get('subtotal', 0)
        total_charged = order_data.get('total_charged', total)
        
        message = f"""
🛍️ *NEW ORDER ALERT!*

📋 *Order ID:* {order_id}
👤 *Customer:* {customer_name}
📧 *Email:* {order_data.get('customer_email', 'N/A')}
📱 *Phone:* {order_data.get('customer_phone', 'N/A')}
📍 *Address:* {order_data.get('customer_address', 'N/A')}
💳 *Payment:* {order_data.get('payment_method', 'cash').upper()}

📦 *Items:*
{items_text}

💰 *Order Breakdown:*
  • Subtotal: KSh {subtotal:,.2f}
  • Discount: -KSh {discount:,.2f}
  • Tax (16%): KSh {tax:,.2f}
  • Shipping: KSh {shipping:,.2f} 🚚

📊 *Revenue:*
  • Net Revenue: KSh {net_revenue:,.2f} ✅ (products only)
  • Total Charged: KSh {total_charged:,.2f}

📅 *Order Date:* {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}

🔗 *View Order:* https://acaciamart.shop/admin/orders

✅ *Thank you for your order!*
        """.strip()
        
        encoded_message = urllib.parse.quote(message)
        WHATSAPP_PHONE = Config.MPESA_BUSINESS_PHONE
        
        whatsapp_url = f"https://api.whatsapp.com/send?phone={WHATSAPP_PHONE}&text={encoded_message}"
        
        print(f"📱 WhatsApp notification generated for {WHATSAPP_PHONE}")
        
        return {
            'success': True,
            'whatsapp_url': whatsapp_url,
            'message': message
        }
        
    except Exception as e:
        print(f"❌ Error sending WhatsApp notification: {e}")
        return {'success': False, 'error': str(e)}


# ============================================================
# M-PESA HELPER FUNCTIONS - PRODUCTION (TILL)
# ============================================================

def get_mpesa_access_token():
    """Get M-Pesa access token - PRODUCTION"""
    consumer_key = Config.MPESA_CONSUMER_KEY
    consumer_secret = Config.MPESA_CONSUMER_SECRET
    url = Config.MPESA_AUTH_URL
    
    try:
        response = requests.get(
            url,
            auth=(consumer_key, consumer_secret),
            timeout=30,
            headers={'Accept': 'application/json'}
        )
        
        if response.status_code == 200:
            token = response.json().get('access_token')
            print(f"✅ M-Pesa token obtained")
            return token
        else:
            print(f"❌ Token failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ M-Pesa token error: {e}")
        return None


def get_mpesa_shortcode():
    """Get the correct shortcode for Till (Buy Goods)"""
    # ✅ Till number for STK Push
    return getattr(Config, 'MPESA_TILL_NUMBER', Config.MPESA_SHORTCODE)


def generate_mpesa_password():
    """Generate password for STK Push - uses TILL"""
    shortcode = get_mpesa_shortcode()
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    password_str = shortcode + Config.MPESA_PASSKEY + timestamp
    password = base64.b64encode(password_str.encode()).decode('utf-8')
    return password, timestamp


def format_phone_number(phone):
    """Format phone to 254XXXXXXXXX"""
    if not phone:
        return None
    
    cleaned = re.sub(r'\D', '', str(phone))
    
    if cleaned.startswith('254') and len(cleaned) == 12:
        return cleaned
    elif cleaned.startswith('0') and len(cleaned) == 10:
        return '254' + cleaned[1:]
    elif cleaned.startswith('7') and len(cleaned) == 9:
        return '254' + cleaned
    elif cleaned.startswith('1') and len(cleaned) == 9:
        return '254' + cleaned
    elif len(cleaned) == 9:
        return '254' + cleaned
    elif len(cleaned) == 12:
        return cleaned
    else:
        return None


def mpesa_stk_push(phone_number, amount, order_id):
    """Initiate M-Pesa STK Push - TILL (Buy Goods)"""
    
    formatted_phone = format_phone_number(phone_number)
    
    if not formatted_phone:
        return False, None, f"Invalid phone number: {phone_number}. Use 0712345678"
    
    print(f"📱 Phone: {phone_number} → {formatted_phone}")
    
    if len(formatted_phone) != 12 or not formatted_phone.startswith('254'):
        return False, None, "Phone number must be 12 digits (e.g., 254712345678)"
    
    access_token = get_mpesa_access_token()
    if not access_token:
        return False, None, "Failed to authenticate with M-Pesa. Check credentials."
    
    password, timestamp = generate_mpesa_password()
    shortcode = get_mpesa_shortcode()
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    amount_int = int(float(amount))
    
    # ✅ TILL PAYLOAD - CustomerBuyGoodsOnline, NO AccountReference
    payload = {
        'BusinessShortCode': shortcode,
        'Password': password,
        'Timestamp': timestamp,
        'TransactionType': 'CustomerBuyGoodsOnline',   # ✅ TILL
        'Amount': amount_int,
        'PartyA': formatted_phone,
        'PartyB': shortcode,                            # ✅ Till number
        'PhoneNumber': formatted_phone,
        'CallBackURL': Config.MPESA_CALLBACK_URL,
        'TransactionDesc': f'Payment for order {order_id}'[:50]
        # ✅ NO AccountReference for Till
    }
    
    print(f"📤 STK Push (TILL) to {formatted_phone} for KSh {amount_int}")
    print(f"   BusinessShortCode: {shortcode}")
    print(f"   TransactionType: CustomerBuyGoodsOnline")
    
    try:
        response = requests.post(
            Config.MPESA_STK_PUSH_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        result = response.json()
        print(f"📱 STK Response: {result}")
        
        if result.get('ResponseCode') == '0':
            checkout_id = result.get('CheckoutRequestID')
            return True, checkout_id, "STK Push sent to your phone"
        else:
            error_msg = result.get('ResponseDescription', 'Payment initiation failed')
            return False, None, error_msg
            
    except Exception as e:
        print(f"❌ M-Pesa error: {e}")
        return False, None, str(e)


def mpesa_query_status(checkout_request_id):
    """Query STK Push status - uses TILL"""
    access_token = get_mpesa_access_token()
    if not access_token:
        return None, "Failed to authenticate"
    
    password, timestamp = generate_mpesa_password()
    shortcode = get_mpesa_shortcode()
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'BusinessShortCode': shortcode,
        'Password': password,
        'Timestamp': timestamp,
        'CheckoutRequestID': checkout_request_id
    }
    
    try:
        response = requests.post(
            Config.MPESA_QUERY_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        result = response.json()
        return result, None
        
    except Exception as e:
        return None, str(e)


# ============================================================
# CATEGORY ICONS
# ============================================================
CATEGORY_ICONS = {
    'All': 'fa-th-large', 'Beverages': 'fa-wine-bottle', 'Snacks': 'fa-utensils',
    'Groceries': 'fa-apple-alt', 'Food': 'fa-apple-alt', 'Electronics': 'fa-laptop',
    'Phones': 'fa-mobile-alt', 'Phone Accessories': 'fa-plug', 'Laptops': 'fa-laptop',
    'Computers': 'fa-desktop', 'Audio': 'fa-headphones', 'Headphones': 'fa-headphones',
    'Fashion': 'fa-tshirt', 'Clothing': 'fa-tshirt', "Men's Fashion": 'fa-user-tie',
    "Women's Fashion": 'fa-female', 'Shoes': 'fa-shoe-prints', 'Accessories': 'fa-plug',
    'Bags': 'fa-bag-shopping', 'Watches': 'fa-clock', 'Jewelry': 'fa-ring',
    'Sunglasses': 'fa-glasses', 'Home & Kitchen': 'fa-utensils', 'Furniture': 'fa-couch',
    'Home Decor': 'fa-home', 'Kitchen': 'fa-kitchen-set', 'Bedding': 'fa-bed',
    'Bath': 'fa-bath', 'Cleaning': 'fa-spray-can-sparkles', 'Laundry': 'fa-shirt',
    'Beauty': 'fa-spa', 'Personal Care': 'fa-spa', 'Skincare': 'fa-spa',
    'Makeup': 'fa-paint-brush', 'Fragrance': 'fa-perfume', 'Books': 'fa-book',
    'Stationery': 'fa-pen', 'School Supplies': 'fa-book-open', 'Office Supplies': 'fa-briefcase',
    'Toys': 'fa-gamepad', 'Games': 'fa-gamepad', 'Gaming': 'fa-gamepad',
    'Sports': 'fa-dumbbell', 'Fitness': 'fa-dumbbell', 'Outdoor': 'fa-tree',
    'Garden': 'fa-tree', 'Automotive': 'fa-car', 'Car Accessories': 'fa-car',
    'Health': 'fa-heartbeat', 'Wellness': 'fa-heartbeat', 'Baby': 'fa-baby',
    'Kids': 'fa-baby', 'Pet': 'fa-paw', 'Pet Supplies': 'fa-paw',
    'Music': 'fa-music', 'Instruments': 'fa-guitar', 'Cameras': 'fa-camera',
    'Photography': 'fa-camera', 'Printers': 'fa-print', 'Networking': 'fa-network-wired',
    'Software': 'fa-code', 'Gifts': 'fa-gift', 'Flowers': 'fa-seedling',
    'Crafts': 'fa-paintbrush', 'Hobbies': 'fa-puzzle-piece', 'Party': 'fa-party-horn',
    'Uncategorized': 'fa-tag', 'Other': 'fa-tag',
}

def get_category_icon(category):
    return CATEGORY_ICONS.get(category, 'fa-tag')


def clean_products(products):
    """Clean products to ensure no None values"""
    if not products:
        return []
    
    cleaned = []
    for p in products:
        if not p:
            continue
        clean = dict(p)
        if clean.get('stock') is None: clean['stock'] = 0
        if clean.get('price') is None: clean['price'] = 0
        if clean.get('name') is None: clean['name'] = 'Unnamed Product'
        if clean.get('category') is None: clean['category'] = 'Uncategorized'
        if clean.get('image') is None: clean['image'] = ''
        if clean.get('description') is None: clean['description'] = ''
        if clean.get('badge') is None: clean['badge'] = ''
        if clean.get('cost_price') is None: clean['cost_price'] = 0
        if clean.get('rating') is None: clean['rating'] = 4.0
        if clean.get('reviews') is None: clean['reviews'] = 0
        if clean.get('barcode') is None: clean['barcode'] = ''
        cleaned.append(clean)
    return cleaned


def build_categories(products_list):
    """Build categories dictionary with counts and icons"""
    categories = {}
    for product in products_list:
        if not product:
            continue
        cat = product.get('category', 'Uncategorized')
        if cat not in categories:
            categories[cat] = {
                'name': cat,
                'icon': get_category_icon(cat),
                'count': 0,
            }
        categories[cat]['count'] += 1
    
    sorted_categories = dict(sorted(categories.items(), key=lambda x: x[0].lower()))
    return sorted_categories


# ============================================================
# ROUTES
# ============================================================

@shop_bp.route('/')
def index():
    products_list = load_products()
    products_list = clean_products(products_list)
    bundles_list = load_bundles()

    products_dict = {}
    for product in products_list:
        if product and 'id' in product:
            products_dict[str(product['id'])] = product

    bundles_dict = {}
    for bundle in bundles_list:
        if bundle and 'id' in bundle:
            bundles_dict[str(bundle['id'])] = bundle

    best_sellers = [p for p in products_list if p.get('badge') == 'Best Seller']
    new_arrivals = [p for p in products_list if p.get('badge') == 'New']
    trending = [p for p in products_list if p.get('badge') == 'Trending']

    categories = build_categories(products_list)

    all_categories = {
        'All': {'name': 'All', 'icon': 'fa-th-large', 'count': len(products_list)}
    }
    all_categories.update(categories)

    return render_template(
        'shop.html',
        products=products_dict,
        all_products=products_dict,
        bundles=bundles_dict,
        best_sellers=best_sellers,
        new_arrivals=new_arrivals,
        trending=trending,
        categories=all_categories,
        CATEGORIES=get_all_categories(),
    )


@shop_bp.route('/category/<category_name>')
def category_page(category_name):
    products = load_products()
    products = clean_products(products)
    
    products_dict = {}
    for product in products:
        if product and 'id' in product and product.get('category') == category_name:
            products_dict[str(product['id'])] = product
    
    categories = build_categories(products)
    all_categories = {
        'All': {'name': 'All', 'icon': 'fa-th-large', 'count': len(products)}
    }
    all_categories.update(categories)
    
    return render_template(
        'category.html', 
        products=products_dict, 
        category_name=category_name, 
        categories=all_categories,
        CATEGORIES=get_all_categories()
    )


@shop_bp.route('/product/<product_id>')
def product_detail(product_id):
    products = load_products()
    products = clean_products(products)
    
    product = None
    for candidate in products:
        if str(candidate.get('id')) == str(product_id):
            product = candidate
            break

    if not product:
        flash('Product not found', 'danger')
        return redirect(url_for('shop.index'))

    related = [p for p in products if p.get('category') == product.get('category') and str(p.get('id')) != product_id][:4]
    related_dict = {}
    for item in related:
        if item and 'id' in item:
            related_dict[str(item['id'])] = item

    return render_template('product.html', product=product, related=related_dict)


@shop_bp.route('/cart')
def cart_page():
    try:
        cart = get_cart()
        cart_items = []
        subtotal = 0
        total_items = 0
        products = load_products()
        products = clean_products(products)
        bundles = load_bundles()

        for item_id, quantity in cart.items():
            if quantity <= 0:
                continue
            product = next((p for p in products if str(p.get('id')) == str(item_id)), None)
            if product:
                item_total = product.get('price', 0) * quantity
                cart_items.append({
                    'id': item_id, 'name': product.get('name', 'Product'),
                    'price': product.get('price', 0), 'image': product.get('image', ''),
                    'type': 'product', 'quantity': quantity, 'item_total': item_total,
                    'stock': product.get('stock', 0),
                    'description': product.get('description', ''),
                    'specs': product.get('specs', []),
                })
                subtotal += item_total
                total_items += quantity
                continue

            for bundle in bundles:
                if str(bundle.get('id')) == str(item_id):
                    item_total = bundle.get('price', 0) * quantity
                    cart_items.append({
                        'id': item_id, 'name': bundle.get('name', 'Bundle'),
                        'price': bundle.get('price', 0), 'image': bundle.get('image', ''),
                        'type': 'bundle', 'quantity': quantity, 'item_total': item_total,
                        'products': bundle.get('products', []),
                    })
                    subtotal += item_total
                    total_items += quantity
                    break

        return render_template('cart.html', 
            cart_items=cart_items, 
            subtotal=subtotal, 
            total_items=total_items
        )
    except Exception as exc:
        print(f'Cart error: {exc}')
        flash('Error loading cart', 'danger')
        return redirect(url_for('shop.index'))


@shop_bp.route('/add-to-cart/<item_id>', methods=['POST'])
def add_to_cart(item_id):
    try:
        cart = get_cart()
        products = load_products()
        products = clean_products(products)
        bundles = load_bundles()

        product = next((p for p in products if str(p.get('id')) == str(item_id)), None)
        if product:
            current_qty = cart.get(item_id, 0)
            if current_qty >= product.get('stock', 0):
                return jsonify({'success': False, 'message': 'Not enough stock available!'})

        bundle_exists = any(str(b.get('id')) == str(item_id) for b in bundles)
        if not product and not bundle_exists:
            return jsonify({'success': False, 'message': 'Item not found'})

        cart[item_id] = cart.get(item_id, 0) + 1
        session['cart'] = cart
        session.modified = True
        total_items = sum(cart.values())
        return jsonify({'success': True, 'message': 'Added to cart!', 'count': total_items, 'quantity': cart[item_id]})
    except Exception as exc:
        print(f'Error adding to cart: {exc}')
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error: {str(exc)}'}), 500


@shop_bp.route('/update-cart/<item_id>/<action>', methods=['POST'])
def update_cart_item(item_id, action):
    try:
        cart = get_cart()
        products = load_products()
        products = clean_products(products)

        if action == 'increase':
            product = next((p for p in products if str(p.get('id')) == str(item_id)), None)
            if product:
                current = cart.get(item_id, 0)
                if current >= product.get('stock', 0):
                    return jsonify({'success': False, 'message': 'Not enough stock available!'})
            cart[item_id] = cart.get(item_id, 0) + 1
        elif action == 'decrease':
            if item_id in cart:
                if cart[item_id] <= 1:
                    del cart[item_id]
                else:
                    cart[item_id] -= 1
            else:
                return jsonify({'success': False, 'message': 'Item not in cart'})
        elif action == 'remove':
            if item_id in cart:
                del cart[item_id]
            else:
                return jsonify({'success': False, 'message': 'Item not in cart'})
        else:
            return jsonify({'success': False, 'message': 'Invalid action'})

        session['cart'] = cart
        session.modified = True

        subtotal = 0
        bundles = load_bundles()
        for iid, qty in cart.items():
            for product in products:
                if str(product.get('id')) == str(iid):
                    subtotal += product.get('price', 0) * qty
                    break
            else:
                for bundle in bundles:
                    if str(bundle.get('id')) == str(iid):
                        subtotal += bundle.get('price', 0) * qty
                        break

        item_price = 0
        for product in products:
            if str(product.get('id')) == str(item_id):
                item_price = product.get('price', 0)
                break
        else:
            for bundle in bundles:
                if str(bundle.get('id')) == str(item_id):
                    item_price = bundle.get('price', 0)
                    break

        return jsonify({
            'success': True,
            'quantity': cart.get(item_id, 0),
            'subtotal': subtotal,
            'total_items': sum(cart.values()),
            'item_total': item_price * cart.get(item_id, 0),
        })
    except Exception as exc:
        print(f'Error updating cart: {exc}')
        return jsonify({'success': False, 'message': str(exc)}), 500


@shop_bp.route('/remove-from-cart/<item_id>', methods=['POST'])
def remove_from_cart(item_id):
    try:
        cart = get_cart()
        if item_id in cart:
            del cart[item_id]
            session['cart'] = cart
            session.modified = True
            return jsonify({'success': True, 'message': 'Removed from cart!', 'count': sum(cart.values())})
        return jsonify({'success': False, 'message': 'Item not in cart'})
    except Exception as exc:
        return jsonify({'success': False, 'message': str(exc)}), 500


@shop_bp.route('/checkout')
def checkout_page():
    try:
        cart = get_cart()
        if not cart:
            flash('Your cart is empty', 'warning')
            return redirect(url_for('shop.index'))

        cart_items = []
        subtotal = 0
        total_items = 0
        products = load_products()
        products = clean_products(products)
        bundles = load_bundles()

        for item_id, quantity in cart.items():
            if quantity <= 0:
                continue
            product = next((p for p in products if str(p.get('id')) == str(item_id)), None)
            if product:
                item_total = product.get('price', 0) * quantity
                cart_items.append({
                    'id': item_id, 'name': product.get('name', 'Product'),
                    'price': product.get('price', 0), 'image': product.get('image', ''),
                    'type': 'product', 'quantity': quantity, 'item_total': item_total,
                    'description': product.get('description', ''),
                    'specs': product.get('specs', []),
                })
                subtotal += item_total
                total_items += quantity
                continue

            for bundle in bundles:
                if str(bundle.get('id')) == str(item_id):
                    item_total = bundle.get('price', 0) * quantity
                    cart_items.append({
                        'id': item_id, 'name': bundle.get('name', 'Bundle'),
                        'price': bundle.get('price', 0), 'image': bundle.get('image', ''),
                        'type': 'bundle', 'quantity': quantity, 'item_total': item_total,
                    })
                    subtotal += item_total
                    total_items += quantity
                    break

        order_id = f'ORD-{datetime.now().strftime("%Y%m%d%H%M%S")}'
        shipping = 0
        total = subtotal + shipping

        return render_template('checkout.html', 
            cart_items=cart_items, 
            subtotal=subtotal,
            total=total,
            shipping=shipping,
            total_items=total_items,
            order_id=order_id,
            mpesa_enabled=True
        )
    except Exception as exc:
        print(f'Checkout error: {exc}')
        flash('Error loading checkout', 'danger')
        return redirect(url_for('shop.index'))


# ============================================================
# M-PESA ROUTES
# ============================================================

@shop_bp.route('/mpesa/initiate', methods=['POST'])
def mpesa_initiate():
    """Initiate M-Pesa payment - TILL"""
    try:
        data = request.get_json()
        phone = data.get('phone', '')
        amount = float(data.get('amount', 0))
        order_id = data.get('order_id', f'ORD-{datetime.now().strftime("%Y%m%d%H%M%S")}')
        
        print(f"\n{'='*60}")
        print(f"📱 M-PESA INITIATE (TILL) | Phone: {phone} | Amount: {amount}")
        print(f"{'='*60}")
        
        if not phone:
            return jsonify({'success': False, 'message': 'Phone number required'})
        
        if amount <= 0:
            return jsonify({'success': False, 'message': 'Invalid amount'})
        
        success, checkout_id, message = mpesa_stk_push(phone, amount, order_id)
        
        if success:
            session['mpesa_checkout_id'] = checkout_id
            session['mpesa_order_id'] = order_id
            
            return jsonify({
                'success': True,
                'checkout_request_id': checkout_id,
                'order_id': order_id,
                'message': message
            })
        else:
            return jsonify({'success': False, 'message': message})
            
    except Exception as e:
        print(f"❌ M-Pesa initiate error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)})


@shop_bp.route('/mpesa/status', methods=['POST'])
def mpesa_status():
    """Check M-Pesa payment status"""
    try:
        data = request.get_json()
        checkout_id = data.get('checkout_request_id')
        elapsed = data.get('elapsed', 0)
        
        if not checkout_id:
            return jsonify({'success': False, 'message': 'Checkout ID required'})
        
        result, error = mpesa_query_status(checkout_id)
        
        if error:
            return jsonify({'success': False, 'message': error})
        
        if result:
            result_code = str(result.get('ResultCode', ''))
            result_desc = result.get('ResultDesc', 'Unknown')
            
            print(f"📱 Status: code={result_code}, desc={result_desc}, elapsed={elapsed}s")
            
            if result_code == '0':
                return jsonify({
                    'success': True, 'status': 'completed',
                    'message': 'Payment successful!', 'data': result
                })
            
            elif result_code in ['1037', '1001', '4999', '429', '500']:
                if result_code == '1037' and elapsed > 90:
                    return jsonify({
                        'success': True, 'status': 'unreachable',
                        'message': 'Could not reach your phone. Check signal and retry.',
                        'data': result
                    })
                return jsonify({
                    'success': True, 'status': 'pending',
                    'message': 'Waiting for confirmation...', 'data': result
                })
            
            elif result_code == '1032':
                return jsonify({
                    'success': True, 'status': 'cancelled',
                    'message': 'You cancelled. Click Retry.', 'data': result
                })
            
            elif result_code == '1019':
                return jsonify({
                    'success': True, 'status': 'expired',
                    'message': 'Expired. Click Retry.', 'data': result
                })
            
            elif result_code == '1':
                return jsonify({
                    'success': True, 'status': 'insufficient',
                    'message': 'Insufficient M-Pesa balance.', 'data': result
                })
            
            elif result_code == '2001':
                return jsonify({
                    'success': True, 'status': 'wrong_pin',
                    'message': 'Wrong M-Pesa PIN. Retry.', 'data': result
                })
            
            else:
                print(f"⚠️ Unknown code: {result_code}")
                return jsonify({
                    'success': True, 'status': 'pending',
                    'message': f'Processing...', 'data': result
                })
        
        return jsonify({'success': False, 'message': 'No response'})
        
    except Exception as e:
        print(f"❌ M-Pesa status error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@shop_bp.route('/mpesa/callback', methods=['POST'])
def mpesa_callback():
    """M-Pesa callback endpoint"""
    try:
        data = request.get_json()
        print(f"\n{'='*60}")
        print(f"📱 M-PESA CALLBACK")
        print(json.dumps(data, indent=2))
        print(f"{'='*60}\n")
        
        if not data:
            return jsonify({'ResultCode': 1, 'ResultDesc': 'No data'})
        
        stk_callback = data.get('Body', {}).get('stkCallback', {})
        result_code = stk_callback.get('ResultCode', '1')
        checkout_request_id = stk_callback.get('CheckoutRequestID', '')
        
        if result_code == 0 or result_code == '0':
            metadata = stk_callback.get('CallbackMetadata', {})
            items = metadata.get('Item', [])
            
            amount = mpesa_receipt = phone = None
            for item in items:
                name = item.get('Name')
                value = item.get('Value')
                if name == 'Amount': amount = value
                elif name == 'MpesaReceiptNumber': mpesa_receipt = value
                elif name == 'PhoneNumber': phone = value
            
            print(f"✅ PAYMENT CONFIRMED: {checkout_request_id} | KSh {amount} | {mpesa_receipt}")
        
        return jsonify({'ResultCode': 0, 'ResultDesc': 'Success'})
        
    except Exception as e:
        print(f"❌ Callback error: {e}")
        return jsonify({'ResultCode': 1, 'ResultDesc': str(e)})


# ============================================================
# PLACE MPESA ORDER
# ============================================================

@shop_bp.route('/place-order', methods=['POST'])
def place_order():
    """Place M-Pesa order - saves to admin"""
    try:
        cart = get_cart()
        if not cart:
            return jsonify({'success': False, 'message': 'Cart is empty'}), 400

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data received'}), 400

        print("=" * 60)
        print("📦 PLACE ORDER (M-PESA)")
        print("=" * 60)

        customer_name = data.get('customer_name') or data.get('name') or 'Web Customer'
        customer_email = data.get('customer_email') or data.get('email') or 'web@example.com'
        customer_phone = data.get('customer_phone') or data.get('phone') or 'N/A'
        customer_address = data.get('customer_address') or data.get('address') or 'Online Order'

        shipping = float(data.get('shipping', 0) or 0)
        subtotal = float(data.get('subtotal', 0) or 0)
        discount = float(data.get('discount', 0) or 0)
        tax_rate = 0.16
        payment_method = data.get('payment_method', 'mpesa')
        order_id = data.get('order_id', f'ORD-{datetime.now().strftime("%Y%m%d%H%M%S")}')

        if subtotal == 0:
            products = load_products()
            products = clean_products(products)
            bundles = load_bundles()
            for item_id, quantity in cart.items():
                for product in products:
                    if str(product.get('id')) == str(item_id):
                        subtotal += float(product.get('price', 0) or 0) * int(quantity)
                        break
                else:
                    for bundle in bundles:
                        if str(bundle.get('id')) == str(item_id):
                            subtotal += float(bundle.get('price', 0) or 0) * int(quantity)
                            break

        net_revenue = subtotal - discount
        tax = subtotal * tax_rate
        total_charged = net_revenue + tax + shipping

        products = load_products()
        products = clean_products(products)
        bundles = load_bundles()
        order_items = []

        for item_id, quantity in cart.items():
            if quantity <= 0:
                continue
            item_found = False
            for product in products:
                if str(product.get('id')) == str(item_id):
                    current_stock = int(product.get('stock', 0) or 0)
                    if current_stock < int(quantity):
                        return jsonify({
                            'success': False, 
                            'message': f'Not enough stock for {product.get("name")}. Available: {current_stock}'
                        }), 400
                    item_total = float(product.get('price', 0) or 0) * int(quantity)
                    order_items.append({
                        'product_id': str(item_id),
                        'name': str(product.get('name', 'Product')),
                        'price': float(product.get('price', 0) or 0),
                        'quantity': int(quantity),
                        'total': float(item_total),
                        'type': 'product',
                    })
                    item_found = True
                    new_stock = max(0, current_stock - int(quantity))
                    update_product_stock(item_id, new_stock)
                    break

            if not item_found:
                for bundle in bundles:
                    if str(bundle.get('id')) == str(item_id):
                        item_total = float(bundle.get('price', 0) or 0) * int(quantity)
                        order_items.append({
                            'product_id': str(item_id),
                            'name': str(bundle.get('name', 'Bundle')),
                            'price': float(bundle.get('price', 0) or 0),
                            'quantity': int(quantity),
                            'total': float(item_total),
                            'type': 'bundle',
                        })
                        break

        if not order_items:
            return jsonify({'success': False, 'message': 'No valid items in cart'}), 400

        order_data = {
            'order_id': str(order_id),
            'items': order_items,
            'subtotal': float(subtotal),
            'discount': float(discount),
            'tax': float(tax),
            'net_revenue': float(net_revenue),
            'shipping': float(shipping),
            'shipping_cost': float(data.get('shipping_cost', 0) or 0),
            'total_charged': float(total_charged),
            'status': str(data.get('status', 'pending')),
            'source': str(data.get('source', 'web')),
            'payment_method': str(payment_method),
            'created_at': datetime.utcnow().isoformat(),
            'customer_name': str(customer_name),
            'customer_email': str(customer_email),
            'customer_phone': str(customer_phone),
            'customer_address': str(customer_address),
            'customer': {
                'name': str(customer_name),
                'email': str(customer_email),
                'phone': str(customer_phone),
                'address': str(customer_address),
            },
            'delivery_notes': str(data.get('delivery_notes', '')),
        }

        if data.get('location'):
            order_data['location'] = data.get('location')

        try:
            response = requests.post(
                f"{Config.SUPABASE_URL}/rest/v1/orders",
                headers={
                    **Config.SUPABASE_HEADERS,
                    'Content-Type': 'application/json',
                    'Prefer': 'return=representation'
                },
                json=order_data,
                timeout=15,
            )

            if response.status_code in [200, 201, 204]:
                session['cart'] = {}
                session.modified = True

                import utils.data
                utils.data.orders_cache = []

                whatsapp_result = send_whatsapp_notification(order_data, customer_name, order_id, total_charged)
                whatsapp_url = whatsapp_result.get('whatsapp_url') if whatsapp_result.get('success') else None

                return jsonify({
                    'success': True,
                    'order_id': order_id,
                    'total': total_charged,
                    'net_revenue': net_revenue,
                    'shipping': shipping,
                    'message': 'Order placed successfully!',
                    'customer_name': customer_name,
                    'whatsapp_url': whatsapp_url,
                })
            else:
                return jsonify({
                    'success': False,
                    'message': f'Database error: {response.status_code}'
                }), 500

        except requests.exceptions.Timeout:
            return jsonify({'success': False, 'message': 'Request timeout.'}), 500
        except requests.exceptions.RequestException as e:
            return jsonify({'success': False, 'message': f'Network error: {str(e)}'}), 500

    except Exception as exc:
        print(f'Error placing order: {exc}')
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error: {str(exc)}'}), 500


# ============================================================
# PLACE WHATSAPP ORDER - Saves to admin AND opens WhatsApp
# ============================================================

@shop_bp.route('/place-order-whatsapp', methods=['POST'])
def place_order_whatsapp():
    """Save WhatsApp order to Supabase AND return WhatsApp URL"""
    try:
        cart = get_cart()
        if not cart:
            return jsonify({'success': False, 'message': 'Cart is empty'}), 400

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data received'}), 400

        print("=" * 60)
        print("💬 PLACE WHATSAPP ORDER")
        print("=" * 60)

        customer_name = data.get('customer_name') or data.get('name') or 'WhatsApp Customer'
        customer_email = data.get('customer_email') or data.get('email') or 'whatsapp@example.com'
        customer_phone = data.get('customer_phone') or data.get('phone') or 'N/A'
        customer_address = data.get('customer_address') or data.get('address') or 'WhatsApp Order'

        shipping = float(data.get('shipping', 0) or 0)
        subtotal = float(data.get('subtotal', 0) or 0)
        discount = float(data.get('discount', 0) or 0)
        tax_rate = 0.16
        order_id = data.get('order_id', f'WA-{datetime.now().strftime("%Y%m%d%H%M%S")}')

        if subtotal == 0:
            products = load_products()
            products = clean_products(products)
            bundles = load_bundles()
            for item_id, quantity in cart.items():
                for product in products:
                    if str(product.get('id')) == str(item_id):
                        subtotal += float(product.get('price', 0) or 0) * int(quantity)
                        break
                else:
                    for bundle in bundles:
                        if str(bundle.get('id')) == str(item_id):
                            subtotal += float(bundle.get('price', 0) or 0) * int(quantity)
                            break

        net_revenue = subtotal - discount
        tax = subtotal * tax_rate
        total_charged = net_revenue + tax + shipping

        products = load_products()
        products = clean_products(products)
        bundles = load_bundles()
        order_items = []

        for item_id, quantity in cart.items():
            if quantity <= 0:
                continue
            item_found = False
            for product in products:
                if str(product.get('id')) == str(item_id):
                    current_stock = int(product.get('stock', 0) or 0)
                    item_total = float(product.get('price', 0) or 0) * int(quantity)
                    order_items.append({
                        'product_id': str(item_id),
                        'name': str(product.get('name', 'Product')),
                        'price': float(product.get('price', 0) or 0),
                        'quantity': int(quantity),
                        'total': float(item_total),
                        'type': 'product',
                    })
                    item_found = True
                    new_stock = max(0, current_stock - int(quantity))
                    update_product_stock(item_id, new_stock)
                    break

            if not item_found:
                for bundle in bundles:
                    if str(bundle.get('id')) == str(item_id):
                        item_total = float(bundle.get('price', 0) or 0) * int(quantity)
                        order_items.append({
                            'product_id': str(item_id),
                            'name': str(bundle.get('name', 'Bundle')),
                            'price': float(bundle.get('price', 0) or 0),
                            'quantity': int(quantity),
                            'total': float(item_total),
                            'type': 'bundle',
                        })
                        break

        if not order_items:
            return jsonify({'success': False, 'message': 'No valid items in cart'}), 400

        order_data = {
            'order_id': str(order_id),
            'items': order_items,
            'subtotal': float(subtotal),
            'discount': float(discount),
            'tax': float(tax),
            'net_revenue': float(net_revenue),
            'shipping': float(shipping),
            'shipping_cost': float(data.get('shipping_cost', 0) or 0),
            'total_charged': float(total_charged),
            'status': 'pending',
            'source': 'whatsapp',
            'payment_method': 'whatsapp',
            'created_at': datetime.utcnow().isoformat(),
            'customer_name': str(customer_name),
            'customer_email': str(customer_email),
            'customer_phone': str(customer_phone),
            'customer_address': str(customer_address),
            'customer': {
                'name': str(customer_name),
                'email': str(customer_email),
                'phone': str(customer_phone),
                'address': str(customer_address),
            },
            'delivery_zone': str(data.get('delivery_zone', '')),
            'delivery_notes': str(data.get('delivery_notes', '')),
        }

        try:
            response = requests.post(
                f"{Config.SUPABASE_URL}/rest/v1/orders",
                headers={
                    **Config.SUPABASE_HEADERS,
                    'Content-Type': 'application/json',
                    'Prefer': 'return=representation'
                },
                json=order_data,
                timeout=15,
            )

            print(f"📥 Supabase: {response.status_code}")

            if response.status_code in [200, 201, 204]:
                print(f"✅ WhatsApp order saved: {order_id}")
                
                session['cart'] = {}
                session.modified = True

                import utils.data
                utils.data.orders_cache = []

                items_text = ""
                for item in order_items:
                    items_text += f"• {item['name']} x{item['quantity']} = KSh {item['total']:,.0f}\n"

                wa_message = f"""🛒 *NEW ORDER — ACACIA MINIMART*

📋 *Order ID:* {order_id}
👤 *Customer:* {customer_name}
📱 *Phone:* {customer_phone}
📍 *Address:* {customer_address}
🚚 *Zone:* {data.get('delivery_zone', 'N/A')}

📦 *Items:*
{items_text}

💰 *Summary:*
  • Subtotal: KSh {subtotal:,.0f}
  • Delivery: KSh {shipping:,.0f}
  • Total: KSh {total_charged:,.0f}

📝 *Notes:* {data.get('delivery_notes', 'None')}

✅ *Please confirm my order via WhatsApp.*"""

                encoded_msg = urllib.parse.quote(wa_message)
                whatsapp_url = f"https://wa.me/{Config.MPESA_BUSINESS_PHONE}?text={encoded_msg}"

                return jsonify({
                    'success': True,
                    'order_id': order_id,
                    'total': total_charged,
                    'message': 'Order saved! Opening WhatsApp...',
                    'whatsapp_url': whatsapp_url,
                })
            else:
                return jsonify({
                    'success': False,
                    'message': f'Database error: {response.status_code}'
                }), 500

        except Exception as e:
            print(f"❌ Save error: {e}")
            traceback.print_exc()
            return jsonify({'success': False, 'message': str(e)}), 500

    except Exception as exc:
        print(f'❌ WhatsApp order error: {exc}')
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error: {str(exc)}'}), 500


@shop_bp.route('/order-confirmation/<order_id>')
def order_confirmation(order_id):
    return render_template('confirmation.html', order_id=order_id)


@shop_bp.route('/clear-cart', methods=['POST'])
def clear_cart():
    session['cart'] = {}
    session.modified = True
    return jsonify({'success': True, 'message': 'Cart cleared'})


@shop_bp.route('/api/categories')
def api_categories():
    products = load_products()
    products = clean_products(products)
    categories = build_categories(products)
    
    all_categories = {
        'All': {'name': 'All', 'icon': 'fa-th-large', 'count': len(products)}
    }
    all_categories.update(categories)
    
    return jsonify(all_categories)


@shop_bp.route('/mpesa/test-auth')
def mpesa_test_auth():
    """Test M-Pesa authentication"""
    try:
        token = get_mpesa_access_token()
        shortcode = get_mpesa_shortcode()
        if token:
            return jsonify({
                'success': True,
                'message': 'Authentication works!',
                'token_preview': token[:30] + '...',
                'auth_url': Config.MPESA_AUTH_URL,
                'shortcode': shortcode,
                'transaction_type': 'CustomerBuyGoodsOnline',
                'till_number': Config.MPESA_TILL_NUMBER
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Authentication failed.',
                'auth_url': Config.MPESA_AUTH_URL
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
