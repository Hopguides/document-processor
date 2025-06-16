import os
import json
from flask import Blueprint, request, jsonify
from .gemini_key_manager import GeminiKeyManager

gemini_keys_bp = Blueprint('gemini_keys', __name__)

# Globalna instanca key managerja
key_manager = GeminiKeyManager()

@gemini_keys_bp.route('/list', methods=['GET'])
def list_keys():
    """Vrne seznam vseh Gemini ključev (brez API ključev)"""
    try:
        keys = key_manager.get_all_keys()
        return jsonify({
            "success": True,
            "keys": keys,
            "count": len(keys)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@gemini_keys_bp.route('/add', methods=['POST'])
def add_key():
    """Doda nov Gemini API ključ"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        api_key = data.get('api_key', '').strip()
        notes = data.get('notes', '').strip()
        
        if not name or not api_key:
            return jsonify({
                "success": False,
                "error": "Ime in API ključ sta obvezna"
            }), 400
        
        # Preveri format API ključa (Gemini ključi se začnejo z AIza)
        if not api_key.startswith('AIza'):
            return jsonify({
                "success": False,
                "error": "Neveljaven format Gemini API ključa (mora se začeti z 'AIza')"
            }), 400
        
        success = key_manager.add_key(name, api_key, notes)
        
        if success:
            return jsonify({
                "success": True,
                "message": f"Ključ '{name}' je bil uspešno dodan"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Ključ s tem imenom že obstaja"
            }), 400
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@gemini_keys_bp.route('/update/<int:key_id>', methods=['PUT'])
def update_key(key_id):
    """Posodobi obstoječi Gemini ključ"""
    try:
        data = request.get_json()
        name = data.get('name')
        api_key = data.get('api_key')
        status = data.get('status')
        notes = data.get('notes')
        
        # Preveri format API ključa, če je podan
        if api_key and not api_key.startswith('AIza'):
            return jsonify({
                "success": False,
                "error": "Neveljaven format Gemini API ključa (mora se začeti z 'AIza')"
            }), 400
        
        success = key_manager.update_key(key_id, name, api_key, status, notes)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Ključ je bil uspešno posodobljen"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Napaka pri posodabljanju ključa"
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@gemini_keys_bp.route('/delete/<int:key_id>', methods=['DELETE'])
def delete_key(key_id):
    """Izbriše Gemini ključ"""
    try:
        success = key_manager.delete_key(key_id)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Ključ je bil uspešno izbrisan"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Napaka pri brisanju ključa"
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@gemini_keys_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """Vrne statistike vseh Gemini ključev"""
    try:
        stats = key_manager.get_statistics()
        return jsonify({
            "success": True,
            "statistics": stats
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@gemini_keys_bp.route('/next-available', methods=['GET'])
def get_next_available():
    """Vrne naslednji dostopni ključ za uporabo"""
    try:
        key = key_manager.get_next_available_key()
        
        if key:
            return jsonify({
                "success": True,
                "key": {
                    "id": key["id"],
                    "name": key["name"],
                    "status": key["status"]
                    # API ključ ne bo vrnjen iz varnostnih razlogov
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": "Ni dostopnih ključev"
            }), 404
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@gemini_keys_bp.route('/reset-rate-limits', methods=['POST'])
def reset_rate_limits():
    """Resetira vse rate limite (za testiranje)"""
    try:
        affected = key_manager.reset_all_rate_limits()
        return jsonify({
            "success": True,
            "message": f"Resetirano {affected} ključev",
            "affected_keys": affected
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@gemini_keys_bp.route('/test/<int:key_id>', methods=['POST'])
def test_key(key_id):
    """Testira Gemini API ključ"""
    try:
        key_data = key_manager.get_key_by_id(key_id)
        
        if not key_data:
            return jsonify({
                "success": False,
                "error": "Ključ ni najden"
            }), 404
        
        # Testni klic na Gemini API
        import requests
        
        headers = {
            'Content-Type': 'application/json',
        }
        
        test_data = {
            "contents": [{
                "parts": [{"text": "Hello, this is a test message."}]
            }]
        }
        
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={key_data['api_key']}"
        
        response = requests.post(api_url, headers=headers, json=test_data, timeout=10)
        
        if response.status_code == 200:
            key_manager.update_key_usage(key_id, success=True)
            return jsonify({
                "success": True,
                "message": "Ključ deluje pravilno",
                "status_code": response.status_code
            })
        elif response.status_code == 429:
            key_manager.update_key_usage(key_id, success=False, error_type="rate_limit")
            return jsonify({
                "success": False,
                "error": "Rate limit dosežen",
                "status_code": response.status_code
            }), 429
        else:
            key_manager.update_key_usage(key_id, success=False, error_type="api_error")
            return jsonify({
                "success": False,
                "error": f"API napaka: {response.status_code}",
                "status_code": response.status_code,
                "response": response.text[:200]
            }), response.status_code
            
    except requests.exceptions.Timeout:
        return jsonify({
            "success": False,
            "error": "Timeout pri testiranju ključa"
        }), 408
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

