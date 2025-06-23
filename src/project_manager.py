import sqlite3
import os
import json
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class Project:
    id: int
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    pinecone_index: str
    system_prompt: str
    is_active: bool

class ProjectManager:
    """
    Manager za upravljanje projektov z ločenimi API ključi, bazami znanja in konfiguracijami
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), 'projects.db')
        
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Inicializira SQLite bazo za shranjevanje projektov in njihovih konfiguracij"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabela projektov
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pinecone_index TEXT NOT NULL,
                system_prompt TEXT DEFAULT '',
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Tabela API ključev za projekte
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                provider TEXT NOT NULL,
                api_key TEXT NOT NULL,
                environment TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
                UNIQUE(project_id, provider)
            )
        ''')
        
        # Tabela Gemini ključev za projekte (za rotacijo)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_gemini_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                api_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP,
                total_requests INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                rate_limit_reset TIMESTAMP,
                notes TEXT DEFAULT '',
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
                UNIQUE(project_id, name)
            )
        ''')
        
        # Tabela prompt konfiguracij
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                prompt_type TEXT NOT NULL,
                prompt_content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
                UNIQUE(project_id, prompt_type)
            )
        ''')
        
        # Indeksi za boljšo performanco
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_projects_active ON projects(is_active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_keys_project ON project_api_keys(project_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gemini_keys_project ON project_gemini_keys(project_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_prompts_project ON project_prompts(project_id)')
        
        conn.commit()
        conn.close()
    
    def create_project(self, name: str, description: str = "", pinecone_index: str = "", 
                      system_prompt: str = "") -> Optional[int]:
        """Ustvari nov projekt"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO projects (name, description, pinecone_index, system_prompt)
                VALUES (?, ?, ?, ?)
            ''', (name, description, pinecone_index, system_prompt))
            
            project_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return project_id
        except sqlite3.IntegrityError:
            return None  # Ime že obstaja
        except Exception as e:
            print(f"Napaka pri ustvarjanju projekta: {e}")
            return None
    
    def get_all_projects(self) -> List[Dict]:
        """Vrne vse projekte"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, description, created_at, updated_at, 
                   pinecone_index, system_prompt, is_active
            FROM projects
            ORDER BY created_at DESC
        ''')
        
        projects = []
        for row in cursor.fetchall():
            projects.append({
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'created_at': row[3],
                'updated_at': row[4],
                'pinecone_index': row[5],
                'system_prompt': row[6],
                'is_active': bool(row[7])
            })
        
        conn.close()
        return projects
    
    def get_project_by_id(self, project_id: int) -> Optional[Dict]:
        """Vrne projekt po ID-ju"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, description, created_at, updated_at,
                   pinecone_index, system_prompt, is_active
            FROM projects
            WHERE id = ?
        ''', (project_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'created_at': row[3],
                'updated_at': row[4],
                'pinecone_index': row[5],
                'system_prompt': row[6],
                'is_active': bool(row[7])
            }
        return None
    
    def update_project(self, project_id: int, name: str = None, description: str = None,
                      pinecone_index: str = None, system_prompt: str = None, 
                      is_active: bool = None) -> bool:
        """Posodobi projekt"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            updates = []
            params = []
            
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if pinecone_index is not None:
                updates.append("pinecone_index = ?")
                params.append(pinecone_index)
            if system_prompt is not None:
                updates.append("system_prompt = ?")
                params.append(system_prompt)
            if is_active is not None:
                updates.append("is_active = ?")
                params.append(is_active)
            
            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(project_id)
                query = f"UPDATE projects SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                conn.commit()
            
            conn.close()
            return True
        except Exception as e:
            print(f"Napaka pri posodabljanju projekta: {e}")
            return False
    
    def delete_project(self, project_id: int) -> bool:
        """Izbriše projekt in vse povezane podatke"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM projects WHERE id = ?', (project_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Napaka pri brisanju projekta: {e}")
            return False
    
    def add_project_api_key(self, project_id: int, provider: str, api_key: str, 
                           environment: str = "", notes: str = "") -> bool:
        """Doda API ključ za projekt"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO project_api_keys 
                (project_id, provider, api_key, environment, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (project_id, provider, api_key, environment, notes))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Napaka pri dodajanju API ključa: {e}")
            return False
    
    def get_project_api_keys(self, project_id: int) -> Dict[str, Dict]:
        """Vrne vse API ključe za projekt"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT provider, api_key, environment, notes, created_at
            FROM project_api_keys
            WHERE project_id = ?
        ''', (project_id,))
        
        keys = {}
        for row in cursor.fetchall():
            keys[row[0]] = {
                'api_key': row[1],
                'environment': row[2],
                'notes': row[3],
                'created_at': row[4]
            }
        
        conn.close()
        return keys
    
    def add_project_gemini_key(self, project_id: int, name: str, api_key: str, 
                              notes: str = "") -> bool:
        """Doda Gemini ključ za projekt (za rotacijo)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO project_gemini_keys 
                (project_id, name, api_key, notes)
                VALUES (?, ?, ?, ?)
            ''', (project_id, name, api_key, notes))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False  # Ime že obstaja za ta projekt
        except Exception as e:
            print(f"Napaka pri dodajanju Gemini ključa: {e}")
            return False
    
    def get_project_gemini_keys(self, project_id: int) -> List[Dict]:
        """Vrne vse Gemini ključe za projekt"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, status, created_at, last_used, 
                   total_requests, error_count, rate_limit_reset, notes
            FROM project_gemini_keys
            WHERE project_id = ?
            ORDER BY created_at DESC
        ''', (project_id,))
        
        keys = []
        for row in cursor.fetchall():
            keys.append({
                'id': row[0],
                'name': row[1],
                'status': row[2],
                'created_at': row[3],
                'last_used': row[4],
                'total_requests': row[5],
                'error_count': row[6],
                'rate_limit_reset': row[7],
                'notes': row[8]
            })
        
        conn.close()
        return keys
    
    def get_next_available_gemini_key(self, project_id: int) -> Optional[Dict]:
        """Vrne naslednji dostopni Gemini ključ za projekt"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, api_key, status, last_used, rate_limit_reset
            FROM project_gemini_keys
            WHERE project_id = ? 
            AND status = 'active' 
            AND (rate_limit_reset IS NULL OR rate_limit_reset < datetime('now'))
            ORDER BY last_used ASC NULLS FIRST
            LIMIT 1
        ''', (project_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'name': row[1],
                'api_key': row[2],
                'status': row[3],
                'last_used': row[4],
                'rate_limit_reset': row[5]
            }
        return None
    
    def set_project_prompt(self, project_id: int, prompt_type: str, prompt_content: str) -> bool:
        """Nastavi prompt za projekt"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO project_prompts 
                (project_id, prompt_type, prompt_content, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (project_id, prompt_type, prompt_content))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Napaka pri nastavljanju prompta: {e}")
            return False
    
    def get_project_prompts(self, project_id: int) -> Dict[str, str]:
        """Vrne vse prompte za projekt"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT prompt_type, prompt_content
            FROM project_prompts
            WHERE project_id = ?
        ''', (project_id,))
        
        prompts = {}
        for row in cursor.fetchall():
            prompts[row[0]] = row[1]
        
        conn.close()
        return prompts
    
    def get_project_statistics(self) -> Dict:
        """Vrne statistike vseh projektov"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                COUNT(*) as total_projects,
                SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_projects,
                COUNT(DISTINCT pak.project_id) as projects_with_api_keys,
                COUNT(DISTINCT pgk.project_id) as projects_with_gemini_keys
            FROM projects p
            LEFT JOIN project_api_keys pak ON p.id = pak.project_id
            LEFT JOIN project_gemini_keys pgk ON p.id = pgk.project_id
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        return {
            'total_projects': row[0] or 0,
            'active_projects': row[1] or 0,
            'projects_with_api_keys': row[2] or 0,
            'projects_with_gemini_keys': row[3] or 0
        }

