import base64
import re
from datetime import datetime

import requests
from flask import Blueprint, jsonify, request

mpesa_test_bp = Blueprint('mpesa_test', __name__)

# ============================================================
# HARDCODED CREDENTIALS — REMOVE AFTER DEBUGGING
# ============================================================
CONSUMER_KEY    = "drj3u3o4WAu9OLj5CxgeubDLT0ovutxLB1d7tpP0GfdaDXwU"
CONSUMER_SECRET = "qupk3DKgDPhPegrnGhwzA7vGyZvvFhnk6ktCs4GZKUAuQo8teCdearePphcWkzpA"
PASSKEY         = "217e9329cf5855e1f89757bbc467cdb9d4e6b42986d4857b96b7fa34eb48a376"

SHORTCODE       = "4671257"     # Paybill / Store number
TILL_NUMBER     = "8454832"     # Till (Buy Goods) number
CALLBACK_URL    = "https://acaciamart.shop/mpesa/callback"

AUTH_URL = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
STK_URL  = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"


def format_phone(phone):
    """Normalize to 254XXXXXXXXX."""
    cleaned = re.sub(r'\D', '', str(phone))
    if cleaned.startswith('254') and len(cleaned) == 12:
        return cleaned
    if cleaned.startswith('0') and len(cleaned) == 10:
        return '254' + cleaned[1:]
    if len(cleaned) == 9:
        return '254' + cleaned
    return None


def _get_token():
    r = requests.get(AUTH_URL, auth=(CONSUMER_KEY, CONSUMER_SECRET), timeout=30)
    try:
        return r.json().get('access_token'), r
    except Exception:
        return None, r


def _password():
    ts = datetime.now().strftime('%Y%m%d%H%M%S')
    pw = base64.b64encode((SHORTCODE + PASSKEY + ts).encode()).decode()
    return pw, ts


def _send_stk(payload, token):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(STK_URL, headers=headers, json=payload, timeout=30)
    try:
        j = r.json()
    except Exception:
        j = None
    return r, j


# ============================================================
# ROUTE 1 — PAYBILL (current behaviour)
# ============================================================
@mpesa_test_bp.route('/mpesa/test-stk', methods=['GET', 'POST'])
def test_stk():
    """Paybill STK push — TransactionType: CustomerPayBillOnline."""

    body = request.get_json(silent=True) if request.method == 'POST' and request.is_json else request.args
    phone  = body.get('phone', '0728922614')
    amount = int(body.get('amount', 1))

    formatted = format_phone(phone)
    if not formatted:
        return jsonify({'step': 'format_phone', 'error': f'Bad phone: {phone}'}), 400

    token, token_resp = _get_token()
    if not token:
        return jsonify({
            'step': 'token',
            'http_status': token_resp.status_code,
            'raw_response': token_resp.text,
        }), 500

    password, timestamp = _password()

    payload = {
        "BusinessShortCode": SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",   # ← Paybill
        "Amount": amount,
        "PartyA": formatted,
        "PartyB": SHORTCODE,                           # ← Paybill number
        "PhoneNumber": formatted,
        "CallBackURL": CALLBACK_URL,
        "AccountReference": "TEST",
        "TransactionDesc": "Test Paybill STK"
    }

    stk_resp, stk_json = _send_stk(payload, token)

    return jsonify({
        'mode': 'PAYBILL',
        'input': {'phone': phone, 'formatted_phone': formatted, 'amount': amount},
        'token': {'http_status': token_resp.status_code, 'token_preview': token[:20] + '...'},
        'password_inputs': {'shortcode': SHORTCODE, 'timestamp': timestamp},
        'stk_request': {
            'url': STK_URL,
            'payload': {**payload, 'Password': password[:20] + '...'},
        },
        'stk_response': {
            'http_status': stk_resp.status_code,
            'raw': stk_resp.text,
            'json': stk_json,
        }
    })


# ============================================================
# ROUTE 2 — BUY GOODS / TILL
# ============================================================
@mpesa_test_bp.route('/mpesa/test-stk-buygoods', methods=['GET', 'POST'])
def test_stk_buygoods():
    """Buy Goods STK push — TransactionType: CustomerBuyGoodsOnline."""

    body = request.get_json(silent=True) if request.method == 'POST' and request.is_json else request.args
    phone  = body.get('phone', '0728922614')
    amount = int(body.get('amount', 1))

    formatted = format_phone(phone)
    if not formatted:
        return jsonify({'step': 'format_phone', 'error': f'Bad phone: {phone}'}), 400

    token, token_resp = _get_token()
    if not token:
        return jsonify({
            'step': 'token',
            'http_status': token_resp.status_code,
            'raw_response': token_resp.text,
        }), 500

    password, timestamp = _password()

    payload = {
        "BusinessShortCode": SHORTCODE,                 # 4671257 (Store/HO)
        "Password": password,                           # built from 4671257 + passkey
        "Timestamp": timestamp,
        "TransactionType": "CustomerBuyGoodsOnline",    # ← Buy Goods
        "Amount": amount,
        "PartyA": formatted,
        "PartyB": TILL_NUMBER,                          # ← 8454832 (Till)
        "PhoneNumber": formatted,
        "CallBackURL": CALLBACK_URL,
        "AccountReference": "TEST",
        "TransactionDesc": "Test Buy Goods STK"
    }

    stk_resp, stk_json = _send_stk(payload, token)

    return jsonify({
        'mode': 'BUY_GOODS',
        'input': {'phone': phone, 'formatted_phone': formatted, 'amount': amount},
        'token': {'http_status': token_resp.status_code, 'token_preview': token[:20] + '...'},
        'password_inputs': {'shortcode': SHORTCODE, 'till': TILL_NUMBER, 'timestamp': timestamp},
        'stk_request': {
            'url': STK_URL,
            'payload': {**payload, 'Password': password[:20] + '...'},
        },
        'stk_response': {
            'http_status': stk_resp.status_code,
            'raw': stk_resp.text,
            'json': stk_json,
        }
    })
