"""EcoCrop (FAO) crawler for cultivated species.

Data source: FAO EcoCrop database — climate requirements for ~2,568 agricultural species.
Local file: data/ecocrop_agricultural.json (pre-downloaded, no API needed).

Fills the gap where WCVP only covers natural distribution — cultivated species like
oregano, ginger, rosemary don't appear in WCVP for Brazil.
"""
import json
import os
from typing import Generator, Dict, Any
from sqlalchemy import text
from sqlalchemy.orm import Session
from .base import BaseCrawler


class EcoCropCrawler(BaseCrawler):
    """Crawler for FAO EcoCrop cultivated species database."""

    name = 'ecocrop'

    DATA_FILE = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'data', 'ecocrop_agricultural.json'
    )

    # Map EcoCrop life_form → standardized growth_form (11 values from migration 012)
    GROWTH_FORM_MAP = {
        'herb': 'forb',
        'grass': 'graminoid',
        'shrub': 'shrub',
        'tree': 'tree',
        'vine': 'vine',
        'palm': 'palm',
        'bamboo': 'bamboo',
    }

    def fetch_data(self, mode='incremental', **kwargs) -> Generator[Dict[str, Any], None, None]:
        """Read species from local ecocrop_agricultural.json."""
        max_records = kwargs.get('max_records', None)

        if not os.path.exists(self.DATA_FILE):
            self.logger.error(f"EcoCrop data file not found: {self.DATA_FILE}")
            return

        self.logger.info(f"Loading EcoCrop data from {self.DATA_FILE}")
        with open(self.DATA_FILE, 'r', encoding='utf-8') as f:
            records = json.load(f)

        self.logger.info(f"Loaded {len(records)} EcoCrop species")

        count = 0
        for record in records:
            yield record
            count += 1

            if count % 500 == 0:
                self.logger.info(f"Progress: {count}/{len(records)} species")

            if max_records and count >= max_records:
                break

    def transform(self, raw_data: Dict) -> Dict:
        """Transform EcoCrop JSON entry to internal schema."""
        # Use WCVP canonical name if available (higher quality), else clean binomial
        if raw_data.get('in_wcvp') and raw_data.get('wcvp_canonical_name'):
            canonical = raw_data['wcvp_canonical_name'].strip()
        else:
            canonical = self._clean_species_name(raw_data.get('scientific_name', ''))

        if not canonical:
            return {}

        # Extract family from hierarchical string: "Magnoliopsida:...:Malvaceae" → "Malvaceae"
        family_raw = raw_data.get('family', '')
        family = family_raw.split(':')[-1].strip() if family_raw else None

        # Extract genus from canonical name
        genus = canonical.split()[0] if canonical else None

        transformed = {
            'canonical_name': canonical,
            'family': family,
            'genus': genus,
            'ecocrop_id': str(raw_data.get('ecocrop_id')) if raw_data.get('ecocrop_id') else None,
            'taxonomic_status': 'accepted',
        }

        # Traits
        traits = {}
        life_form = (raw_data.get('life_form') or '').lower().strip()
        if life_form:
            gf = self.GROWTH_FORM_MAP.get(life_form, 'other')
            traits['growth_form'] = gf
        if traits:
            transformed['traits'] = traits

        # Common names
        names = raw_data.get('common_names', [])
        if names:
            transformed['common_names'] = [
                {'name': n.strip(), 'language': 'en'}
                for n in names
                if isinstance(n, str) and n.strip()
            ]

        # Climate data for _save override
        transformed['_climate'] = raw_data.get('climate_envelope', {})
        transformed['_soil'] = raw_data.get('soil', {})
        transformed['_environment'] = raw_data.get('environment', {})
        transformed['_categories'] = raw_data.get('category', [])
        transformed['_life_span'] = raw_data.get('life_span', '')

        return transformed

    def validate(self, data: Dict) -> bool:
        """Require canonical_name and at least some climate data."""
        if not data.get('canonical_name'):
            return False
        climate = data.get('_climate', {})
        return bool(
            climate.get('temperature_optimal_min_c') is not None
            or climate.get('rainfall_optimal_min_mm') is not None
        )

    def _save(self, data: Dict):
        """Save species + populate species_climate_envelope + climate_envelope_ecocrop."""
        with Session(self.engine) as session:
            species_id, was_inserted = self._upsert_species(session, data)

            if was_inserted:
                self.stats['inserted'] += 1
            else:
                self.stats['updated'] += 1

            # Save traits
            if 'traits' in data:
                self._save_traits(session, species_id, data['traits'])

            # Save common names
            if 'common_names' in data:
                self._save_common_names(session, species_id, data['common_names'])

            # Save EcoCrop-specific climate envelope
            climate = data.get('_climate', {})
            soil = data.get('_soil', {})
            env = data.get('_environment', {})
            categories = data.get('_categories', [])
            life_span = data.get('_life_span', '')

            self._save_ecocrop_envelope(
                session, species_id, climate, soil, env, categories, life_span
            )

            # Populate species_climate_envelope for calculate_climate_match()
            self._save_unified_climate_envelope(session, species_id, climate)

            session.commit()

    def _save_ecocrop_envelope(
        self, session: Session, species_id: int,
        climate: Dict, soil: Dict, env: Dict,
        categories: list, life_span: str
    ):
        """Save detailed EcoCrop data to climate_envelope_ecocrop."""
        cats = categories if categories else None

        session.execute(
            text("""
                INSERT INTO climate_envelope_ecocrop (
                    species_id,
                    temp_optimal_min, temp_optimal_max,
                    temp_abs_min, temp_abs_max, killing_temperature,
                    rainfall_optimal_min, rainfall_optimal_max,
                    rainfall_abs_min, rainfall_abs_max,
                    growing_cycle_min, growing_cycle_max,
                    ph_optimal_min, ph_optimal_max,
                    ph_abs_min, ph_abs_max,
                    categories, life_span, altitude_max_m
                ) VALUES (
                    :sid,
                    :t_opt_min, :t_opt_max,
                    :t_abs_min, :t_abs_max, :killing_temp,
                    :r_opt_min, :r_opt_max,
                    :r_abs_min, :r_abs_max,
                    :gc_min, :gc_max,
                    :ph_opt_min, :ph_opt_max,
                    :ph_abs_min, :ph_abs_max,
                    :categories, :life_span, :alt_max
                )
                ON CONFLICT (species_id) DO UPDATE SET
                    temp_optimal_min = EXCLUDED.temp_optimal_min,
                    temp_optimal_max = EXCLUDED.temp_optimal_max,
                    temp_abs_min = EXCLUDED.temp_abs_min,
                    temp_abs_max = EXCLUDED.temp_abs_max,
                    killing_temperature = EXCLUDED.killing_temperature,
                    rainfall_optimal_min = EXCLUDED.rainfall_optimal_min,
                    rainfall_optimal_max = EXCLUDED.rainfall_optimal_max,
                    rainfall_abs_min = EXCLUDED.rainfall_abs_min,
                    rainfall_abs_max = EXCLUDED.rainfall_abs_max,
                    growing_cycle_min = EXCLUDED.growing_cycle_min,
                    growing_cycle_max = EXCLUDED.growing_cycle_max,
                    ph_optimal_min = EXCLUDED.ph_optimal_min,
                    ph_optimal_max = EXCLUDED.ph_optimal_max,
                    ph_abs_min = EXCLUDED.ph_abs_min,
                    ph_abs_max = EXCLUDED.ph_abs_max,
                    categories = EXCLUDED.categories,
                    life_span = EXCLUDED.life_span,
                    altitude_max_m = EXCLUDED.altitude_max_m,
                    updated_at = NOW()
            """),
            {
                'sid': species_id,
                't_opt_min': climate.get('temperature_optimal_min_c'),
                't_opt_max': climate.get('temperature_optimal_max_c'),
                't_abs_min': climate.get('temperature_abs_min_c'),
                't_abs_max': climate.get('temperature_abs_max_c'),
                'killing_temp': climate.get('killing_temperature_c'),
                'r_opt_min': climate.get('rainfall_optimal_min_mm'),
                'r_opt_max': climate.get('rainfall_optimal_max_mm'),
                'r_abs_min': climate.get('rainfall_abs_min_mm'),
                'r_abs_max': climate.get('rainfall_abs_max_mm'),
                'gc_min': climate.get('growing_cycle_min_days'),
                'gc_max': climate.get('growing_cycle_max_days'),
                'ph_opt_min': soil.get('ph_optimal_min'),
                'ph_opt_max': soil.get('ph_optimal_max'),
                'ph_abs_min': soil.get('ph_abs_min'),
                'ph_abs_max': soil.get('ph_abs_max'),
                'categories': cats,
                'life_span': life_span or None,
                'alt_max': env.get('altitude_max_m'),
            }
        )

    def _save_unified_climate_envelope(
        self, session: Session, species_id: int, climate: Dict
    ):
        """Map EcoCrop climate data → species_climate_envelope for calculate_climate_match().

        Mapping:
        - temp_mean: avg(optimal_min, optimal_max)
        - temp_min / cold_month_min: abs_min
        - temp_max / warm_month_max: abs_max
        - temp_range: abs_max - abs_min
        - precip_mean: avg(rainfall_optimal_min, rainfall_optimal_max)
        - precip_min: rainfall_abs_min
        - precip_max: rainfall_abs_max
        """
        t_opt_min = climate.get('temperature_optimal_min_c')
        t_opt_max = climate.get('temperature_optimal_max_c')
        t_abs_min = climate.get('temperature_abs_min_c')
        t_abs_max = climate.get('temperature_abs_max_c')
        r_opt_min = climate.get('rainfall_optimal_min_mm')
        r_opt_max = climate.get('rainfall_optimal_max_mm')
        r_abs_min = climate.get('rainfall_abs_min_mm')
        r_abs_max = climate.get('rainfall_abs_max_mm')

        # Compute derived values
        temp_mean = None
        if t_opt_min is not None and t_opt_max is not None:
            temp_mean = round((t_opt_min + t_opt_max) / 2.0, 2)

        temp_range = None
        if t_abs_min is not None and t_abs_max is not None:
            temp_range = round(t_abs_max - t_abs_min, 2)

        precip_mean = None
        if r_opt_min is not None and r_opt_max is not None:
            precip_mean = round((r_opt_min + r_opt_max) / 2.0, 2)

        if temp_mean is None and precip_mean is None:
            return

        session.execute(
            text("""
                INSERT INTO species_climate_envelope (
                    species_id,
                    temp_mean, temp_min, temp_max, temp_range,
                    precip_mean, precip_min, precip_max,
                    cold_month_min, warm_month_max,
                    n_regions_sampled
                ) VALUES (
                    :sid,
                    :temp_mean, :temp_min, :temp_max, :temp_range,
                    :precip_mean, :precip_min, :precip_max,
                    :cold_month_min, :warm_month_max,
                    1
                )
                ON CONFLICT (species_id) DO NOTHING
            """),
            {
                'sid': species_id,
                'temp_mean': temp_mean,
                'temp_min': t_abs_min,
                'temp_max': t_abs_max,
                'temp_range': temp_range,
                'precip_mean': precip_mean,
                'precip_min': r_abs_min,
                'precip_max': r_abs_max,
                'cold_month_min': t_abs_min,
                'warm_month_max': t_abs_max,
            }
        )

    def _clean_species_name(self, name: str) -> str:
        """Extract binomial from scientific name with author."""
        if not name:
            return ''
        parts = name.strip().split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"
        return name.strip()
