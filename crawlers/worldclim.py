"""WorldClim climate data crawler with full Bio variable storage."""
from typing import Generator, Dict, Any, Optional, List, Tuple
import requests
import os
import tempfile
import zipfile
import io
import json
import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session
from .base import BaseCrawler


class WorldClimCrawler(BaseCrawler):
    """
    Crawler for WorldClim climate data.

    Source: https://www.worldclim.org
    Data: Bioclimatic variables (BIO1-BIO19), temperature, precipitation
    Resolution: 30s (~1km), 2.5m, 5m, 10m

    This crawler downloads WorldClim raster data and calculates zonal statistics
    for each TDWG Level 3 region, storing all 19 bioclimatic variables.
    """

    name = 'worldclim'

    # Updated URL (changed from biogeo.ucdavis.edu to geodata.ucdavis.edu)
    BASE_URL = 'https://geodata.ucdavis.edu/climate/worldclim/2_1/base'

    # Bioclimatic variables with metadata
    # WorldClim 2.1 stores values in actual units (°C for temp, mm for precip)
    BIOCLIM_VARS = {
        'bio1': {'name': 'Annual Mean Temperature', 'unit': '°C', 'scale': 1},
        'bio2': {'name': 'Mean Diurnal Range', 'unit': '°C', 'scale': 1},
        'bio3': {'name': 'Isothermality', 'unit': '%', 'scale': 1},
        'bio4': {'name': 'Temperature Seasonality', 'unit': 'std*100', 'scale': 1},
        'bio5': {'name': 'Max Temperature of Warmest Month', 'unit': '°C', 'scale': 1},
        'bio6': {'name': 'Min Temperature of Coldest Month', 'unit': '°C', 'scale': 1},
        'bio7': {'name': 'Temperature Annual Range', 'unit': '°C', 'scale': 1},
        'bio8': {'name': 'Mean Temperature of Wettest Quarter', 'unit': '°C', 'scale': 1},
        'bio9': {'name': 'Mean Temperature of Driest Quarter', 'unit': '°C', 'scale': 1},
        'bio10': {'name': 'Mean Temperature of Warmest Quarter', 'unit': '°C', 'scale': 1},
        'bio11': {'name': 'Mean Temperature of Coldest Quarter', 'unit': '°C', 'scale': 1},
        'bio12': {'name': 'Annual Precipitation', 'unit': 'mm', 'scale': 1},
        'bio13': {'name': 'Precipitation of Wettest Month', 'unit': 'mm', 'scale': 1},
        'bio14': {'name': 'Precipitation of Driest Month', 'unit': 'mm', 'scale': 1},
        'bio15': {'name': 'Precipitation Seasonality', 'unit': 'CV', 'scale': 1},
        'bio16': {'name': 'Precipitation of Wettest Quarter', 'unit': 'mm', 'scale': 1},
        'bio17': {'name': 'Precipitation of Driest Quarter', 'unit': 'mm', 'scale': 1},
        'bio18': {'name': 'Precipitation of Warmest Quarter', 'unit': 'mm', 'scale': 1},
        'bio19': {'name': 'Precipitation of Coldest Quarter', 'unit': 'mm', 'scale': 1},
    }

    # Köppen climate classification thresholds
    KOPPEN_THRESHOLDS = {
        'tropical': {'temp_min': 18},  # All months >= 18°C
        'arid': {'aridity': 0.65},     # Precipitation threshold
        'temperate': {'temp_cold': 0, 'temp_warm': 10},
        'continental': {'temp_cold': -3, 'temp_warm': 10},
        'polar': {'temp_max': 10},
    }

    def __init__(self, db_url: str):
        super().__init__(db_url)
        self._cache_dir = os.path.join(tempfile.gettempdir(), 'worldclim_cache')
        os.makedirs(self._cache_dir, exist_ok=True)
        self._raster_data = {}

    def fetch_data(self, mode='incremental', **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch WorldClim climate data and calculate zonal statistics per TDWG region.

        Args:
            mode: 'full' or 'incremental'
            **kwargs: Additional parameters
                - resolution: '10m', '5m', '2.5m', '30s' (default: '10m')
                - store_db: Whether to store results in database (default: True)

        Yields:
            Climate statistics per TDWG region
        """
        resolution = kwargs.get('resolution', '10m')
        store_db = kwargs.get('store_db', True)

        self.logger.info(f"Fetching WorldClim data at {resolution} resolution")

        # Step 1: Download all bio variables
        self.logger.info("Step 1: Downloading bioclimatic variables...")
        download_result = self._download_all_bio(resolution)
        yield download_result

        if download_result['status'] != 'downloaded':
            self.logger.error("Failed to download climate data")
            return

        # Step 2: Get TDWG regions from database
        self.logger.info("Step 2: Loading TDWG regions...")
        tdwg_regions = self._get_tdwg_regions()

        if not tdwg_regions:
            self.logger.error("No TDWG regions found in database")
            yield {'status': 'error', 'error': 'No TDWG regions in database'}
            return

        self.logger.info(f"Found {len(tdwg_regions)} TDWG regions")

        # Step 3: Calculate zonal statistics for each region
        self.logger.info("Step 3: Calculating zonal statistics...")

        processed = 0
        errors = 0

        for tdwg_code, geom_wkt in tdwg_regions:
            try:
                climate_data = self._calculate_zonal_stats(tdwg_code, geom_wkt, resolution)

                if climate_data:
                    # Add derived classifications
                    climate_data = self._add_classifications(climate_data)
                    climate_data['tdwg_code'] = tdwg_code
                    climate_data['resolution'] = resolution

                    if store_db:
                        self._store_climate_data(climate_data)

                    processed += 1
                    yield climate_data

                    if processed % 50 == 0:
                        self.logger.info(f"Processed {processed}/{len(tdwg_regions)} regions")
                else:
                    errors += 1

            except Exception as e:
                self.logger.error(f"Error processing {tdwg_code}: {e}")
                errors += 1

        self.logger.info(f"Completed: {processed} regions processed, {errors} errors")
        yield {
            'status': 'completed',
            'processed': processed,
            'errors': errors,
            'total_regions': len(tdwg_regions)
        }

    def _download_all_bio(self, resolution: str) -> Dict:
        """Download all bioclimatic variables in a single zip."""
        filename = f"wc2.1_{resolution}_bio.zip"
        local_path = os.path.join(self._cache_dir, filename)

        if os.path.exists(local_path):
            self.logger.info(f"Using cached {filename}")
            return {'status': 'downloaded', 'file': filename, 'cached': True}

        url = f"{self.BASE_URL}/{filename}"
        self.logger.info(f"Downloading {url}")

        try:
            response = requests.get(url, stream=True, timeout=1200)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0 and downloaded % (10 * 1024 * 1024) == 0:
                        pct = (downloaded / total_size) * 100
                        self.logger.info(f"Download progress: {pct:.1f}%")

            self.logger.info(f"Downloaded {filename} ({os.path.getsize(local_path) / 1024 / 1024:.1f} MB)")
            return {'status': 'downloaded', 'file': filename, 'cached': False}

        except Exception as e:
            self.logger.error(f"Download failed: {e}")
            return {'status': 'error', 'error': str(e)}

    def _get_tdwg_regions(self) -> List[Tuple[str, str]]:
        """Get all TDWG Level 3 regions with their geometries."""
        query = text("""
            SELECT level3_code, ST_AsText(geom) as geom_wkt
            FROM tdwg_level3
            WHERE geom IS NOT NULL
            ORDER BY level3_code
        """)

        with Session(self.engine) as session:
            result = session.execute(query)
            return result.fetchall()

    def _calculate_zonal_stats(self, tdwg_code: str, geom_wkt: str,
                                resolution: str) -> Optional[Dict]:
        """
        Calculate zonal statistics for all bio variables within a TDWG region.

        Uses rasterstats if available, otherwise falls back to sampling approach.
        """
        try:
            # Try using rasterstats for proper zonal statistics
            return self._zonal_stats_rasterstats(tdwg_code, geom_wkt, resolution)
        except ImportError:
            # Fallback to sampling approach
            return self._zonal_stats_sampling(tdwg_code, geom_wkt, resolution)

    def _zonal_stats_rasterstats(self, tdwg_code: str, geom_wkt: str,
                                  resolution: str) -> Optional[Dict]:
        """Calculate zonal statistics using rasterstats library."""
        try:
            from rasterstats import zonal_stats
            from shapely import wkt
        except ImportError:
            raise ImportError("rasterstats or shapely not installed")

        bio_zip = os.path.join(self._cache_dir, f"wc2.1_{resolution}_bio.zip")
        if not os.path.exists(bio_zip):
            return None

        # Parse geometry
        try:
            geom = wkt.loads(geom_wkt)
            geom_geojson = geom.__geo_interface__
        except Exception as e:
            self.logger.error(f"Error parsing geometry for {tdwg_code}: {e}")
            return None

        climate_data = {}

        with zipfile.ZipFile(bio_zip, 'r') as z:
            for i in range(1, 20):
                var_name = f'bio{i}'
                tif_name = f"wc2.1_{resolution}_bio_{i}.tif"

                if tif_name not in z.namelist():
                    continue

                # Extract TIF to temp location
                z.extract(tif_name, self._cache_dir)
                tif_path = os.path.join(self._cache_dir, tif_name)

                try:
                    stats = zonal_stats(
                        geom_geojson,
                        tif_path,
                        stats=['mean', 'min', 'max', 'count'],
                        nodata=-9999
                    )

                    if stats and stats[0]['count'] > 0:
                        scale = self.BIOCLIM_VARS[var_name]['scale']
                        climate_data[f'{var_name}_mean'] = stats[0]['mean'] * scale
                        climate_data[f'{var_name}_min'] = stats[0]['min'] * scale
                        climate_data[f'{var_name}_max'] = stats[0]['max'] * scale
                        climate_data['pixel_count'] = stats[0]['count']

                finally:
                    # Cleanup extracted file
                    if os.path.exists(tif_path):
                        os.remove(tif_path)

        return climate_data if climate_data else None

    def _zonal_stats_sampling(self, tdwg_code: str, geom_wkt: str,
                               resolution: str) -> Optional[Dict]:
        """
        Fallback: Calculate statistics by sampling points within the region.
        Less accurate but doesn't require rasterstats.
        """
        try:
            import rasterio
            from shapely import wkt
            from shapely.geometry import Point
        except ImportError:
            self.logger.error("rasterio and shapely required for climate extraction")
            return None

        bio_zip = os.path.join(self._cache_dir, f"wc2.1_{resolution}_bio.zip")
        if not os.path.exists(bio_zip):
            return None

        # Parse geometry and get bounding box
        try:
            geom = wkt.loads(geom_wkt)
            bounds = geom.bounds  # (minx, miny, maxx, maxy)
        except Exception as e:
            self.logger.error(f"Error parsing geometry for {tdwg_code}: {e}")
            return None

        # Generate sample points within bounding box
        n_samples = 100
        sample_points = []

        for _ in range(n_samples * 3):  # Generate more points to account for those outside polygon
            lon = np.random.uniform(bounds[0], bounds[2])
            lat = np.random.uniform(bounds[1], bounds[3])
            if geom.contains(Point(lon, lat)):
                sample_points.append((lat, lon))
                if len(sample_points) >= n_samples:
                    break

        if len(sample_points) < 10:
            self.logger.warning(f"Too few sample points for {tdwg_code}: {len(sample_points)}")
            return None

        # Extract values for each bio variable
        climate_data = {}

        with zipfile.ZipFile(bio_zip, 'r') as z:
            for i in range(1, 20):
                var_name = f'bio{i}'
                tif_name = f"wc2.1_{resolution}_bio_{i}.tif"

                if tif_name not in z.namelist():
                    continue

                values = []

                with z.open(tif_name) as tif_file:
                    with rasterio.open(io.BytesIO(tif_file.read())) as src:
                        for lat, lon in sample_points:
                            try:
                                row, col = src.index(lon, lat)
                                value = src.read(1)[row, col]
                                if value != src.nodata and not np.isnan(value):
                                    values.append(value)
                            except (IndexError, ValueError):
                                continue

                if values:
                    scale = self.BIOCLIM_VARS[var_name]['scale']
                    climate_data[f'{var_name}_mean'] = float(np.mean(values)) * scale
                    climate_data[f'{var_name}_min'] = float(np.min(values)) * scale
                    climate_data[f'{var_name}_max'] = float(np.max(values)) * scale

        climate_data['pixel_count'] = len(sample_points)
        return climate_data if climate_data else None

    def _add_classifications(self, climate_data: Dict) -> Dict:
        """Add derived climate classifications (Köppen, Whittaker, Aridity)."""

        bio1 = climate_data.get('bio1_mean')  # Annual mean temp
        bio12 = climate_data.get('bio12_mean')  # Annual precip
        bio5 = climate_data.get('bio5_mean')  # Max temp warmest month
        bio6 = climate_data.get('bio6_mean')  # Min temp coldest month

        # Whittaker biome classification
        if bio1 is not None and bio12 is not None:
            climate_data['whittaker_biome'] = self._classify_whittaker(bio1, bio12)

        # Köppen climate classification (simplified)
        if bio1 is not None and bio12 is not None and bio6 is not None:
            climate_data['koppen_zone'] = self._classify_koppen(
                bio1, bio12, bio5, bio6
            )

        # Aridity index: AI = P / (T + 10) * 10
        # Higher = more humid, Lower = more arid
        if bio1 is not None and bio12 is not None and bio1 > -10:
            climate_data['aridity_index'] = bio12 / (bio1 + 10) * 10

        return climate_data

    def _classify_whittaker(self, temp: float, precip: float) -> str:
        """Classify biome using Whittaker diagram logic."""
        if temp < -5:
            return 'Tundra'
        elif temp < 5:
            if precip < 250:
                return 'Cold Desert'
            else:
                return 'Boreal Forest'
        elif temp < 15:
            if precip < 300:
                return 'Cold Desert'
            elif precip < 750:
                return 'Temperate Grassland'
            else:
                return 'Temperate Forest'
        elif temp < 20:
            if precip < 300:
                return 'Hot Desert'
            elif precip < 750:
                return 'Subtropical Grassland'
            elif precip < 1500:
                return 'Subtropical Forest'
            else:
                return 'Temperate Rainforest'
        else:
            if precip < 250:
                return 'Hot Desert'
            elif precip < 750:
                return 'Tropical Savanna'
            elif precip < 1500:
                return 'Tropical Seasonal Forest'
            else:
                return 'Tropical Rainforest'

    def _classify_koppen(self, mean_temp: float, annual_precip: float,
                         max_temp: Optional[float], min_temp: float) -> str:
        """
        Simplified Köppen climate classification.
        Returns main group (A, B, C, D, E) + subtype.
        """
        # E: Polar climates
        if max_temp is not None and max_temp < 10:
            if max_temp < 0:
                return 'EF'  # Ice cap
            return 'ET'  # Tundra

        # B: Arid climates (simplified threshold)
        # Threshold depends on temperature and precipitation pattern
        threshold = mean_temp * 20 + 280  # Simplified formula
        if annual_precip < threshold:
            if annual_precip < threshold / 2:
                return 'BWh' if mean_temp >= 18 else 'BWk'  # Desert
            return 'BSh' if mean_temp >= 18 else 'BSk'  # Steppe

        # A: Tropical climates
        if min_temp >= 18:
            if annual_precip >= 2500:
                return 'Af'  # Tropical rainforest
            return 'Am'  # Tropical monsoon/savanna

        # D: Continental climates
        if min_temp < -3:
            if min_temp < -38:
                return 'Dfd'  # Extreme continental
            return 'Dfb'  # Humid continental

        # C: Temperate climates
        if min_temp >= -3 and min_temp < 18:
            if annual_precip > 1500:
                return 'Cfa'  # Humid subtropical
            return 'Cfb'  # Oceanic

        return 'Cf'  # Default temperate

    def _store_climate_data(self, climate_data: Dict) -> bool:
        """Store climate data in the database."""

        # Build column lists dynamically
        columns = ['tdwg_code', 'resolution', 'pixel_count']
        values = [
            climate_data.get('tdwg_code'),
            climate_data.get('resolution'),
            climate_data.get('pixel_count')
        ]

        # Add all bio variables
        for i in range(1, 20):
            var = f'bio{i}'
            if f'{var}_mean' in climate_data:
                columns.append(f'{var}_mean')
                values.append(climate_data[f'{var}_mean'])

            # Only store min/max for bio1 and bio12 (temp and precip)
            if i in [1, 12]:
                if f'{var}_min' in climate_data:
                    columns.append(f'{var}_min')
                    values.append(climate_data[f'{var}_min'])
                if f'{var}_max' in climate_data:
                    columns.append(f'{var}_max')
                    values.append(climate_data[f'{var}_max'])

        # Add classifications
        for field in ['koppen_zone', 'whittaker_biome', 'aridity_index']:
            if field in climate_data and climate_data[field] is not None:
                columns.append(field)
                values.append(climate_data[field])

        # Build upsert query with named parameters
        placeholders = ', '.join([f':{col}' for col in columns])
        col_names = ', '.join(columns)
        update_clause = ', '.join([
            f'{col} = EXCLUDED.{col}' for col in columns if col != 'tdwg_code'
        ])

        query = text(f"""
            INSERT INTO tdwg_climate ({col_names})
            VALUES ({placeholders})
            ON CONFLICT (tdwg_code) DO UPDATE SET
            {update_clause},
            updated_at = CURRENT_TIMESTAMP
        """)

        try:
            # Build params dict
            params = dict(zip(columns, values))

            with Session(self.engine) as session:
                session.execute(query, params)
                session.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error storing climate data: {e}")
            return False

    def transform(self, raw_data: Dict) -> Dict:
        """Transform is handled during zonal stats calculation."""
        return raw_data

    def validate(self, data: Dict) -> bool:
        """Validate climate data record."""
        if data.get('status') in ['downloaded', 'completed', 'error']:
            return True
        return 'tdwg_code' in data and 'bio1_mean' in data

    def get_climate_for_coords(self, lat: float, lon: float,
                               resolution: str = '10m') -> Dict[str, float]:
        """
        Extract all bio variable values for a coordinate.

        Args:
            lat: Latitude
            lon: Longitude
            resolution: Data resolution

        Returns:
            Dict of all bioclimatic variable values
        """
        try:
            import rasterio
        except ImportError:
            self.logger.error("rasterio not installed. Install with: pip install rasterio")
            return {}

        climate_data = {}

        bio_zip = os.path.join(self._cache_dir, f"wc2.1_{resolution}_bio.zip")
        if not os.path.exists(bio_zip):
            self.logger.warning("Climate data not downloaded. Run crawler first.")
            return {}

        try:
            with zipfile.ZipFile(bio_zip, 'r') as z:
                for i in range(1, 20):
                    var_name = f'bio{i}'
                    tif_name = f"wc2.1_{resolution}_bio_{i}.tif"

                    if tif_name not in z.namelist():
                        continue

                    with z.open(tif_name) as tif_file:
                        with rasterio.open(io.BytesIO(tif_file.read())) as src:
                            row, col = src.index(lon, lat)
                            value = src.read(1)[row, col]

                            if value != src.nodata and not np.isnan(value):
                                scale = self.BIOCLIM_VARS[var_name]['scale']
                                climate_data[var_name] = float(value) * scale

        except Exception as e:
            self.logger.error(f"Error extracting climate data: {e}")

        # Add classifications
        if climate_data:
            climate_data = self._add_classifications(climate_data)

        return climate_data

    def get_climate_for_species(self, species_id: int) -> Dict[str, Any]:
        """
        Get climate envelope for a species based on its TDWG distribution.

        Args:
            species_id: Species ID from database

        Returns:
            Dict with climate statistics across all distribution regions
        """
        query = text("""
            SELECT
                c.bio1_mean, c.bio1_min, c.bio1_max,
                c.bio12_mean, c.bio12_min, c.bio12_max,
                c.whittaker_biome, c.koppen_zone, c.aridity_index
            FROM species_distribution sd
            JOIN tdwg_climate c ON sd.tdwg_code = c.tdwg_code
            WHERE sd.species_id = :species_id AND sd.native = TRUE
        """)

        with Session(self.engine) as session:
            result = session.execute(query, {'species_id': species_id})
            rows = result.fetchall()

        if not rows:
            return {}

        # Aggregate climate data across all native regions
        temps = [r[0] for r in rows if r[0] is not None]
        precips = [r[3] for r in rows if r[3] is not None]
        biomes = [r[6] for r in rows if r[6] is not None]
        koppens = [r[7] for r in rows if r[7] is not None]

        result = {
            'n_regions': len(rows),
        }

        if temps:
            result['temp_mean'] = float(np.mean(temps))
            result['temp_min'] = float(min(r[1] for r in rows if r[1] is not None))
            result['temp_max'] = float(max(r[2] for r in rows if r[2] is not None))

        if precips:
            result['precip_mean'] = float(np.mean(precips))
            result['precip_min'] = float(min(r[4] for r in rows if r[4] is not None))
            result['precip_max'] = float(max(r[5] for r in rows if r[5] is not None))

        if biomes:
            from collections import Counter
            result['biomes'] = dict(Counter(biomes))

        if koppens:
            from collections import Counter
            result['koppen_zones'] = dict(Counter(koppens))

        return result

    def list_cached_data(self) -> list:
        """List all cached WorldClim data files."""
        if not os.path.exists(self._cache_dir):
            return []

        files = []
        for f in os.listdir(self._cache_dir):
            if f.endswith('.zip'):
                path = os.path.join(self._cache_dir, f)
                size_mb = os.path.getsize(path) / (1024 * 1024)
                files.append({
                    'filename': f,
                    'size_mb': round(size_mb, 2)
                })

        return files

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of stored climate data."""
        query = text("""
            SELECT
                COUNT(*) as total_regions,
                COUNT(bio1_mean) as with_temperature,
                COUNT(bio12_mean) as with_precipitation,
                COUNT(whittaker_biome) as with_biome,
                COUNT(koppen_zone) as with_koppen,
                AVG(bio1_mean) as avg_temp,
                AVG(bio12_mean) as avg_precip
            FROM tdwg_climate
        """)

        biome_query = text("""
            SELECT whittaker_biome, COUNT(*)
            FROM tdwg_climate
            WHERE whittaker_biome IS NOT NULL
            GROUP BY whittaker_biome
            ORDER BY COUNT(*) DESC
        """)

        with Session(self.engine) as session:
            row = session.execute(query).fetchone()
            biomes = session.execute(biome_query).fetchall()

        return {
            'total_regions': row[0],
            'with_temperature': row[1],
            'with_precipitation': row[2],
            'with_biome': row[3],
            'with_koppen': row[4],
            'avg_temp_celsius': round(row[5], 1) if row[5] else None,
            'avg_precip_mm': round(row[6], 1) if row[6] else None,
            'biome_distribution': dict(biomes) if biomes else {}
        }
