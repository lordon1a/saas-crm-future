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
from flask_sqlalchemy import SQLAlchemy

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', '').replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class SuperAdmin(db.Model):
    __tablename__ = 'super_admins'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

with app.app_context():
    db.create_all()

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

@app.route('/tenants', methods=['GET'])
def get_tenants():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Token gerekli'}), 401
    
    try:
        token = auth_header.split(' ')[1]
        jwt.decode(token, os.environ.get('SUPER_ADMIN_JWT_SECRET'), algorithms=['HS256'])
    except:
        return jsonify({'error': 'Geçersiz token'}), 401
    
    from sqlalchemy import create_engine, text
    engine = create_engine(os.environ.get('DATABASE_URL', '').replace('postgres://', 'postgresql://', 1))
    
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT w.id,
                   w.name as company_name,
                   w.created_at,
                   COUNT(DISTINCT u.id) as user_count,
                   COUNT(DISTINCT c.id) as customer_count,
                   COUNT(DISTINCT m.id) as message_count
            FROM workspaces w
            LEFT JOIN users u ON u.workspace_id = w.id
            LEFT JOIN customers c ON c.workspace_id = w.id
            LEFT JOIN messages m ON m.conversation_id IN (
                SELECT id FROM conversations 
                WHERE workspace_id = w.id
                AND created_at > NOW() - INTERVAL '30 days'
            )
            GROUP BY w.id, w.name, w.created_at
            ORDER BY w.created_at DESC
        """)).fetchall()
        
        tenants = []
        for row in rows:
            tenants.append({
                'id': row[0],
                'company_name': row[1],
                'created_at': str(row[2]),
                'whatsapp_connected': False,
                'stats': {
                    'users': row[3],
                    'customers': row[4],
                    'messages_30d': row[5]
                }
            })
        
        return jsonify({'tenants': tenants}), 200

@app.route('/analytics/overview', methods=['GET'])
def get_analytics():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Token gerekli'}), 401
    
    try:
        token = auth_header.split(' ')[1]
        jwt.decode(token, os.environ.get('SUPER_ADMIN_JWT_SECRET'), algorithms=['HS256'])
    except:
        return jsonify({'error': 'Geçersiz token'}), 401
    
    from sqlalchemy import create_engine, text
    engine = create_engine(os.environ.get('DATABASE_URL', '').replace('postgres://', 'postgresql://', 1))
    
    with engine.connect() as conn:
        stats = conn.execute(text("""
            SELECT
                (SELECT COUNT(*) FROM workspaces) as total_workspaces,
                0 as dau,
                0 as mau,
                (SELECT COUNT(*) FROM messages WHERE created_at > NOW() - INTERVAL '30 days') as messages_30d
        """)).fetchone()
        
        return jsonify({
            'platform': {
                'total_workspaces': stats[0]
            },
            'activity': {
                'dau': stats[1],
                'mau': stats[2],
                'messages_30d': stats[3]
            }
        }), 200

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/dashboard')
def dashboard():
    return send_from_directory('.', 'dashboard.html')

@app.route('/<path:path>')
def serve_file(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
