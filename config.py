import os
from datetime import timedelta

class Config:
    SECRET_KEY = 'allison-electronics-secret-2026'
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
    # ✅ OLD WORKING DATABASE
    SUPABASE_URL = os.environ.get('NEXT_PUBLIC_SUPABASE_URL', 'https://haqqknmerdnfvwmsnath.supabase.co')
    SUPABASE_KEY = os.environ.get('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY', 'sb_publishable_fKWHaWSF-h5O8raSZzWMKA_udQTGyAA')
    
    print(f"🔑 Using Supabase URL: {SUPABASE_URL}")
    print(f"🔑 Using Supabase key: {SUPABASE_KEY[:30]}...")
    
    SUPABASE_HEADERS = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }

    DATA_FILE = os.path.join(PROJECT_ROOT, 'offline_data.json')

    # ============================================================
    # M-PESA CONFIGURATION (Sandbox)
    # ============================================================
    # ✅ USE ENVIRONMENT VARIABLES FOR PRODUCTION!
    MPESA_CONSUMER_KEY = os.environ.get('MPESA_CONSUMER_KEY', 'EwweXrZdaoB6Tgs8J9ROVe8lDL0OEIFml0rZDWzVTvG319D1')
    MPESA_CONSUMER_SECRET = os.environ.get('MPESA_CONSUMER_SECRET', 'QjhDN1Kablkw9NolMZDmIQ8ybS5gEcBdFg1iLGRqYlUzMczkVGzIAN8jsX9R5iL7')
    MPESA_PASSKEY = os.environ.get('MPESA_PASSKEY', 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919')
    MPESA_SHORTCODE = os.environ.get('MPESA_SHORTCODE', '174379')
    
    # ⚠️ IMPORTANT: Change this to your actual domain for production
    # For local testing, use ngrok or your local IP
    MPESA_CALLBACK_URL = os.environ.get('MPESA_CALLBACK_URL', 'https://your-domain.com/mpesa/callback')
    
    # For local testing with ngrok:
    # MPESA_CALLBACK_URL = os.environ.get('MPESA_CALLBACK_URL', 'https://your-ngrok-url.ngrok.io/mpesa/callback')
    
    print(f"📱 M-Pesa configured:")
    print(f"   Shortcode: {MPESA_SHORTCODE}")
    print(f"   Callback URL: {MPESA_CALLBACK_URL}")
