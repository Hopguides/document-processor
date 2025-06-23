import os
import json
from flask import Blueprint, request, jsonify
from .project_manager import ProjectManager

projects_bp = Blueprint('projects', __name__)

# Globalna instanca project managerja
project_manager = ProjectManager()

@projects_bp.route('/list', methods=['GET'])
def list_projects():
    """Vrne seznam vseh projektov"""
    try:
        projects = project_manager.get_all_projects()
        return jsonify({
            "success": True,
            "projects": projects,
            "count": len(projects)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@projects_bp.route('/create', methods=['POST'])
def create_project():
    """Ustvari nov projekt"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        pinecone_index = data.get('pinecone_index', '').strip()
        system_prompt = data.get('system_prompt', '').strip()
        
        if not name:
            return jsonify({
                "success": False,
                "error": "Ime projekta je obvezno"
            }), 400
        
        if not pinecone_index:
            return jsonify({
                "success": False,
                "error": "Pinecone indeks je obvezen"
            }), 400
        
        project_id = project_manager.create_project(name, description, pinecone_index, system_prompt)
        
        if project_id:
            return jsonify({
                "success": True,
                "message": f"Projekt '{name}' je bil uspešno ustvarjen",
                "project_id": project_id
            })
        else:
            return jsonify({
                "success": False,
                "error": "Projekt s tem imenom že obstaja"
            }), 400
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@projects_bp.route('/<int:project_id>', methods=['GET'])
def get_project(project_id):
    """Vrne podatke o projektu"""
    try:
        project = project_manager.get_project_by_id(project_id)
        
        if not project:
            return jsonify({
                "success": False,
                "error": "Projekt ni najden"
            }), 404
        
        # Dodaj API ključe in Gemini ključe
        api_keys = project_manager.get_project_api_keys(project_id)
        gemini_keys = project_manager.get_project_gemini_keys(project_id)
        prompts = project_manager.get_project_prompts(project_id)
        
        project['api_keys'] = api_keys
        project['gemini_keys'] = gemini_keys
        project['prompts'] = prompts
        
        return jsonify({
            "success": True,
            "project": project
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@projects_bp.route('/<int:project_id>', methods=['PUT'])
def update_project(project_id):
    """Posodobi projekt"""
    try:
        data = request.get_json()
        name = data.get('name')
        description = data.get('description')
        pinecone_index = data.get('pinecone_index')
        system_prompt = data.get('system_prompt')
        is_active = data.get('is_active')
        
        success = project_manager.update_project(
            project_id, name, description, pinecone_index, system_prompt, is_active
        )
        
        if success:
            return jsonify({
                "success": True,
                "message": "Projekt je bil uspešno posodobljen"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Napaka pri posodabljanju projekta"
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@projects_bp.route('/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Izbriše projekt"""
    try:
        success = project_manager.delete_project(project_id)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Projekt je bil uspešno izbrisan"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Napaka pri brisanju projekta"
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@projects_bp.route('/<int:project_id>/api-keys', methods=['POST'])
def add_project_api_key(project_id):
    """Doda API ključ za projekt"""
    try:
        data = request.get_json()
        provider = data.get('provider', '').strip()
        api_key = data.get('api_key', '').strip()
        environment = data.get('environment', '').strip()
        notes = data.get('notes', '').strip()
        
        if not provider or not api_key:
            return jsonify({
                "success": False,
                "error": "Provider in API ključ sta obvezna"
            }), 400
        
        # Preveri, če projekt obstaja
        project = project_manager.get_project_by_id(project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": "Projekt ni najden"
            }), 404
        
        success = project_manager.add_project_api_key(project_id, provider, api_key, environment, notes)
        
        if success:
            return jsonify({
                "success": True,
                "message": f"API ključ za {provider} je bil uspešno dodan"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Napaka pri dodajanju API ključa"
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@projects_bp.route('/<int:project_id>/gemini-keys', methods=['POST'])
def add_project_gemini_key(project_id):
    """Doda Gemini ključ za projekt"""
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
        
        # Preveri, če projekt obstaja
        project = project_manager.get_project_by_id(project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": "Projekt ni najden"
            }), 404
        
        success = project_manager.add_project_gemini_key(project_id, name, api_key, notes)
        
        if success:
            return jsonify({
                "success": True,
                "message": f"Gemini ključ '{name}' je bil uspešno dodan"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Ključ s tem imenom že obstaja za ta projekt"
            }), 400
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@projects_bp.route('/<int:project_id>/prompts', methods=['POST'])
def set_project_prompt(project_id):
    """Nastavi prompt za projekt"""
    try:
        data = request.get_json()
        prompt_type = data.get('prompt_type', '').strip()
        prompt_content = data.get('prompt_content', '').strip()
        
        if not prompt_type or not prompt_content:
            return jsonify({
                "success": False,
                "error": "Tip prompta in vsebina sta obvezna"
            }), 400
        
        # Preveri, če projekt obstaja
        project = project_manager.get_project_by_id(project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": "Projekt ni najden"
            }), 404
        
        success = project_manager.set_project_prompt(project_id, prompt_type, prompt_content)
        
        if success:
            return jsonify({
                "success": True,
                "message": f"Prompt '{prompt_type}' je bil uspešno nastavljen"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Napaka pri nastavljanju prompta"
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@projects_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """Vrne statistike vseh projektov"""
    try:
        stats = project_manager.get_project_statistics()
        return jsonify({
            "success": True,
            "statistics": stats
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@projects_bp.route('/<int:project_id>/next-gemini-key', methods=['GET'])
def get_next_gemini_key(project_id):
    """Vrne naslednji dostopni Gemini ključ za projekt"""
    try:
        key = project_manager.get_next_available_gemini_key(project_id)
        
        if key:
            return jsonify({
                "success": True,
                "key": {
                    "id": key["id"],
                    "name": key["name"],
                    "api_key": key["api_key"],
                    "status": key["status"]
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": "Ni dostopnih Gemini ključev za ta projekt"
            }), 404
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

