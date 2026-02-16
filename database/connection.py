"""Database connection management for DiversiPlant."""
import os
import logging
from contextlib import contextmanager
from typing import Optional, Generator, List, Dict
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


def get_bioclim_at_coords(lat: float, lon: float) -> Optional[Dict[str, float]]:
    """Get BioClim variables for coordinates. Tries raster first, falls back to TDWG."""
    db = get_db()
    try:
        rows = db.execute(
            "SELECT bio_var, value FROM get_climate_at_point(:lat, :lon)",
            {'lat': lat, 'lon': lon}
        )
        bioclim = {row[0]: float(row[1]) for row in rows if row[1] is not None}
    except Exception:
        bioclim = {}

    if not bioclim or 'bio1' not in bioclim:
        tdwg = get_tdwg_by_coords(lat, lon)
        if tdwg:
            try:
                rows = db.execute(
                    """SELECT bio1_mean, bio5_mean, bio6_mean, bio12_mean, bio15_mean
                       FROM tdwg_climate WHERE tdwg_code = :code""",
                    {'code': tdwg['level3_code']}
                )
                if rows:
                    r = rows[0]
                    bioclim = {
                        'bio1': float(r[0]) if r[0] else None,
                        'bio5': float(r[1]) if r[1] else None,
                        'bio6': float(r[2]) if r[2] else None,
                        'bio12': float(r[3]) if r[3] else None,
                        'bio15': float(r[4]) if r[4] else None,
                    }
            except Exception:
                pass

    required = ['bio1', 'bio5', 'bio6', 'bio12', 'bio15']
    if all(bioclim.get(k) is not None for k in required):
        return {k: bioclim[k] for k in required}
    return None


def get_climate_match_scores(
    lat: float, lon: float, sci_names: List[str], threshold: float = 0.3
) -> Dict[str, float]:
    """Compute climate match scores for a list of species (by scientific name).

    Returns dict mapping scientific_name -> score (0-1), only for species above threshold.
    """
    bioclim = get_bioclim_at_coords(lat, lon)
    if not bioclim:
        return {}

    db = get_db()
    # Build parameterized IN clause for the scientific names
    params = {
        'bio1': bioclim['bio1'],
        'bio5': bioclim['bio5'],
        'bio6': bioclim['bio6'],
        'bio12': bioclim['bio12'],
        'bio15': bioclim['bio15'],
        'threshold': threshold,
    }
    placeholders = []
    for i, name in enumerate(sci_names):
        key = f"n{i}"
        placeholders.append(f":{key}")
        params[key] = name

    if not placeholders:
        return {}

    in_clause = ", ".join(placeholders)
    query = f"""
        SELECT sp.canonical_name,
               calculate_climate_match(sp.id, :bio1, :bio5, :bio6, :bio12, :bio15) as score
        FROM species sp
        JOIN species_climate_envelope sce ON sp.id = sce.species_id
        WHERE sp.canonical_name IN ({in_clause})
    """

    try:
        rows = db.execute(query, params)
        return {
            row[0]: float(row[1])
            for row in rows
            if row[1] is not None and float(row[1]) >= threshold
        }
    except Exception as e:
        logging.warning(f"[CLIMATE] Failed to get climate scores: {e}")
        return {}


def get_cultivated_species(
    lat: float = None, lon: float = None, threshold: float = 0.3
) -> List[Dict]:
    """Get EcoCrop cultivated species, optionally with climate match scores.

    Returns list of dicts with keys:
    canonical_name, common_name, family, growth_form, categories, life_span, score
    """
    db = get_db()

    # Base query: species with ecocrop data
    base_query = """
        SELECT s.canonical_name,
               cn.common_name,
               s.family,
               su.growth_form,
               cee.categories,
               cee.life_span
        FROM species s
        JOIN climate_envelope_ecocrop cee ON s.id = cee.species_id
        LEFT JOIN species_unified su ON s.id = su.species_id
        LEFT JOIN LATERAL (
            SELECT common_name FROM common_names
            WHERE species_id = s.id AND language = 'en'
            LIMIT 1
        ) cn ON TRUE
        WHERE s.ecocrop_id IS NOT NULL
    """

    # If coordinates provided, also compute climate match score
    if lat is not None and lon is not None:
        bioclim = get_bioclim_at_coords(lat, lon)
        if bioclim:
            query = f"""
                SELECT s.canonical_name,
                       cn.common_name,
                       s.family,
                       su.growth_form,
                       cee.categories,
                       cee.life_span,
                       calculate_climate_match(s.id, :bio1, :bio5, :bio6, :bio12, :bio15) as score
                FROM species s
                JOIN climate_envelope_ecocrop cee ON s.id = cee.species_id
                JOIN species_climate_envelope sce ON s.id = sce.species_id
                LEFT JOIN species_unified su ON s.id = su.species_id
                LEFT JOIN LATERAL (
                    SELECT common_name FROM common_names
                    WHERE species_id = s.id AND language = 'en'
                    LIMIT 1
                ) cn ON TRUE
                WHERE s.ecocrop_id IS NOT NULL
                ORDER BY score DESC
            """
            try:
                rows = db.execute(query, {
                    'bio1': bioclim['bio1'],
                    'bio5': bioclim['bio5'],
                    'bio6': bioclim['bio6'],
                    'bio12': bioclim['bio12'],
                    'bio15': bioclim['bio15'],
                })
                return [
                    {
                        'canonical_name': r[0],
                        'common_name': r[1],
                        'family': r[2],
                        'growth_form': r[3],
                        'categories': r[4],
                        'life_span': r[5],
                        'score': float(r[6]) if r[6] is not None else 0,
                    }
                    for r in rows
                    if r[6] is not None and float(r[6]) >= threshold
                ]
            except Exception as e:
                logging.warning(f"[CULTIVATED] Climate scoring failed: {e}")

    # Fallback: return all without score
    try:
        rows = db.execute(base_query)
        return [
            {
                'canonical_name': r[0],
                'common_name': r[1],
                'family': r[2],
                'growth_form': r[3],
                'categories': r[4],
                'life_span': r[5],
                'score': None,
            }
            for r in rows
        ]
    except Exception as e:
        logging.warning(f"[CULTIVATED] Failed to get cultivated species: {e}")
        return []
