"""
GBIF Occurrence Crawler for Climate Envelope Calculation.

This crawler fetches individual occurrence records from GBIF,
extracts climate data at each point using WorldClim rasters,
and calculates climate envelopes with percentile statistics.

Usage:
    python -m crawlers.run gbif_occurrences --limit 1000
    python -m crawlers.run gbif_occurrences --mode full --limit 10000
"""

import os
import time
import requests
import numpy as np
from datetime import datetime
from typing import Dict, List, Generator, Any, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from .base import BaseCrawler


class GBIFOccurrenceCrawler(BaseCrawler):
    """
    Crawler to fetch GBIF occurrences and calculate climate envelopes.

    Strategy:
    1. Get priority species (those without GBIF envelope yet)
    2. For each species, fetch occurrences from GBIF API
    3. Filter by quality (coordinate uncertainty, year)
    4. Extract climate at each point using get_climate_at_point()
    5. Calculate envelope statistics (mean, percentiles, min/max)
    """

    @property
    def name(self) -> str:
        return 'gbif_occurrences'

    # API Configuration
    GBIF_API = 'https://api.gbif.org/v1/occurrence/search'

    # Quality filters
    MIN_OCCURRENCES = 20  # Minimum points for reliable envelope
    MAX_UNCERTAINTY_M = 10000  # 10km max coordinate uncertainty
    MIN_YEAR = 1970  # Only recent observations
    MAX_OCCURRENCES_PER_SPECIES = 1000  # Limit per species for performance

    # Rate limiting
    API_DELAY = 0.3  # Seconds between API calls
    SPECIES_DELAY = 1.0  # Seconds between species processing
    MAX_RETRIES = 5  # Max retries on 429
    BACKOFF_BASE = 30  # Base backoff in seconds (30, 60, 120, 240, 480)

    def get_priority_species(self, limit: int = 1000) -> List[Dict]:
        """
        Get species that need GBIF occurrence-based envelopes.

        Priority order:
        1. Species with TreeGOER data (have ecoregion counts, likely findable in GBIF)
        2. Species with WCVP distribution but no envelope yet
        """
        with Session(self.engine) as session:
            result = session.execute(text("""
                SELECT
                    s.id,
                    s.canonical_name,
                    s.family,
                    COALESCE(se_agg.total_observations, 0) as tregoer_occurrences,
                    COALESCE(sr.region_count, 0) as wcvp_regions
                FROM species s
                JOIN species_unified su ON s.id = su.species_id
                LEFT JOIN climate_envelope_gbif ceg ON s.id = ceg.species_id
                LEFT JOIN (
                    SELECT species_id, SUM(n_observations) as total_observations
                    FROM species_ecoregions
                    GROUP BY species_id
                ) se_agg ON s.id = se_agg.species_id
                LEFT JOIN (
                    SELECT species_id, COUNT(*) as region_count
                    FROM species_regions
                    WHERE is_native = TRUE
                    GROUP BY species_id
                ) sr ON s.id = sr.species_id
                WHERE ceg.species_id IS NULL  -- No GBIF envelope yet
                  AND su.growth_form IS NOT NULL
                  AND (se_agg.species_id IS NOT NULL OR sr.species_id IS NOT NULL)  -- Has some distribution data
                ORDER BY
                    se_agg.total_observations DESC NULLS LAST,  -- Prioritize species with more TreeGOER occurrences
                    sr.region_count DESC NULLS LAST,
                    s.id
                LIMIT :limit
            """), {'limit': limit})

            return [dict(row._mapping) for row in result]

    def _request_with_backoff(self, params: Dict, species_name: str) -> Optional[Dict]:
        """
        Make a GBIF API request with exponential backoff on 429 errors.

        Returns:
            Response JSON dict, or None if all retries failed.
        """
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = requests.get(
                    self.GBIF_API,
                    params=params,
                    timeout=30,
                    headers={'Accept': 'application/json'}
                )

                if response.status_code == 429:
                    if attempt >= self.MAX_RETRIES:
                        self.logger.warning(
                            f"GBIF 429 for {species_name}: max retries ({self.MAX_RETRIES}) exceeded"
                        )
                        return None

                    # Exponential backoff: 30, 60, 120, 240, 480 seconds
                    wait_time = self.BACKOFF_BASE * (2 ** attempt)
                    # Check Retry-After header if provided
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        try:
                            wait_time = max(wait_time, int(retry_after))
                        except ValueError:
                            pass

                    self.logger.info(
                        f"GBIF 429 for {species_name}: backing off {wait_time}s "
                        f"(attempt {attempt + 1}/{self.MAX_RETRIES})"
                    )
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response.json()

            except requests.ConnectionError as e:
                if attempt < self.MAX_RETRIES:
                    wait_time = self.BACKOFF_BASE * (2 ** attempt)
                    self.logger.warning(
                        f"Connection error for {species_name}: {e}. Retrying in {wait_time}s"
                    )
                    time.sleep(wait_time)
                    continue
                self.logger.warning(f"Connection failed for {species_name} after {self.MAX_RETRIES} retries")
                return None

            except requests.RequestException as e:
                self.logger.warning(f"GBIF API error for {species_name}: {e}")
                return None

        return None

    def fetch_gbif_occurrences(self, species_name: str, limit: int = 1000) -> List[Dict]:
        """
        Fetch occurrence records from GBIF API.

        Args:
            species_name: Scientific name to search
            limit: Maximum occurrences to fetch

        Returns:
            List of occurrence dictionaries with coordinates
        """
        params = {
            'scientificName': species_name,
            'hasCoordinate': 'true',
            'hasGeospatialIssue': 'false',
            'coordinateUncertaintyInMeters': f'0,{self.MAX_UNCERTAINTY_M}',
            'year': f'{self.MIN_YEAR},{datetime.now().year}',
            'limit': min(limit, 300),  # GBIF API max per request
            'offset': 0
        }

        occurrences = []
        max_pages = (limit // 300) + 1

        for page in range(max_pages):
            if len(occurrences) >= limit:
                break

            data = self._request_with_backoff(params, species_name)
            if data is None:
                break

            results = data.get('results', [])
            if not results:
                break

            for occ in results:
                if self._is_valid_occurrence(occ):
                    occurrences.append({
                        'gbif_id': occ.get('key'),
                        'latitude': occ.get('decimalLatitude'),
                        'longitude': occ.get('decimalLongitude'),
                        'uncertainty_m': occ.get('coordinateUncertaintyInMeters'),
                        'year': occ.get('year'),
                        'country_code': occ.get('countryCode')
                    })

                    if len(occurrences) >= limit:
                        break

            if data.get('endOfRecords', True):
                break

            params['offset'] += 300
            time.sleep(self.API_DELAY)

        return occurrences

    def _is_valid_occurrence(self, occ: Dict) -> bool:
        """
        Check if an occurrence meets quality criteria.

        Filters:
        - Valid coordinates (not null, within bounds)
        - Not at null island (0,0)
        - Coordinate uncertainty within limit
        """
        lat = occ.get('decimalLatitude')
        lon = occ.get('decimalLongitude')

        # Must have coordinates
        if lat is None or lon is None:
            return False

        # Valid coordinate range
        if abs(lat) > 90 or abs(lon) > 180:
            return False

        # Not null island
        if lat == 0 and lon == 0:
            return False

        # Check uncertainty
        uncertainty = occ.get('coordinateUncertaintyInMeters')
        if uncertainty and uncertainty > self.MAX_UNCERTAINTY_M:
            return False

        return True

    def extract_climate_at_points(self, occurrences: List[Dict]) -> List[Dict]:
        """
        Extract WorldClim climate data at each occurrence point.

        Uses the get_climate_json_at_point() database function that returns
        all bio variables as JSONB in a single call.
        """
        climate_data = []

        with Session(self.engine) as session:
            for occ in occurrences:
                try:
                    result = session.execute(
                        text("SELECT get_climate_json_at_point(:lat, :lon) as climate_json"),
                        {'lat': occ['latitude'], 'lon': occ['longitude']}
                    ).fetchone()

                    if result and result.climate_json:
                        cj = result.climate_json
                        bio1 = cj.get('bio1')
                        if bio1 is not None:
                            climate_data.append({
                                **occ,
                                'bio1': float(bio1) if bio1 else None,
                                'bio5': float(cj.get('bio5')) if cj.get('bio5') else None,
                                'bio6': float(cj.get('bio6')) if cj.get('bio6') else None,
                                'bio7': float(cj.get('bio7')) if cj.get('bio7') else None,
                                'bio12': float(cj.get('bio12')) if cj.get('bio12') else None,
                                'bio15': float(cj.get('bio15')) if cj.get('bio15') else None
                            })
                except Exception as e:
                    self.logger.debug(f"Climate extraction error at {occ['latitude']},{occ['longitude']}: {e}")

        return climate_data

    def calculate_envelope(self, climate_data: List[Dict]) -> Optional[Dict]:
        """
        Calculate climate envelope statistics from occurrence data.

        Returns envelope with:
        - Mean values
        - 5th and 95th percentiles (robust to outliers)
        - Min/max (absolute range)
        - Quality indicator based on sample size
        """
        if len(climate_data) < self.MIN_OCCURRENCES:
            return None

        # Extract climate arrays
        bio1 = np.array([d['bio1'] for d in climate_data if d['bio1'] is not None])
        bio5 = np.array([d['bio5'] for d in climate_data if d['bio5'] is not None])
        bio6 = np.array([d['bio6'] for d in climate_data if d['bio6'] is not None])
        bio12 = np.array([d['bio12'] for d in climate_data if d['bio12'] is not None])
        bio15 = np.array([d['bio15'] for d in climate_data if d['bio15'] is not None])

        # Need minimum data for statistics
        if len(bio1) < self.MIN_OCCURRENCES:
            return None

        # Collect metadata
        years = [d['year'] for d in climate_data if d.get('year')]
        countries = set(d['country_code'] for d in climate_data if d.get('country_code'))

        n = len(bio1)

        # Quality based on sample size
        if n >= 100:
            quality = 'high'
        elif n >= 50:
            quality = 'medium'
        else:
            quality = 'low'

        return {
            # Temperature mean
            'temp_mean': round(float(np.mean(bio1)), 2),
            'temp_p05': round(float(np.percentile(bio1, 5)), 2),
            'temp_p95': round(float(np.percentile(bio1, 95)), 2),
            'temp_min': round(float(np.min(bio1)), 2),
            'temp_max': round(float(np.max(bio1)), 2),

            # Cold/warm month extremes
            'cold_month_mean': round(float(np.mean(bio6)), 2) if len(bio6) > 0 else None,
            'cold_month_p05': round(float(np.percentile(bio6, 5)), 2) if len(bio6) > 0 else None,
            'warm_month_mean': round(float(np.mean(bio5)), 2) if len(bio5) > 0 else None,
            'warm_month_p95': round(float(np.percentile(bio5, 95)), 2) if len(bio5) > 0 else None,

            # Precipitation
            'precip_mean': round(float(np.mean(bio12)), 2) if len(bio12) > 0 else None,
            'precip_p05': round(float(np.percentile(bio12, 5)), 2) if len(bio12) > 0 else None,
            'precip_p95': round(float(np.percentile(bio12, 95)), 2) if len(bio12) > 0 else None,
            'precip_min': round(float(np.min(bio12)), 2) if len(bio12) > 0 else None,
            'precip_max': round(float(np.max(bio12)), 2) if len(bio12) > 0 else None,
            'precip_seasonality': round(float(np.mean(bio15)), 2) if len(bio15) > 0 else None,

            # Quality metrics
            'n_occurrences': n,
            'n_countries': len(countries),
            'year_range': f"{min(years)}-{max(years)}" if years else None,
            'envelope_quality': quality
        }

    def fetch_data(self, mode: str = 'incremental', limit: int = 1000, **kwargs) -> Generator[Dict, None, None]:
        """
        Main crawler entry point.

        Args:
            mode: 'incremental' for new species only, 'full' for all
            limit: Maximum number of species to process

        Yields:
            Processing results (not used by base class transform/save flow)
        """
        self.logger.info(f"Starting GBIF occurrence crawler (mode={mode}, limit={limit})")

        # Get species to process
        species_list = self.get_priority_species(limit)
        self.logger.info(f"Found {len(species_list)} priority species")

        if not species_list:
            self.logger.info("No species need GBIF envelopes")
            return

        processed = 0
        envelopes_created = 0
        total_occurrences = 0

        for species in species_list:
            species_id = species['id']
            species_name = species['canonical_name']

            self.logger.debug(f"Processing {species_name}")

            # Fetch occurrences from GBIF
            occurrences = self.fetch_gbif_occurrences(
                species_name,
                limit=self.MAX_OCCURRENCES_PER_SPECIES
            )

            if len(occurrences) < self.MIN_OCCURRENCES:
                self.logger.debug(f"  Skipping: only {len(occurrences)} occurrences")
                self.stats['skipped'] += 1
                continue

            # Extract climate at each point
            climate_data = self.extract_climate_at_points(occurrences)

            if len(climate_data) < self.MIN_OCCURRENCES:
                self.logger.debug(f"  Skipping: only {len(climate_data)} with valid climate")
                self.stats['skipped'] += 1
                continue

            # Save occurrences
            saved_count = self._save_occurrences(species_id, climate_data)
            total_occurrences += saved_count

            # Calculate and save envelope
            envelope = self.calculate_envelope(climate_data)
            if envelope:
                self._save_envelope(species_id, envelope)
                self._update_analysis(species_id)
                envelopes_created += 1
                self.stats['inserted'] += 1

            processed += 1
            self.stats['processed'] += 1

            if processed % 50 == 0:
                self.logger.info(
                    f"Progress: {processed}/{len(species_list)} species, "
                    f"{envelopes_created} envelopes, {total_occurrences} occurrences"
                )

            time.sleep(self.SPECIES_DELAY)

            # Yield for base class flow (not really used here)
            yield {
                'species_id': species_id,
                'species_name': species_name,
                'occurrences': len(climate_data),
                'envelope_created': envelope is not None
            }

        self.logger.info(
            f"Completed: {processed} species processed, "
            f"{envelopes_created} envelopes created, "
            f"{total_occurrences} occurrences saved"
        )

    def _save_occurrences(self, species_id: int, climate_data: List[Dict]) -> int:
        """Save occurrence records to database."""
        saved = 0

        with Session(self.engine) as session:
            for d in climate_data:
                try:
                    session.execute(
                        text("""
                            INSERT INTO gbif_occurrences (
                                species_id, gbif_id, latitude, longitude,
                                coordinate_uncertainty_m, year, country_code,
                                bio1, bio5, bio6, bio7, bio12, bio15
                            ) VALUES (
                                :species_id, :gbif_id, :lat, :lon,
                                :uncertainty, :year, :country,
                                :bio1, :bio5, :bio6, :bio7, :bio12, :bio15
                            )
                            ON CONFLICT (gbif_id) DO NOTHING
                        """),
                        {
                            'species_id': species_id,
                            'gbif_id': d['gbif_id'],
                            'lat': d['latitude'],
                            'lon': d['longitude'],
                            'uncertainty': d.get('uncertainty_m'),
                            'year': d.get('year'),
                            'country': d.get('country_code'),
                            'bio1': d.get('bio1'),
                            'bio5': d.get('bio5'),
                            'bio6': d.get('bio6'),
                            'bio7': d.get('bio7'),
                            'bio12': d.get('bio12'),
                            'bio15': d.get('bio15')
                        }
                    )
                    saved += 1
                except Exception as e:
                    self.logger.debug(f"Occurrence save error: {e}")

            session.commit()

        return saved

    def _save_envelope(self, species_id: int, envelope: Dict) -> None:
        """Save calculated envelope to database."""
        with Session(self.engine) as session:
            session.execute(
                text("""
                    INSERT INTO climate_envelope_gbif (
                        species_id, temp_mean, temp_p05, temp_p95, temp_min, temp_max,
                        cold_month_mean, cold_month_p05, warm_month_mean, warm_month_p95,
                        precip_mean, precip_p05, precip_p95, precip_min, precip_max,
                        precip_seasonality, n_occurrences, n_countries, year_range, envelope_quality
                    ) VALUES (
                        :species_id, :temp_mean, :temp_p05, :temp_p95, :temp_min, :temp_max,
                        :cold_month_mean, :cold_month_p05, :warm_month_mean, :warm_month_p95,
                        :precip_mean, :precip_p05, :precip_p95, :precip_min, :precip_max,
                        :precip_seasonality, :n_occurrences, :n_countries, :year_range, :envelope_quality
                    )
                    ON CONFLICT (species_id) DO UPDATE SET
                        temp_mean = EXCLUDED.temp_mean,
                        temp_p05 = EXCLUDED.temp_p05,
                        temp_p95 = EXCLUDED.temp_p95,
                        temp_min = EXCLUDED.temp_min,
                        temp_max = EXCLUDED.temp_max,
                        cold_month_mean = EXCLUDED.cold_month_mean,
                        cold_month_p05 = EXCLUDED.cold_month_p05,
                        warm_month_mean = EXCLUDED.warm_month_mean,
                        warm_month_p95 = EXCLUDED.warm_month_p95,
                        precip_mean = EXCLUDED.precip_mean,
                        precip_p05 = EXCLUDED.precip_p05,
                        precip_p95 = EXCLUDED.precip_p95,
                        precip_min = EXCLUDED.precip_min,
                        precip_max = EXCLUDED.precip_max,
                        precip_seasonality = EXCLUDED.precip_seasonality,
                        n_occurrences = EXCLUDED.n_occurrences,
                        n_countries = EXCLUDED.n_countries,
                        year_range = EXCLUDED.year_range,
                        envelope_quality = EXCLUDED.envelope_quality,
                        updated_at = CURRENT_TIMESTAMP
                """),
                {
                    'species_id': species_id,
                    **envelope
                }
            )
            session.commit()

    def _update_analysis(self, species_id: int) -> None:
        """Update the analysis table for this species."""
        with Session(self.engine) as session:
            try:
                session.execute(
                    text("SELECT update_envelope_analysis(:species_id)"),
                    {'species_id': species_id}
                )
                session.commit()
            except Exception as e:
                self.logger.debug(f"Analysis update error: {e}")

    def transform(self, raw_data: Dict) -> Dict:
        """Transform is not used - we handle everything in fetch_data."""
        return raw_data

    def validate(self, data: Dict) -> bool:
        """Always returns False - processing is handled entirely in fetch_data."""
        return False


# For running directly
if __name__ == '__main__':
    import sys
    db_url = os.environ.get('DATABASE_URL', 'postgresql://localhost/diversiplant')
    crawler = GBIFOccurrenceCrawler(db_url)

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    crawler.run(mode='incremental', limit=limit)
