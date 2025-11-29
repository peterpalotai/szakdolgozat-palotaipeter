import os
import psycopg2
import streamlit as st
from contextlib import contextmanager
from typing import Optional, Dict, Any
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseConnection:
    
    def __init__(self):
        self.connection_params = self._get_connection_params()
    
    def _get_connection_params(self) -> Dict[str, str]:
        try:
            if hasattr(st, 'secrets') and 'database' in st.secrets:
                return {
                    'host': st.secrets['database']['host'],
                    'port': st.secrets['database']['port'],
                    'database': st.secrets['database']['database'],
                    'user': st.secrets['database']['user'],
                    'password': st.secrets['database']['password']
                }
        except Exception as e:
            logger.warning(f"Nem sikerült betölteni a Streamlit secrets-et: {e}")
        
        return {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD')
        }

    def _validate_connection_params(self) -> bool:
        required_params = ['database', 'user', 'password']
        missing_params = [param for param in required_params if not self.connection_params.get(param)]
        
        if missing_params:
            logger.error(f"Hiányzó adatbázis paraméterek: {missing_params}")
            return False
        return True
    
    @contextmanager
    def get_connection(self):
        """Adatbázis kapcsolat context manager. Biztosítja a kapcsolat automatikus lezárását, még hiba esetén is. 
        Validálja a kapcsolati paramétereket, majd létrehozza a PostgreSQL kapcsolatot és visszaadja használatra."""
        if not self._validate_connection_params():
            raise ValueError("Érvénytelen adatbázis paraméterek")
        
        conn = None
        try:
            conn = psycopg2.connect(**self.connection_params)
            yield conn
        except psycopg2.Error as e:
            logger.error(f"Adatbázis csatlakozási hiba: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def test_connection(self) -> bool:
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    logger.info("A csatlakozási teszt sikeres")
                    return result[0] == 1
        except Exception as e:
            logger.error(f"A csatlakozási teszt sikertelen: {e}")
            return False
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> Any:
        """SELECT lekérdezés végrehajtása. Végrehajtja a megadott SQL lekérdezést paraméterekkel, majd visszaadja az összes eredményt."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    return cursor.fetchall()
        except Exception as e:
            logger.error(f"Lekérdezési hiba: {e}")
            raise
    
    def execute_insert(self, query: str, params: Optional[tuple] = None) -> int:
        """INSERT lekérdezés végrehajtása. Beszúr egy vagy több rekordot az adatbázisba a megadott SQL lekérdezéssel és paraméterekkel."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    conn.commit()
                    return cursor.rowcount
        except Exception as e:
            logger.error(f"Hiba: {e}")
            raise
    
    def execute_update(self, query: str, params: Optional[tuple] = None) -> int:
        """UPDATE lekérdezés végrehajtása. Frissít egy vagy több rekordot az adatbázisban a megadott SQL lekérdezéssel és paraméterekkel."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    conn.commit()
                    return cursor.rowcount
        except Exception as e:
            logger.error(f"Hiba: {e}")
            raise


db = DatabaseConnection()


def get_db_connection():
    """Visszaadja az adatbázis kapcsolat példányt."""
    return db


def test_db_connection():
    """Teszteli az adatbázis kapcsolatot."""
    return db.test_connection()


def execute_query(query: str, params: Optional[tuple] = None):
    """SELECT lekérdezés végrehajtása."""
    return db.execute_query(query, params)


def execute_insert(query: str, params: Optional[tuple] = None):
    """INSERT lekérdezés végrehajtása."""
    return db.execute_insert(query, params)


def execute_update(query: str, params: Optional[tuple] = None):
    """UPDATE lekérdezés végrehajtása."""
    return db.execute_update(query, params)
