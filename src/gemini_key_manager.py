import sqlite3
import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class KeyStatus(Enum):
    ACTIVE = "active"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    DISABLED = "disabled"

@dataclass
class GeminiKey:
    id: int
    name: str
    api_key: str
    status: KeyStatus
    created_at: datetime
    last_used: Optional[datetime]
    total_requests: int
    error_count: int
    rate_limit_reset: Optional[datetime]
    notes: str

class GeminiKeyManager:
    """
    Manager za upravljanje več Gemini API ključev z rotacijo in load balancing
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Uporabi relativno pot glede na lokacijo skripte
            db_path = os.path.join(os.path.dirname(__file__), '..', 'gemini_keys.db')
        
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Inicializira SQLite bazo za shranjevanje Gemini ključev"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gemini_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                api_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP,
                total_requests INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                rate_limit_reset TIMESTAMP,
                notes TEXT DEFAULT ''
            )
        ''')
        
        # Dodaj indekse za boljšo performanco
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON gemini_keys(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_last_used ON gemini_keys(last_used)')
        
        conn.commit()
        conn.close()
    
    def add_key(self, name: str, api_key: str, notes: str = "") -> bool:
        """Doda nov Gemini API ključ"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO gemini_keys (name, api_key, notes)
                VALUES (?, ?, ?)
            ''', (name, api_key, notes))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False  # Ime že obstaja
        except Exception as e:
            print(f"Napaka pri dodajanju ključa: {e}")
            return False
    
    def get_all_keys(self) -> List[Dict]:
        """Vrne vse ključe (brez API ključev za varnost)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, status, created_at, last_used, 
                   total_requests, error_count, rate_limit_reset, notes
            FROM gemini_keys
            ORDER BY created_at DESC
        ''')
        
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
                'notes': row[8],
                'api_key_preview': '***' + (self.get_key_by_id(row[0])['api_key'][-4:] if self.get_key_by_id(row[0]) else '****')
            })
        
        conn.close()
        return keys
    
    def get_key_by_id(self, key_id: int) -> Optional[Dict]:
        """Vrne ključ po ID-ju (z API ključem)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, api_key, status, created_at, last_used,
                   total_requests, error_count, rate_limit_reset, notes
            FROM gemini_keys
            WHERE id = ?
        ''', (key_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'name': row[1],
                'api_key': row[2],
                'status': row[3],
                'created_at': row[4],
                'last_used': row[5],
                'total_requests': row[6],
                'error_count': row[7],
                'rate_limit_reset': row[8],
                'notes': row[9]
            }
        return None
    
    def get_next_available_key(self) -> Optional[Dict]:
        """
        Vrne naslednji dostopni ključ za uporabo
        Logika: round-robin med aktivnimi ključi, izogiba se rate-limited ključem
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Najprej poskusi najti ključe, ki niso rate limited
        cursor.execute('''
            SELECT id, name, api_key, status, last_used, rate_limit_reset
            FROM gemini_keys
            WHERE status = 'active' 
            AND (rate_limit_reset IS NULL OR rate_limit_reset < datetime('now'))
            ORDER BY last_used ASC NULLS FIRST
            LIMIT 1
        ''')
        
        row = cursor.fetchone()
        
        if not row:
            # Če ni dostopnih ključev, preveri če se je kateri reset
            cursor.execute('''
                UPDATE gemini_keys 
                SET status = 'active', rate_limit_reset = NULL
                WHERE status = 'rate_limited' 
                AND rate_limit_reset < datetime('now')
            ''')
            conn.commit()
            
            # Poskusi znova
            cursor.execute('''
                SELECT id, name, api_key, status, last_used, rate_limit_reset
                FROM gemini_keys
                WHERE status = 'active'
                ORDER BY last_used ASC NULLS FIRST
                LIMIT 1
            ''')
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
    
    def update_key_usage(self, key_id: int, success: bool = True, error_type: str = None):
        """Posodobi statistike uporabe ključa"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if success:
            cursor.execute('''
                UPDATE gemini_keys 
                SET last_used = datetime('now'),
                    total_requests = total_requests + 1
                WHERE id = ?
            ''', (key_id,))
        else:
            # Obravnava napak
            if error_type == "rate_limit":
                # Rate limit - nastavi reset čez 1 minuto
                cursor.execute('''
                    UPDATE gemini_keys 
                    SET status = 'rate_limited',
                        error_count = error_count + 1,
                        rate_limit_reset = datetime('now', '+1 minute')
                    WHERE id = ?
                ''', (key_id,))
            else:
                # Druga napaka
                cursor.execute('''
                    UPDATE gemini_keys 
                    SET error_count = error_count + 1,
                        last_used = datetime('now')
                    WHERE id = ?
                ''', (key_id,))
                
                # Če je preveč napak, onemogoči ključ
                cursor.execute('''
                    UPDATE gemini_keys 
                    SET status = 'error'
                    WHERE id = ? AND error_count >= 5
                ''', (key_id,))
        
        conn.commit()
        conn.close()
    
    def update_key(self, key_id: int, name: str = None, api_key: str = None, 
                   status: str = None, notes: str = None) -> bool:
        """Posodobi podatke ključa"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            updates = []
            params = []
            
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if api_key is not None:
                updates.append("api_key = ?")
                params.append(api_key)
            if status is not None:
                updates.append("status = ?")
                params.append(status)
            if notes is not None:
                updates.append("notes = ?")
                params.append(notes)
            
            if updates:
                params.append(key_id)
                query = f"UPDATE gemini_keys SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                conn.commit()
            
            conn.close()
            return True
        except Exception as e:
            print(f"Napaka pri posodabljanju ključa: {e}")
            return False
    
    def delete_key(self, key_id: int) -> bool:
        """Izbriše ključ"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM gemini_keys WHERE id = ?', (key_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Napaka pri brisanju ključa: {e}")
            return False
    
    def get_statistics(self) -> Dict:
        """Vrne statistike vseh ključev"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                COUNT(*) as total_keys,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_keys,
                SUM(CASE WHEN status = 'rate_limited' THEN 1 ELSE 0 END) as rate_limited_keys,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_keys,
                SUM(CASE WHEN status = 'disabled' THEN 1 ELSE 0 END) as disabled_keys,
                SUM(total_requests) as total_requests,
                SUM(error_count) as total_errors
            FROM gemini_keys
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        return {
            'total_keys': row[0] or 0,
            'active_keys': row[1] or 0,
            'rate_limited_keys': row[2] or 0,
            'error_keys': row[3] or 0,
            'disabled_keys': row[4] or 0,
            'total_requests': row[5] or 0,
            'total_errors': row[6] or 0
        }
    
    def reset_all_rate_limits(self) -> int:
        """Resetira vse rate limite (za testiranje)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE gemini_keys 
            SET status = 'active', rate_limit_reset = NULL
            WHERE status = 'rate_limited'
        ''')
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected

