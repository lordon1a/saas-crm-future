import os
os.environ['FLASK_ENV'] = 'development'
os.environ['FLASK_DEBUG'] = '1'

from app import app

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
