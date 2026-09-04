from flask import Flask, session
from admin import admin_bp

app = Flask(__name__)
app.secret_key = 'your-secret-key-2026'

# Register admin blueprint
app.register_blueprint(admin_bp)

@app.route('/')
def home():
    return redirect('/admin')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
