import os
from datetime import timedelta

class Config:
    # ============================================================
    # FLASK
    # ============================================================
    SECRET_KEY = os.environ.get('SECRET_KEY')
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

    # ============================================================
    # SUPABASE
    # ============================================================
    SUPABASE_URL = os.environ.get('SUPABASE_URL')
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

    SUPABASE_HEADERS = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }

    DATA_FILE = os.path.join(PROJECT_ROOT, 'offline_data.json')

    # ============================================================
    # M-PESA — Acacia Minimart (Merchant Till / Buy Goods)
    # ============================================================
    MPESA_BUSINESS_NAME = os.environ.get('MPESA_BUSINESS_NAME', 'Acacia Minimart')
    MPESA_SHORTCODE = os.environ.get('MPESA_SHORTCODE')
    MPESA_TILL_NUMBER = os.environ.get('MPESA_TILL_NUMBER')
    MPESA_TRANSACTION_TYPE = os.environ.get('MPESA_TRANSACTION_TYPE', 'CustomerBuyGoodsOnline')
    MPESA_USERNAME = os.environ.get('MPESA_USERNAME', '')
    MPESA_BUSINESS_PHONE = os.environ.get('MPESA_BUSINESS_PHONE', '')

    MPESA_CONSUMER_KEY = os.environ.get('MPESA_CONSUMER_KEY')
    MPESA_CONSUMER_SECRET = os.environ.get('MPESA_CONSUMER_SECRET')
    MPESA_PASSKEY = os.environ.get('MPESA_PASSKEY')

    MPESA_BASE_URL = 'https://api.safaricom.co.ke'
    MPESA_AUTH_URL = 'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
    MPESA_STK_PUSH_URL = 'https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
    MPESA_QUERY_URL = 'https://api.safaricom.co.ke/mpesa/stkpushquery/v1/query'

    MPESA_CALLBACK_URL = os.environ.get('MPESA_CALLBACK_URL')

    # ============================================================
    # FAIL-FAST: refuse to start if critical secrets are missing
    # ============================================================
    _REQUIRED = [
        'SECRET_KEY',
        'SUPABASE_URL',
        'SUPABASE_KEY',
        'MPESA_SHORTCODE',
        'MPESA_TILL_NUMBER',
        'MPESA_CONSUMER_KEY',
        'MPESA_CONSUMER_SECRET',
        'MPESA_PASSKEY',
        'MPESA_CALLBACK_URL',
    ]
    _missing = [k for k in _REQUIRED if not os.environ.get(k)]
    if _missing:
        raise RuntimeError(
            "❌ Missing required environment variables: "
            + ", ".join(_missing)
            + ". Set them in .env locally, or in Vercel → Settings → Environment Variables."
        )

    # ============================================================
    # Startup log (no secret values shown)
    # ============================================================
    print("=" * 60)
    print("🏪 ACACIAMART — M-PESA PRODUCTION (BUY GOODS / TILL)")
    print("=" * 60)
    print(f"📱 Business:      {MPESA_BUSINESS_NAME}")
    print(f"📱 Shortcode:     {MPESA_SHORTCODE}")
    print(f"📱 Till Number:   {MPESA_TILL_NUMBER}")
    print(f"📱 Txn Type:      {MPESA_TRANSACTION_TYPE}")
    print(f"📱 Callback:      {MPESA_CALLBACK_URL}")
    print(f"🗄️  Supabase URL: {SUPABASE_URL}")
    print(f"🔑 SECRET_KEY:    {'✓ set (' + str(len(SECRET_KEY)) + ' chars)' if SECRET_KEY else '✗ MISSING'}")
    print(f"🔑 MPESA keys:    {'✓ set' if MPESA_CONSUMER_KEY and MPESA_CONSUMER_SECRET else '✗ MISSING'}")
    print("=" * 60)
