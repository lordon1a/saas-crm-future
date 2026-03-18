from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
import os
import jwt
import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, static_folder='static', static_url_path='/static')

# CORS configuration from environment
cors_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:3000')
CORS(app, 
     origins=cors_origins.split(','),
     supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization'],
     methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])

# Database setup
import sys
sys.path.append('..')
from models import SuperAdmin, db

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', '').replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

@app.route('/setup-admin', methods=['POST'])
def setup_admin():
    """Create initial super admin (one-time setup)"""
    data = request.get_json()
    
    # Check if admin already exists
    if SuperAdmin.query.first():
        return jsonify({'error': 'Admin zaten mevcut'}), 403
    
    admin = SuperAdmin(
        email=data['email'],
        name=data['name'],
        password_hash=generate_password_hash(data['password']),
        is_active=True
    )
    db.session.add(admin)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Admin oluşturuldu'}), 201

@app.route('/auth/login', methods=['POST'])
def login():
    """Super admin login"""
    data = request.get_json()
    
    admin = SuperAdmin.query.filter_by(email=data['email']).first()
    if not admin or not check_password_hash(admin.password_hash, data['password']):
        return jsonify({'error': 'Geçersiz email veya şifre'}), 401
    
    token = jwt.encode(
        {
            'admin_id': admin.id,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=8)
        },
        os.environ.get('SUPER_ADMIN_JWT_SECRET'),
        algorithm='HS256'
    )
    
    return jsonify({'token': token, 'name': admin.name}), 200

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_file(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
