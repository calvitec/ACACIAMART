from flask import Flask, jsonify, request, session
from flask_cors import CORS
from flask_session import Session
import requests
import os
import json

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'allison-electronics-secret-2026')

# Supabase Configuration (OLD DATABASE)
SUPABASE_URL = os.environ.get('NEXT_PUBLIC_SUPABASE_URL', 'https://hzqrdwerkgfmfaufabjr.supabase.co')
SUPABASE_KEY = os.environ.get('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY', 'sb_publishable_tnBOmCO7EFfIoXfNjEH_Tg_D7WX-zld')

SUPABASE_HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation'
}

@app.route('/')
def home():
    return jsonify({"message": "API is running!", "database": SUPABASE_URL})

@app.route('/api/products')
def get_products():
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/products?select=*",
            headers=SUPABASE_HEADERS
        )
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/credit_transactions')
def get_credit_transactions():
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/credit_transactions?select=*",
            headers=SUPABASE_HEADERS
        )
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
