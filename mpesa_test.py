import os
import base64
import json
import re
from datetime import datetime

import requests
from flask import Blueprint, jsonify, request

mpesa_test_bp = Blueprint('mpesa_test', __name__)

# ============================================================
# HARDCODE EVERYTHING HERE — no config imports, no env vars
# ============================================================
CONSUMER_KEY    = "drj3u3o4WAu9OLj5CxgeubDLT0ovutxLB1d7tpP0GfdaDXwU"
CONSUMER_SECRET = "qupk3DKgDPhPegrnGhwzA7vGyZvvFhnk6ktCs4GZKUAuQo8teCdearePphcWkzpA"
PASSKEY         = "217e9329cf5855e1f89757bbc467cdb9d4e6b42986d4857b96b7fa34eb48a376"
SHORTCODE       = "4671257"
CALLBACK_URL    = "https://acaciamart.shop/mpesa/callback"

AUTH_URL    = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
STK_URL     = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"


def format_phone(phone):
    cleaned = re.sub(r'\D', '', str(phone))
    if cleaned.startswith('254') and len(cleaned) == 12:
        return cleaned
    if cleaned.startswith('0') and len(cleaned) == 10:
        return '254' + cleaned[1:]
    if len(cleaned) == 9:
        return '254' + cleaned
    return None


@mpesa_test_bp.route('/mpesa/test-stk', methods=['GET', 'POST'])
def test_stk():
    """Minimal STK push. No DB, no session, no callback store."""

    # Accept phone from query string or JSON body
    if request.method == 'POST' and request.is_json:
        body = request.get_json()
    else:
        body = request.args

    phone  = body.get('phone', '0728922614')
    amount = int(body.get('amount', 1))

    formatted = format_phone(phone)
    if not formatted:
        return jsonify({'step': 'format_phone', 'error': f'Bad phone: {phone}'}), 400

    # ---------- STEP 1: TOKEN ----------
    token_resp = requests.get(AUTH_URL, auth=(CONSUMER_KEY, CONSUMER_SECRET), timeout=30)
    token_raw = token_resp.text
    try:
        token = token_resp.json().get('access_token')
    except Exception:
        token = None

    if not token:
        return jsonify({
            'step': 'token',
            'http_status': token_resp.status_code,
            'raw_response': token_raw,
        }), 500

    # ---------- STEP 2: PASSWORD ----------
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    password  = base64.b64encode(
        (SHORTCODE + PASSKEY + timestamp).encode()
    ).decode()

    # ---------- STEP 3: STK PUSH ----------
    payload = {
        "BusinessShortCode": SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": formatted,
        "PartyB": SHORTCODE,
        "PhoneNumber": formatted,
        "CallBackURL": CALLBACK_URL,
        "AccountReference": "TEST",
        "TransactionDesc": "Test STK"
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    stk_resp = requests.post(STK_URL, headers=headers, json=payload, timeout=30)
    stk_raw  = stk_resp.text

    try:
        stk_json = stk_resp.json()
    except Exception:
        stk_json = None

    # ---------- STEP 4: RETURN EVERYTHING ----------
    return jsonify({
        'input': {
            'phone': phone,
            'formatted_phone': formatted,
            'amount': amount,
        },
        'token': {
            'http_status': token_resp.status_code,
            'token_preview': token[:20] + '...' if token else None,
        },
        'password_inputs': {
            'shortcode': SHORTCODE,
            'timestamp': timestamp,
            'password_preview': password[:20] + '...',
        },
        'stk_request': {
            'url': STK_URL,
            'payload': {**payload, 'Password': password[:20] + '...'},
        },
        'stk_response': {
            'http_status': stk_resp.status_code,
            'raw': stk_raw,
            'json': stk_json,
        }
    })
