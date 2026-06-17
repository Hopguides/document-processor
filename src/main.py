import os
import sys
# DON'T CHANGE THIS PATH
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, send_from_directory
from flask_cors import CORS

from src.routes.user import user_bp
from src.routes.api_keys import api_keys_bp
from src.routes.rag import rag_bp

app = Flask(__name__)
CORS(app)

# Register blueprints
app.register_blueprint(user_bp, url_prefix='/api/user')
app.register_blueprint(api_keys_bp, url_prefix='/api')
app.register_blueprint(rag_bp, url_prefix='/api/rag')

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/chat')
def chat():
    return send_from_directory('static', 'chat.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)

