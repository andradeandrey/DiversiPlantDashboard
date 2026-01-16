"""WorldClim climate data crawler."""
from typing import Generator, Dict, Any, Tuple, Optional
import requests
import os
import tempfile
import zipfile
import io
from .base import BaseCrawler


class WorldClimCrawler(BaseCrawler):
    """
    Crawler for WorldClim climate data.

    Source: https://www.worldclim.org
    Data: Bioclimatic variables (BIO1-BIO19), temperature, precipitation
    Resolution: 30s (~1km), 2.5m, 5m, 10m
    """

    name = 'worldclim'

    BASE_URL = 'https://biogeo.ucdavis.edu/data/worldclim/v2.1/base'

    # Bioclimatic variables
    BIOCLIM_VARS = {
        'bio1': 'Annual Mean Temperature',
        'bio2': 'Mean Diurnal Range',
        'bio3': 'Isothermality',
        'bio4': 'Temperature Seasonality',
        'bio5': 'Max Temperature of Warmest Month',
        'bio6': 'Min Temperature of Coldest Month',
        'bio7': 'Temperature Annual Range',
        'bio8': 'Mean Temperature of Wettest Quarter',
        'bio9': 'Mean Temperature of Driest Quarter',
        'bio10': 'Mean Temperature of Warmest Quarter',
        'bio11': 'Mean Temperature of Coldest Quarter',
        'bio12': 'Annual Precipitation',
        'bio13': 'Precipitation of Wettest Month',
        'bio14': 'Precipitation of Driest Month',
        'bio15': 'Precipitation Seasonality',
        'bio16': 'Precipitation of Wettest Quarter',
        'bio17': 'Precipitation of Driest Quarter',
        'bio18': 'Precipitation of Warmest Quarter',
        'bio19': 'Precipitation of Coldest Quarter',
    }

    def __init__(self, db_url: str):
        super().__init__(db_url)
        self._cache_dir = os.path.join(tempfile.gettempdir(), 'worldclim_cache')
        os.makedirs(self._cache_dir, exist_ok=True)
        self._raster_data = {}

    def fetch_data(self, mode='incremental', **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch WorldClim climate data.

        This crawler downloads raster data and stores metadata.
        Actual climate values are extracted on-demand for coordinates.

        Args:
            mode: 'full' or 'incremental'
            **kwargs: Additional parameters

        Yields:
            Metadata about downloaded layers
        """
        resolution = kwargs.get('resolution', '10m')
        variables = kwargs.get('variables', ['bio'])

        self.logger.info(f"Fetching WorldClim data at {resolution} resolution")

        for var in variables:
            try:
                self._download_variable(var, resolution)
                yield {
                    'variable': var,
                    'resolution': resolution,
                    'status': 'downloaded'
                }
            except Exception as e:
                self.logger.error(f"Error downloading {var}: {e}")
                yield {
                    'variable': var,
                    'resolution': resolution,
                    'status': 'error',
                    'error': str(e)
                }

    def _download_variable(self, variable: str, resolution: str):
        """Download a WorldClim variable."""
        filename = f"wc2.1_{resolution}_{variable}.zip"
        local_path = os.path.join(self._cache_dir, filename)

        if os.path.exists(local_path):
            self.logger.info(f"Using cached {filename}")
            return

        url = f"{self.BASE_URL}/{filename}"
        self.logger.info(f"Downloading {url}")

        response = requests.get(url, stream=True, timeout=600)
        response.raise_for_status()

        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        self.logger.info(f"Downloaded {filename}")

    def transform(self, raw_data: Dict) -> Dict:
        """Transform is not applicable for raster data."""
        return raw_data

    def validate(self, data: Dict) -> bool:
        """Validate download status."""
        return data.get('status') == 'downloaded'

    def get_climate_for_coords(self, lat: float, lon: float,
                               resolution: str = '10m') -> Dict[str, float]:
        """
        Extract climate values for a coordinate.

        Args:
            lat: Latitude
            lon: Longitude
            resolution: Data resolution

        Returns:
            Dict of bioclimatic variable values
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
                    tif_name = f"wc2.1_{resolution}_{var_name}.tif"

                    if tif_name not in z.namelist():
                        continue

                    # Extract and read the TIF
                    with z.open(tif_name) as tif_file:
                        with rasterio.open(io.BytesIO(tif_file.read())) as src:
                            # Get value at coordinates
                            row, col = src.index(lon, lat)
                            value = src.read(1)[row, col]

                            # Handle nodata
                            if value != src.nodata:
                                climate_data[var_name] = float(value)

        except Exception as e:
            self.logger.error(f"Error extracting climate data: {e}")

        return climate_data

    def get_biome_from_climate(self, climate_data: Dict) -> Optional[str]:
        """
        Estimate biome from climate data using Whittaker diagram logic.

        Args:
            climate_data: Dict with bio1 (temp) and bio12 (precip)

        Returns:
            Estimated biome name
        """
        temp = climate_data.get('bio1')  # Annual mean temp (degC * 10)
        precip = climate_data.get('bio12')  # Annual precipitation (mm)

        if temp is None or precip is None:
            return None

        # Convert temperature (WorldClim stores as degC * 10)
        temp = temp / 10 if abs(temp) > 100 else temp

        # Simplified Whittaker classification
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
