from __future__ import annotations
import sqlite3
import os
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ClipboardEntry:
    """Entrada do histórico da área de transferência"""
    id: Optional[int] = None
    content: str = ''
    content_type: str = 'text'  # 'text' ou 'image'
    timestamp: Optional[datetime] = None
    is_pinned: bool = False
    category: str = ''  # categoria opcional para organização


class ClipboardHistoryDB:
    """Gerencia o histórico da área de transferência com SQLite"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self) -> None:
        """Inicializa o banco de dados"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS clipboard_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    content_type TEXT DEFAULT 'text',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_pinned INTEGER DEFAULT 0,
                    category TEXT DEFAULT ''
                )
            ''')
            
            # Índices para melhor performance
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON clipboard_history(timestamp DESC)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_pinned 
                ON clipboard_history(is_pinned DESC, timestamp DESC)
            ''')
            conn.commit()
    
    def add_entry(self, content: str, content_type: str = 'text') -> int:
        """
        Adiciona uma entrada ao histórico.
        Retorna o ID da entrada criada.
        """
        # Verificar se já existe entrada idêntica recente (últimos 5 segundos)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT id FROM clipboard_history 
                WHERE content = ? 
                AND datetime(timestamp) > datetime('now', '-5 seconds')
                LIMIT 1
            ''', (content,))
            
            if cursor.fetchone():
                return -1  # Já existe, não adicionar duplicata
            
            cursor = conn.execute('''
                INSERT INTO clipboard_history (content, content_type, timestamp)
                VALUES (?, ?, ?)
            ''', (content, content_type, datetime.now()))
            conn.commit()
            return cursor.lastrowid
    
    def get_entries(
        self,
        limit: int = 100,
        search: Optional[str] = None,
        pinned_only: bool = False
    ) -> List[ClipboardEntry]:
        """
        Retorna entradas do histórico.
        
        Args:
            limit: número máximo de entradas
            search: filtro de busca (case-insensitive)
            pinned_only: retornar apenas fixados
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            query = 'SELECT * FROM clipboard_history WHERE 1=1'
            params: List = []
            
            if pinned_only:
                query += ' AND is_pinned = 1'
            
            if search:
                query += ' AND content LIKE ?'
                params.append(f'%{search}%')
            
            query += ' ORDER BY is_pinned DESC, timestamp DESC LIMIT ?'
            params.append(limit)
            
            cursor = conn.execute(query, params)
            
            entries = []
            for row in cursor:
                entries.append(ClipboardEntry(
                    id=row['id'],
                    content=row['content'],
                    content_type=row['content_type'],
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    is_pinned=bool(row['is_pinned']),
                    category=row['category'] or ''
                ))
            
            return entries
    
    def toggle_pin(self, entry_id: int) -> bool:
        """Alterna o estado de fixado de uma entrada"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT is_pinned FROM clipboard_history WHERE id = ?',
                (entry_id,)
            )
            row = cursor.fetchone()
            if not row:
                return False
            
            new_state = 0 if row[0] else 1
            conn.execute(
                'UPDATE clipboard_history SET is_pinned = ? WHERE id = ?',
                (new_state, entry_id)
            )
            conn.commit()
            return True
    
    def delete_entry(self, entry_id: int) -> bool:
        """Remove uma entrada do histórico"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'DELETE FROM clipboard_history WHERE id = ?',
                (entry_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def clear_history(self, keep_pinned: bool = True) -> int:
        """
        Limpa o histórico.
        
        Args:
            keep_pinned: se True, mantém entradas fixadas
        
        Returns:
            número de entradas removidas
        """
        with sqlite3.connect(self.db_path) as conn:
            if keep_pinned:
                cursor = conn.execute('DELETE FROM clipboard_history WHERE is_pinned = 0')
            else:
                cursor = conn.execute('DELETE FROM clipboard_history')
            conn.commit()
            return cursor.rowcount
    
    def update_category(self, entry_id: int, category: str) -> bool:
        """Atualiza a categoria de uma entrada"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'UPDATE clipboard_history SET category = ? WHERE id = ?',
                (category, entry_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def get_stats(self) -> dict:
        """Retorna estatísticas do histórico"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(is_pinned) as pinned,
                    COUNT(DISTINCT DATE(timestamp)) as days_with_activity
                FROM clipboard_history
            ''')
            row = cursor.fetchone()
            
            return {
                'total': row[0] or 0,
                'pinned': row[1] or 0,
                'days_with_activity': row[2] or 0
            }
