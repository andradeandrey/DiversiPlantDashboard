"""Database connection management for DiversiPlant."""
import os
from contextlib import contextmanager
from typing import Optional, Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

# Database configuration from environment or defaults
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': os.environ.get('DB_PORT', '5432'),
    'database': os.environ.get('DB_NAME', 'diversiplant'),
    'user': os.environ.get('DB_USER', 'diversiplant'),
    'password': os.environ.get('DB_PASSWORD', ''),
}


def get_database_url() -> str:
    """Build database URL from configuration."""
    password = f":{DB_CONFIG['password']}" if DB_CONFIG['password'] else ""
    return (
        f"postgresql://{DB_CONFIG['user']}{password}@"
        f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )


class DatabaseConnection:
    """Singleton database connection manager."""

    _instance: Optional['DatabaseConnection'] = None
    _engine = None
    _session_factory = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._engine is None:
            self._engine = create_engine(
                get_database_url(),
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True
            )
            self._session_factory = sessionmaker(bind=self._engine)

    @property
    def engine(self):
        return self._engine

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations."""
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def execute(self, query: str, params: Optional[dict] = None):
        """Execute a raw SQL query."""
        with self.session() as session:
            result = session.execute(text(query), params or {})
            return result.fetchall()

    def execute_scalar(self, query: str, params: Optional[dict] = None):
        """Execute a query and return single value."""
        with self.session() as session:
            result = session.execute(text(query), params or {})
            return result.scalar()


# Global database connection instance
_db: Optional[DatabaseConnection] = None


def get_db() -> DatabaseConnection:
    """Get the database connection instance."""
    global _db
    if _db is None:
        _db = DatabaseConnection()
    return _db


def get_ecoregion_by_coords(lat: float, lon: float) -> Optional[dict]:
    """Get ecoregion for given coordinates."""
    db = get_db()
    result = db.execute(
        "SELECT * FROM get_ecoregion_by_coords(:lat, :lon)",
        {'lat': lat, 'lon': lon}
    )
    if result:
        row = result[0]
        return {
            'eco_name': row[0],
            'biome_name': row[1],
            'biome_num': row[2],
            'realm': row[3]
        }
    return None


def get_tdwg_by_coords(lat: float, lon: float) -> Optional[dict]:
    """Get TDWG region for given coordinates."""
    db = get_db()
    result = db.execute(
        "SELECT * FROM get_tdwg_by_coords(:lat, :lon)",
        {'lat': lat, 'lon': lon}
    )
    if result:
        row = result[0]
        return {
            'level3_code': row[0],
            'level3_name': row[1],
            'continent': row[2]
        }
    return None


def filter_species_by_distribution(tdwg_code: str, filter_type: str = None):
    """Filter species by distribution type in a TDWG region."""
    db = get_db()
    query = """
        SELECT s.canonical_name, s.family, st.growth_form
        FROM species s
        JOIN species_distribution sd ON s.id = sd.species_id
        LEFT JOIN species_traits st ON s.id = st.species_id
        WHERE sd.tdwg_code = :tdwg
    """

    if filter_type == 'endemic':
        query += " AND sd.endemic = TRUE"
    elif filter_type == 'native':
        query += " AND sd.native = TRUE"
    elif filter_type == 'naturalized':
        query += " AND sd.introduced = TRUE"

    query += " ORDER BY s.family, s.canonical_name"

    return db.execute(query, {'tdwg': tdwg_code})
