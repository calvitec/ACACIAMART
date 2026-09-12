import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'allison-electronics-secret-2026')
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    IS_VERCEL = 'VERCEL' in os.environ or 'NOW' in os.environ
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

    if IS_VERCEL:
        UPLOAD_FOLDER = '/tmp/static/uploads'
        STATIC_FOLDER = '/tmp/static'
    else:
        UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'static', 'uploads')
        STATIC_FOLDER = os.path.join(PROJECT_ROOT, 'static')

    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024

    # ===== SUPABASE CONFIGURATION =====
    SUPABASE_URL = os.environ.get(
        'NEXT_PUBLIC_SUPABASE_URL',
        'https://hzqrdwerkgfmfaufabjr.supabase.co'
    )
    SUPABASE_KEY = os.environ.get(
        'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY',
        'sb_publishable_tnBOmCO7EFfIoXfNjEH_Tg_D7WX-zld'
    )

    SUPABASE_HEADERS = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }

    DATA_FILE = os.path.join(PROJECT_ROOT, 'offline_data.json')

    # ============================================================
    # M-PESA PRODUCTION CONFIGURATION - ACACIA MINIMART
    # Merchant Till (Buy Goods) — NOT PayBill
    # ============================================================
    MPESA_BUSINESS_NAME = "Acacia Minimart"

    # BusinessShortCode = HO/store number that went live on Daraja.
    # Used for: OAuth password, STK Push payload's BusinessShortCode, status queries.
    MPESA_SHORTCODE = "4671257"

    # PartyB = actual Till number customers pay to.
    # Used for: STK Push payload's PartyB only.
    MPESA_TILL_NUMBER = "8454832"

    # ✅ Buy Goods — required because this is a Merchant Till, not a PayBill.
    MPESA_TRANSACTION_TYPE = "CustomerBuyGoodsOnline"

    MPESA_USERNAME = "VICHAMINYA"
    MPESA_BUSINESS_PHONE = "254728922614"

    MPESA_CONSUMER_KEY = os.environ.get('MPESA_CONSUMER_KEY', 'drj3u3o4WAu9OLj5CxgeubDLT0ovutxLB1d7tpP0GfdaDXwU')
    MPESA_CONSUMER_SECRET = os.environ.get('MPESA_CONSUMER_SECRET', 'qupk3DKgDPhPegrnGhwzA7vGyZvvFhnk6ktCs4GZKUAuQo8teCdearePphcWkzpA')
    MPESA_PASSKEY = os.environ.get('MPESA_PASSKEY', '217e9329cf5855e1f89757bbc467cdb9d4e6b42986d4857b96b7fa34eb48a376')

    MPESA_BASE_URL = 'https://api.safaricom.co.ke'
    MPESA_AUTH_URL = 'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
    MPESA_STK_PUSH_URL = 'https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
    MPESA_QUERY_URL = 'https://api.safaricom.co.ke/mpesa/stkpushquery/v1/query'

    MPESA_CALLBACK_URL = os.environ.get(
        'MPESA_CALLBACK_URL',
        'https://acaciamart.shop/mpesa/callback'
    )

    print("=" * 60)
    print("🏪 ACACIA MINIMART - M-PESA PRODUCTION (BUY GOODS / TILL)")
    print("=" * 60)
    print(f"📱 Business: {MPESA_BUSINESS_NAME}")
    print(f"📱 BusinessShortCode (HO/Store): {MPESA_SHORTCODE}")
    print(f"📱 Till Number (PartyB): {MPESA_TILL_NUMBER}")
    print(f"📱 Transaction Type: {MPESA_TRANSACTION_TYPE}")
    print(f"📱 Callback: {MPESA_CALLBACK_URL}")
    print(f"📱 Base URL: {MPESA_BASE_URL}")
    print(f"🗄️  Supabase URL: {SUPABASE_URL}")
    print(f"🔑 Consumer Key: {MPESA_CONSUMER_KEY[:15]}...")
    print(f"🔑 Passkey: {MPESA_PASSKEY[:15]}...")
    print("=" * 60)
