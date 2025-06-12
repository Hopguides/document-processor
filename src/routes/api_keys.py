import os
import json
from flask import Blueprint, request, jsonify

api_keys_bp = Blueprint('api_keys', __name__)

# Path to store API keys
KEYS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'api_keys.json')

@api_keys_bp.route('/save-keys', methods=['POST'])
def save_api_keys():
    """Save API keys to a JSON file"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['openai_api_key', 'pinecone_api_key', 'pinecone_environment']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Save to file
        with open(KEYS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        
        return jsonify({'message': 'API keys saved successfully'}), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_keys_bp.route('/load-keys', methods=['GET'])
def load_api_keys():
    """Load API keys from JSON file"""
    try:
        if os.path.exists(KEYS_FILE):
            with open(KEYS_FILE, 'r') as f:
                data = json.load(f)
            # Don't return the actual keys for security, just indicate they exist
            return jsonify({
                'openai_api_key': '***' if data.get('openai_api_key') else '',
                'pinecone_api_key': '***' if data.get('pinecone_api_key') else '',
                'pinecone_environment': data.get('pinecone_environment', '')
            }), 200
        else:
            return jsonify({
                'openai_api_key': '',
                'pinecone_api_key': '',
                'pinecone_environment': ''
            }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_keys_bp.route('/process-document', methods=['POST'])
def process_document():
    """Process document and create embeddings"""
    try:
        from src.document_processor import DocumentProcessor
        
        data = request.get_json()
        content = data.get('content', '')
        
        if not content.strip():
            return jsonify({'error': 'Content is required'}), 400
        
        # Inicializiraj processor
        processor = DocumentProcessor(api_keys_file=KEYS_FILE)
        
        # Obdelaj dokument
        result = processor.process_document(
            content=content,
            metadata={
                "source": "web_upload",
                "timestamp": str(data.get('timestamp', '')),
                "type": "user_document"
            }
        )
        
        return jsonify(result), 200 if result.get('success') else 500
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

