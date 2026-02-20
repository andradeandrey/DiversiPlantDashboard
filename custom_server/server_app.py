import os
import json
import numpy as np
import pandas as pd
from pathlib import Path
from shinywidgets import render_widget
from shiny import render, ui, reactive
import plotly.graph_objects as go
from custom_server.agroforestry_server import open_csv, get_Plants
import logging
import geopandas as gpd
import folium
from folium import plugins
try:
    from rpy2.robjects.conversion import localconverter
    from rpy2 import robjects
    from rpy2.robjects.packages import importr
    from rpy2.robjects.vectors import StrVector
    import rpy2.robjects.packages as rpackages, data
    from rpy2.robjects import r, pandas2ri
    HAS_RPY2 = True
except ImportError:
    HAS_RPY2 = False
    logging.warning("[INIT] rpy2 not available — GIFT database mode disabled")
from collections import Counter


FILE_NAME = os.path.join(Path(__file__).parent.parent,"data","MgmtTraitData_updated.csv")
# FILE_NAME = os.path.join(Path(__file__).parent.parent,"data","practitioners.csv")

# Ecoregion shapefile path — loaded on demand only as DB fallback (saves ~500MB RAM)
_ECOREGION_SHP_PATH = os.path.join(Path(__file__).parent.parent, "data", "ecoregions_raster", "Ecoregions2017.shp")
_ECOREGION_GDF_CACHE = {"gdf": None}


COLOR = {'herb': '#d77d28', 'forb': '#d77d28', 'climber': '#cc4fb9', 'subshrub': '#612e14', 'shrub': '#0095c6', 'cactus': '#49d1d5', 'bamboo': '#fd2f6d', 'tree': '#2a43d1', 'palm': '#63a355', 'graminoid': '#633096', 'liana': '#be2843', 'vine': '#cc4fb9', 'scrambler': '#017201', 'other': '#171717'}

STRATUM = [0,1,[[0,4,9],{2:"Baixo", 6.5:"Alto"}],
            [[0,3,6,9],{1.5:"Baixo", 4.5:"Médio", 7.5:"Alto"}],
            [[0,3,5,7,9],{1.5:"Baixo", 4:"Médio", 6:"Alto", 8:"Emergente"}],
            [[0,2,4,6,7,9],{1:"Rasteiro", 3:"Baixo", 5:"Médio", 6.5:"Alto", 8:"Emergente"}],
            [[0,2,4,6,7,8,9],{1:"Rasteiro", 3:"Baixo", 5:"Médio", 6.5:"Alto",7.5:"Alto-Emergente", 8.5:"Emergente"}],
            [[0,2,4,5,6,7,8,9],{1:"Rasteiro", 3:"Baixo", 4.5:"Médio", 5.5:"Médio-Alto", 6.5:"Alto", 7.5:"Alto-Emergente", 8.5:"Emergente"}],
            [[0,2,3,4,5,6,7,8,9],{1:"Rasteiro", 2.5:"Baixo", 3.5:"Baixo-Médio", 4.5:"Médio", 5.5:"Médio-Alto", 6.5:"Alto", 7.5:"Alto-Emergente", 8.5:"Emergente"}],
            [[0,1,2,3,4,5,6,7,8,9],{0.5: "Rasteiro",1.5: "Rasteiro-Baixo",2.5: "Baixo",3.5: "Baixo-Médio",4.5: "Médio",5.5: "Médio-Alto",6.5: "Alto",7.5: "Alto-Emergente",8.5: "Emergente"}]]

FLORISTIC_GROUP = {"Native": 'native', "Endemic":'endemic_list', "Naturalized":'naturalized',  "All Species":'all'}

# PT-BR display names for results table columns (Figma match)
COLUMN_DISPLAY_NAMES = {
    'common_en': 'Nome científico',
    'growth_form': 'Forma de crescimento',
    'plant_max_height': 'Altura máxima (m)',
    'stratum': 'Estrato (demanda de luz)',
    'family': 'Família',
    'function': 'Função',
    'yrs_ini_prod': 'Prod. inicial (anos)',
    'life_hist': 'História de vida',
    'longev_prod': 'Long. produtiva (anos)',
    'threat_status': 'Ameaça à conservação',
    'ref': 'Referência',
}

# Numeric columns that should be center-aligned in results table
_NUMERIC_COLS = {'plant_max_height', 'yrs_ini_prod', 'longev_prod'}


def _render_results_table(df, columns):
    """Build a custom HTML table matching the Figma design.

    Features: zebra striping, PT-BR headers, sort icons, column-remove
    buttons, scientific-name links.
    """
    import html as _html

    header_cells = []
    for col in columns:
        display = COLUMN_DISPLAY_NAMES.get(col, col.replace('_', ' ').title())
        display_esc = _html.escape(display)
        col_esc = _html.escape(col)
        header_cells.append(
            f'<th>'
            f'<span class="th-sort" data-col="{col_esc}" title="Ordenar">&#9671;</span> '
            f'{display_esc} '
            f'<span class="th-remove" data-col="{col_esc}" title="Remover coluna"'
            f' onclick="var cb=document.querySelector(\'input[value=&quot;{col_esc}&quot;]\');if(cb)cb.click();"'
            f'>&times;</span>'
            f'</th>'
        )

    rows = []
    for _, row in df.iterrows():
        cells = []
        for col in columns:
            val = row[col]
            val_str = _html.escape(str(val))
            td_class = ' class="text-center"' if col in _NUMERIC_COLS else ''
            if col == 'common_en':
                cells.append(f'<td{td_class}><span class="sci-link">{val_str}</span></td>')
            else:
                cells.append(f'<td{td_class}>{val_str}</td>')
        rows.append('<tr>' + ''.join(cells) + '</tr>')

    sort_js = """
<script>
(function(){
  document.querySelectorAll('.results-table .th-sort').forEach(function(el){
    el.addEventListener('click', function(){
      var table = el.closest('table');
      var colIdx = Array.from(el.closest('tr').children).indexOf(el.closest('th'));
      var tbody = table.querySelector('tbody');
      var rows = Array.from(tbody.querySelectorAll('tr'));
      var asc = el.dataset.asc !== '1';
      el.dataset.asc = asc ? '1' : '0';
      rows.sort(function(a,b){
        var av = a.children[colIdx].textContent.trim();
        var bv = b.children[colIdx].textContent.trim();
        var an = parseFloat(av), bn = parseFloat(bv);
        if(!isNaN(an) && !isNaN(bn)) return asc ? an-bn : bn-an;
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      });
      rows.forEach(function(r){ tbody.appendChild(r); });
    });
  });
})();
</script>"""

    return (
        '<table class="results-table">'
        '<thead><tr>' + ''.join(header_cells) + '</tr></thead>'
        '<tbody>' + ''.join(rows) + '</tbody>'
        '</table>'
        + sort_js
    )

SPECIES_GIFT_DATAFRAME = pd.DataFrame()

growth_forms = ['bamboo', 'cactus', 'climber', 'herb', 'palm', 'shrub', 'subshrub', 'tree']
colors = ['#fd2f6d', '#49d1d5', '#cc4fb9', '#d77d28', '#63a355', '#0095c6', '#612e14', '#2a43d1']
color_mapping = dict(zip(growth_forms, colors))

# ECharts path:// symbols — same paths as badge SVGs (_GF_SVGS in tab_03_species.py)
# Elements converted: ellipse→arc, rect→L, line→rect, H→L, V→L
ECHARTS_PATHS = {
    # viewBox 0 0 10 20: ellipse(arc) + trunk(rect)
    'tree':      'path://M1,5.5 A4,5 0 1,0 9,5.5 A4,5 0 1,0 1,5.5 Z M4.2,10.5 L5.8,10.5 L5.8,20 L4.2,20 Z',
    # viewBox 0 0 9.5 9: pentagon (H→L)
    'shrub':     'path://M8.688 3.575L7.153 8.302L2.182 8.302L0.646 3.575L4.668 0.653L8.688 3.575Z',
    # viewBox 0 0 16 16: square (rect→L)
    'subshrub':  'path://M2,2 L14,2 L14,14 L2,14 Z',
    # viewBox 0 0 13.9 12.4: rounded triangle (H→L)
    'forb':      'path://M6.929 0.65C7.161 0.65 7.376 0.774 7.492 0.975L13.122 10.725C13.238 10.926 13.238 11.174 13.122 11.375C13.005 11.576 12.79 11.7 12.558 11.7L1.3 11.7C1.068 11.7 0.853 11.576 0.737 11.375C0.621 11.174 0.621 10.926 0.737 10.725L6.367 0.975L6.415 0.904C6.537 0.745 6.726 0.65 6.929 0.65Z',
    'herb':      'path://M6.929 0.65C7.161 0.65 7.376 0.774 7.492 0.975L13.122 10.725C13.238 10.926 13.238 11.174 13.122 11.375C13.005 11.576 12.79 11.7 12.558 11.7L1.3 11.7C1.068 11.7 0.853 11.576 0.737 11.375C0.621 11.174 0.621 10.926 0.737 10.725L6.367 0.975L6.415 0.904C6.537 0.745 6.726 0.65 6.929 0.65Z',
    # viewBox 0 0 4 16: thin bar (rect→L)
    'graminoid': 'path://M1,0 L3,0 L3,16 L1,16 Z',
    # viewBox 0 0 13.74 22: trident (3 open strokes — rendered via borderColor)
    'palm':      'path://M6.867,1 L6.867,21 M1,1 L6.867,12 M12.734,1 L6.867,12',
    # viewBox 0 0 14 16: V chevron (open stroke)
    'bamboo':    'path://M1,2 L7,14 L13,2',
    # viewBox 0 0 5.18 22: vertical wave (Figma path)
    'liana':     'path://M1.1 1C1.075 1.32 0.993 1.523 1.233 1.728C1.388 1.86 1.56 1.975 1.735 2.083C2.1 2.308 2.485 2.498 2.84 2.74C4.395 3.803 4.325 4.81 2.835 5.85C2.573 6.173 2.183 6.43 1.735 6.758C1.295 7.083 1.153 7.423 1.368 7.898C1.695 8.63 2.335 8.945 3.055 9.44C4.203 10.228 4.275 11.455 3.043 12.198C2.508 12.52 1.933 12.823 1.428 13.16C0.593 13.718 0.598 14.385 1.428 14.95C1.835 15.228 2.33 15.458 2.735 15.735C4.285 16.795 4.483 17.973 2.64 19.028C2.228 19.263 1.803 19.493 1.428 19.748C0.853 20.138 0.675 20.578 0.9 21',
    # viewBox -0.2 0 4.8 11: coil/tendril (Figma path, V→L)
    'vine':      'path://M0.786 0.5C1.714 0.491 3.057 0.695 3.528 1.72C3.817 2.347 3.784 3.071 3.581 3.722L3.557 3.753L3.557 3.735C3.275 2.944 2.75 2.573 2.319 2.4C1.777 2.181 1.031 2.32 0.661 2.839C0.514 3.045 0.476 3.306 0.514 3.562C0.637 4.378 1.198 4.649 1.198 4.649C1.198 4.649 2.105 5.193 2.84 4.649C3.221 4.367 3.437 4.012 3.556 3.735L3.55 3.716C4.016 4.782 4.127 6.316 3.67 7.313L3.556 7.375C3.436 7.652 3.278 7.961 2.897 8.244C2.162 8.787 1.255 8.244 1.255 8.244C1.255 8.244 0.694 7.972 0.571 7.156C0.533 6.9 0.571 6.639 0.718 6.433C1.088 5.914 1.834 5.776 2.377 5.994C2.807 6.167 3.332 6.539 3.614 7.329L3.67 7.438C3.872 8.089 3.874 8.653 3.586 9.28C3.114 10.305 1.772 10.509 0.843 10.5',
    'climber':   'path://M0.786 0.5C1.714 0.491 3.057 0.695 3.528 1.72C3.817 2.347 3.784 3.071 3.581 3.722L3.557 3.753L3.557 3.735C3.275 2.944 2.75 2.573 2.319 2.4C1.777 2.181 1.031 2.32 0.661 2.839C0.514 3.045 0.476 3.306 0.514 3.562C0.637 4.378 1.198 4.649 1.198 4.649C1.198 4.649 2.105 5.193 2.84 4.649C3.221 4.367 3.437 4.012 3.556 3.735L3.55 3.716C4.016 4.782 4.127 6.316 3.67 7.313L3.556 7.375C3.436 7.652 3.278 7.961 2.897 8.244C2.162 8.787 1.255 8.244 1.255 8.244C1.255 8.244 0.694 7.972 0.571 7.156C0.533 6.9 0.571 6.639 0.718 6.433C1.088 5.914 1.834 5.776 2.377 5.994C2.807 6.167 3.332 6.539 3.614 7.329L3.67 7.438C3.872 8.089 3.874 8.653 3.586 9.28C3.114 10.305 1.772 10.509 0.843 10.5',
    # viewBox 0 0 22 5.18: horizontal wave (Figma path)
    'scrambler': 'path://M21 4.08C20.578 4.305 20.138 4.127 19.748 3.552C19.493 3.177 19.263 2.752 19.028 2.34C17.973 0.497 16.795 0.695 15.735 2.245C15.458 2.65 15.228 3.145 14.95 3.552C14.385 4.382 13.718 4.387 13.16 3.552C12.823 3.047 12.52 2.472 12.198 1.937C11.455 0.705 10.228 0.777 9.44 1.925C8.945 2.645 8.63 3.685 7.898 4.012C7.423 4.227 7.083 4.085 6.758 3.645C6.43 3.197 6.173 2.607 5.85 2.145C4.81 0.655 3.803 0.585 2.74 2.14C2.498 2.495 2.308 2.88 2.083 3.245C1.975 3.42 1.86 3.592 1.728 3.747C1.523 3.987 1.32 4.132 1 4.157',
    # viewBox 0 0 16 16: circle(arc) + diagonal
    'cactus':    'path://M2,1 L14,1 L14,15 L2,15 Z',
    'other':     'path://M2,8 A6,6 0 1,0 14,8 A6,6 0 1,0 2,8 Z M4,4 L12,12',
}

# Raw path data (without path:// prefix) for ECharts graphic elements
ECHARTS_PATH_DATA = {k: v.replace('path://', '') for k, v in ECHARTS_PATHS.items()}

# Per-growth-form [width, height] matching each SVG's viewBox aspect ratio
ECHARTS_SYMBOL_SIZE = {
    'tree':      [7, 14],
    'shrub':     [13, 12],
    'subshrub':  [12, 12],
    'forb':      [14, 12],
    'herb':      [14, 12],
    'graminoid': [4, 16],
    'palm':      [9, 14],
    'bamboo':    [13, 10],
    'liana':     [5, 18],
    'vine':      [8, 18],
    'climber':   [8, 18],
    'scrambler': [22, 7],
    'other':     [12, 12],
}
_DEFAULT_SYMBOL_SIZE = 14

# Shapes rendered as stroke-only (open paths or outlines): color=none, borderColor=gf_color
# Closed filled shapes (pentagon, triangle, square, bar): color=gf_color
_GF_STROKE_ONLY = {'tree', 'palm', 'bamboo', 'liana', 'vine', 'climber', 'scrambler', 'other'}


def _gf_item_style(growth_type: str, color: str) -> dict:
    return {'color': 'none', 'borderColor': color, 'borderWidth': 2}


def sqrt_transform(x):
    """Real years → sqrt-space for plotting."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return x
    return np.sqrt(max(0, float(x)))


def sqrt_inverse(sx):
    """Sqrt-space → real years."""
    return sx * sx


def echarts_html(option: dict, chart_id: str, height: int = 700, post_init_js: str = "") -> str:
    """Render an ECharts option dict as an HTML div + script."""
    option_json = json.dumps(option, ensure_ascii=False)
    # Replace JS function placeholders: "__JS__<code>__JSEND__"
    import re
    option_json = re.sub(
        r'"__JS__(.*?)__JSEND__"',
        lambda m: m.group(1).replace('\\"', '"'),
        option_json,
    )
    return f"""
    <div id="{chart_id}" style="width:100%;height:{height}px;"></div>
    <script>
    (function() {{
        var el = document.getElementById('{chart_id}');
        if (!el) return;
        if (el._ec) {{ el._ec.dispose(); el._ec = null; }}
        var chart = echarts.init(el);
        el._ec = chart;
        chart.setOption({option_json});
        new ResizeObserver(function() {{ chart.resize(); }}).observe(el);
        {post_init_js}
    }})();
    </script>
    """


def parse_lat_lon(lat_lon_str):
    """
    Parses a string containing latitude and longitude (e.g., 'lat,lon').

    Args:
        lat_lon_str (str): Input string in the format 'lat,lon'.

    Returns:
        tuple: (latitude, longitude) as floats.
    """
    try:
        # Split the string on ',' and remove any surrounding whitespace
        lat, lon = map(str.strip, lat_lon_str.split(","))
        return float(lat), float(lon)
    except (ValueError, AttributeError):
        # Handle invalid input
        raise ValueError("Invalid input. Please enter coordinates in the format 'latitude,longitude'.")

def server_app(input,output,session):
## Homepage
    # @reactive.event(input.begin)
    # def _():
    #     reactive.set_value("homepage_content", "location")
    
##Location

    #This function creates the world map and update it if you click on "Update map"
    @output
    @render.ui
    @reactive.event(input.update_map, ignore_none=None)
    def world_map():
        # Default center of the map (e.g., equatorial region)
        default_center = [20, 0]

        # Initialize Folium map with satellite tiles
        world_map = folium.Map(
            location=default_center,
            zoom_start=2  # Set an appropriate zoom level
        )
        # Add Google Maps layer with labels (default — best for navigation)
        folium.TileLayer(
            tiles="https://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
            attr="Map data &copy; Google",
            name="Google Maps",
            subdomains=["mt0", "mt1", "mt2", "mt3"],
        ).add_to(world_map)

        # Add OpenStreetMap layer
        folium.TileLayer("OpenStreetMap").add_to(world_map)

        # Add Satellite + Labels (hybrid) layer
        folium.TileLayer(
            tiles="https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
            attr="Map data &copy; Google",
            name="Satellite",
            subdomains=["mt0", "mt1", "mt2", "mt3"],
        ).add_to(world_map)
        # If the user provides latitude and longitude input
        if input.longitude_latitude() != "":
            try:
                # Parse the user input
                lat, lon = parse_lat_lon(input.longitude_latitude())

                # Add a red marker for the user-provided coordinates
                folium.Marker(
                    location=[lat, lon],
                    popup=f"Lat: {lat}, Lon: {lon}",
                    icon=folium.Icon(color="red", icon="info-sign")
                ).add_to(world_map)

                # Center the map on the provided coordinates
                world_map.location = [lat, lon]
                world_map.zoom_start = 20  # Adjust zoom for closer view
            except ValueError as e:
                print(f"Error parsing coordinates: {e}")

        # Add layer control, scale bar, fullscreen and locate buttons
        folium.LayerControl(collapsed=True).add_to(world_map)
        folium.plugins.Fullscreen().add_to(world_map)
        folium.plugins.LocateControl(auto_start=False).add_to(world_map)

        # Click-to-place pin: JS that removes old markers, places new one, updates input
        click_js = folium.Element("""
        <script>
        (function() {
            var mapEl = document.querySelector('.folium-map');
            if (!mapEl || !mapEl._leaflet_id) {
                setTimeout(arguments.callee, 300);
                return;
            }
            var map = null;
            for (var key in mapEl) {
                if (mapEl[key] instanceof L.Map) { map = mapEl[key]; break; }
            }
            if (!map) {
                map = Object.values(window).find(function(v) { return v instanceof L.Map; });
            }
            if (!map) return;

            var clickMarker = null;
            map.on('click', function(e) {
                var lat = e.latlng.lat.toFixed(6);
                var lon = e.latlng.lng.toFixed(6);
                var coords = lat + ', ' + lon;

                // Remove ALL existing markers
                map.eachLayer(function(layer) {
                    if (layer instanceof L.Marker) {
                        map.removeLayer(layer);
                    }
                });

                // Place new marker
                clickMarker = L.marker(e.latlng, {
                    icon: L.icon({
                        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
                        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
                        iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41]
                    })
                }).addTo(map);
                clickMarker.bindPopup('Lat: ' + lat + ', Lon: ' + lon).openPopup();

                // Access parent document (map runs inside iframe)
                var parentDoc = window.parent.document;
                var parentShiny = window.parent.Shiny;
                var input = parentDoc.getElementById('longitude_latitude');
                if (input) {
                    input.value = coords;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                }
                if (parentShiny) {
                    parentShiny.setInputValue('longitude_latitude', coords);
                    setTimeout(function(){
                        parentShiny.setInputValue('update_map', Math.random(), {priority:'event'});
                    }, 200);
                }
            });
        })();
        </script>
        """)
        world_map.get_root().html.add_child(click_js)

        # Return the Folium map as raw HTML
        return ui.HTML(world_map._repr_html_())

    # Location badge in navbar (Figma: green pill showing current location)
    @render.ui
    @reactive.event(input.update_map)
    def location_badge():
        coords = input.longitude_latitude()
        if not coords or not coords.strip():
            return ui.span()
        try:
            lat, lon = parse_lat_lon(coords)
            label = f"{lat:.2f}, {lon:.2f}"
        except Exception:
            label = coords.strip()
        return ui.span(
            ui.span("\U0001F4CD ", style="margin-right: 2px;"),
            label,
            class_="badge",
            style="background-color: #6cb043; color: white; font-size: 0.8em; "
                  "padding: 5px 12px; border-radius: 20px; font-weight: 500;",
        )


##Climate

    # --- Ecoregion lookup (WWF Ecoregions 2017) ---
    def _load_ecoregions():
        """Return ecoregion GeoDataFrame from preloaded cache or load on demand."""
        gdf = _ECOREGION_GDF_CACHE.get("gdf")
        if gdf is not None:
            return gdf
        # Fallback: load synchronously if preload hasn't finished yet
        logging.info("[ECO] Cache miss — loading shapefile synchronously")
        gdf = gpd.read_file(_ECOREGION_SHP_PATH)
        _ = gdf.sindex
        _ECOREGION_GDF_CACHE["gdf"] = gdf
        return gdf

    def _find_ecoregion_at_point(lat, lon):
        """Fast spatial lookup: returns single-row GeoDataFrame or None."""
        from shapely.geometry import Point
        gdf = _load_ecoregions()
        pt = Point(lon, lat)
        # Use spatial index for O(log n) candidate lookup
        candidates = gdf.sindex.query(pt, predicate="intersects")
        if len(candidates) == 0:
            return None
        matches = gdf.iloc[candidates]
        exact = matches[matches.geometry.contains(pt)]
        if exact.empty:
            return None
        return exact.iloc[[0]]

    # Map WWF BIOME_NAME → UI biome key
    _BIOME_NAME_TO_UI = {
        "Tropical & Subtropical Moist Broadleaf Forests": "Tropical & Subtropical Moist Broadleaf Forests",
        "Tropical & Subtropical Dry Broadleaf Forests": "Tropical & Subtropical Dry Broadleaf Forests",
        "Tropical & Subtropical Coniferous Forests": "Temperate Conifer Forests",
        "Temperate Broadleaf & Mixed Forests": "Temperate Broadleaf & Mixed Forests",
        "Temperate Conifer Forests": "Temperate Conifer Forests",
        "Boreal Forests/Taiga": "Boreal Forest (Taiga)",
        "Tropical & Subtropical Grasslands, Savannas & Shrublands": "Tropical & Subtropical Grasslands, Savannas & Shrublands",
        "Temperate Grasslands, Savannas & Shrublands": "Temperate Grasslands, Savannas & Shrublands",
        "Flooded Grasslands & Savannas": "Tropical & Subtropical Grasslands, Savannas & Shrublands",
        "Montane Grasslands & Shrublands": "Montane Grasslands & Shrublands",
        "Tundra": "Rock and Ice",
        "Mediterranean Forests, Woodlands & Scrub": "Mediterranean Forests, Woodlands & Scrub",
        "Deserts & Xeric Shrublands": "Deserts & Xeric Shrublands",
        "Mangroves": "Mangroves",
    }

    def _query_ecoregion(lat, lon):
        """Find ecoregion at given coordinates. Uses DB (fast) with shapefile fallback."""
        # Try PostgreSQL first — instant with spatial index
        try:
            from database.connection import get_ecoregion_by_coords
            result = get_ecoregion_by_coords(lat, lon)
            if result:
                return result
        except Exception as e:
            logging.debug(f"[ECO] DB lookup failed, falling back to shapefile: {e}")
        # Fallback to shapefile (slow first load)
        result = _find_ecoregion_at_point(lat, lon)
        if result is None:
            return None
        row = result.iloc[0]
        return {
            "eco_name": row.get("ECO_NAME", ""),
            "biome_name": row.get("BIOME_NAME", ""),
            "realm": row.get("REALM", ""),
            "biome_num": row.get("BIOME_NUM", ""),
        }

    # Biome color palette (WWF standard-ish)
    _BIOME_COLORS = {
        1: "#006400",   # Tropical Moist Broadleaf
        2: "#8B8B00",   # Tropical Dry Broadleaf
        3: "#4B8B3B",   # Tropical Coniferous
        4: "#228B22",   # Temperate Broadleaf & Mixed
        5: "#2E8B57",   # Temperate Conifer
        6: "#4682B4",   # Boreal Forests/Taiga
        7: "#DAA520",   # Tropical Grasslands/Savannas
        8: "#BDB76B",   # Temperate Grasslands
        9: "#5F9EA0",   # Flooded Grasslands
        10: "#8FBC8F",  # Montane Grasslands
        11: "#B0C4DE",  # Tundra
        12: "#CD853F",  # Mediterranean Forests
        13: "#DEB887",  # Deserts & Xeric
        14: "#20B2AA",  # Mangroves
        98: "#AAAAAA",  # Rock and Ice
        99: "#6495ED",  # Lakes / Water
    }

    def _biome_style(feature):
        biome_num = feature["properties"].get("BIOME_NUM", 0)
        color = _BIOME_COLORS.get(int(biome_num), "#999999")
        return {
            "fillColor": color,
            "color": "#444",
            "weight": 0.5,
            "fillOpacity": 0.35,
        }

    @render.ui
    @reactive.event(input.update_map, input.main_nav)
    def ecoregion_map():
        """Render a Folium map centred on user coordinates with ecoregion overlay."""
        coords = input.longitude_latitude()
        center = [0, 20]
        zoom = 3
        lat, lon = None, None
        if coords and coords.strip():
            try:
                lat, lon = parse_lat_lon(coords)
                center = [lat, lon]
                zoom = 8
            except Exception:
                lat, lon = None, None

        m = folium.Map(location=center, zoom_start=zoom, width="100%", height="1050px")
        folium.TileLayer("OpenStreetMap").add_to(m)

        # Add ecoregion overlay + marker from PostGIS (no shapefile needed)
        if lat is not None and lon is not None:
            try:
                from database.connection import get_db
                _db = get_db()
                eco_rows = _db.execute("""
                    SELECT eco_name, biome_name, biome_num, realm,
                           ST_AsGeoJSON(ST_Simplify(geom, 0.01)) as geojson
                    FROM ecoregions
                    WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                    LIMIT 1
                """, {'lat': lat, 'lon': lon})
                if eco_rows:
                    row = eco_rows[0]
                    eco_name, biome_name, biome_num, realm, geojson_str = row
                    import json
                    geojson_geom = json.loads(geojson_str)
                    feature = {
                        "type": "FeatureCollection",
                        "features": [{
                            "type": "Feature",
                            "properties": {
                                "ECO_NAME": eco_name,
                                "BIOME_NAME": biome_name,
                                "BIOME_NUM": biome_num,
                                "REALM": realm,
                            },
                            "geometry": geojson_geom,
                        }]
                    }
                    folium.GeoJson(
                        feature,
                        name="Ecorregião",
                        style_function=_biome_style,
                        tooltip=folium.GeoJsonTooltip(
                            fields=["ECO_NAME", "BIOME_NAME"],
                            aliases=["Ecorregião:", "Bioma:"],
                            style="font-size: 12px;",
                        ),
                    ).add_to(m)
                    popup_text = (
                        f"<b>{eco_name}</b><br>"
                        f"Biome: {biome_name}<br>"
                        f"Realm: {realm}"
                    )
                else:
                    popup_text = f"Lat: {lat:.4f}, Lon: {lon:.4f}"
                folium.Marker(
                    location=[lat, lon],
                    popup=folium.Popup(popup_text, max_width=280),
                    icon=folium.Icon(color="green", icon="leaf", prefix="fa"),
                ).add_to(m)
            except Exception:
                pass

        # Layer control to toggle ecoregions
        folium.LayerControl().add_to(m)

        return ui.HTML(m._repr_html_())

    @render.ui
    @reactive.event(input.update_map, input.main_nav)
    def ecoregion_info():
        """Show detected ecoregion as info pills."""
        coords = input.longitude_latitude()
        if not coords or not coords.strip():
            return ui.span()
        try:
            lat, lon = parse_lat_lon(coords)
        except Exception:
            return ui.span()

        eco = _query_ecoregion(lat, lon)
        if not eco:
            return ui.p(
                "Ecoregion not detected for these coordinates.",
                class_="text-muted",
                style="font-size: 0.85em;",
            )

        pill_style = (
            "display: inline-block; padding: 4px 12px; border-radius: 16px; "
            "border: 1.5px solid #6cb043; color: #6cb043; font-size: 0.85em; "
            "font-weight: 500; margin: 2px 4px;"
        )
        return ui.div(
            ui.p(
                ui.strong(eco["eco_name"]),
                style="margin-bottom: 4px;",
            ),
            ui.span(eco["biome_name"], style=pill_style),
            ui.span(eco["realm"], style=pill_style),
            style="margin-bottom: 8px;",
        )

    @reactive.effect
    @reactive.event(input.update_map, input.main_nav)
    def _auto_select_biome():
        """Auto-select biome checkbox based on detected ecoregion."""
        coords = input.longitude_latitude()
        if not coords or not coords.strip():
            return
        try:
            lat, lon = parse_lat_lon(coords)
        except Exception:
            return
        eco = _query_ecoregion(lat, lon)
        if not eco:
            return
        biome_name = eco.get("biome_name", "")
        ui_key = _BIOME_NAME_TO_UI.get(biome_name)
        if ui_key:
            ui.update_checkbox_group("biome_types", selected=[ui_key])

    # Mapping from Climate Types to Whittaker biomes (using names from plotbiomes dataset)
    CLIMATE_TO_BIOMES = {
        "Continental": ["Boreal forest", "Temperate seasonal forest"],
        "Polar": ["Tundra"],
        "Temperate": ["Temperate rain forest", "Temperate seasonal forest", "Temperate grassland/desert"],
        "Dry": ["Subtropical desert", "Temperate grassland/desert", "Woodland/shrubland"],
        "Highland": ["Tundra", "Boreal forest"],
        "Tropical Rainy": ["Tropical rain forest", "Tropical seasonal forest/savanna"]
    }

    # Mapping from Biome Types (UI) to Whittaker biomes (using names from plotbiomes dataset)
    BIOME_TYPE_TO_WHITTAKER = {
        "Boreal Forest (Taiga)": ["Boreal forest"],
        "Deserts & Xeric Shrublands": ["Subtropical desert"],
        "Mangroves": ["Tropical rain forest"],
        "Mediterranean Forests, Woodlands & Scrub": ["Woodland/shrubland"],
        "Montane Grasslands & Shrublands": ["Temperate grassland/desert", "Tundra"],
        "Rock and Ice": ["Tundra"],
        "Temperate Broadleaf & Mixed Forests": ["Temperate seasonal forest", "Temperate rain forest"],
        "Temperate Conifer Forests": ["Boreal forest", "Temperate seasonal forest"],
        "Tropical & Subtropical Moist Broadleaf Forests": ["Tropical rain forest"],
        "Tropical & Subtropical Dry Broadleaf Forests": ["Tropical seasonal forest/savanna"],
        "Tropical & Subtropical Grasslands, Savannas & Shrublands": ["Tropical seasonal forest/savanna", "Woodland/shrubland"],
        "Temperate Grasslands, Savannas & Shrublands": ["Temperate grassland/desert"]
    }

    # Color palette for Whittaker biomes (matching classic diagram colors)
    WHITTAKER_COLORS = {
        "Tundra": "#B8D4E3",
        "Boreal forest": "#A8C686",
        "Temperate seasonal forest": "#7A9A5A",
        "Temperate rain forest": "#4A7C59",
        "Tropical rain forest": "#1B5E3B",
        "Tropical seasonal forest/savanna": "#8B9E5A",
        "Subtropical desert": "#E8C496",
        "Temperate grassland/desert": "#D4C4A0",
        "Woodland/shrubland": "#C9A86C"
    }

    # Load Whittaker biomes data from CSV (real data from plotbiomes R package)
    WHITTAKER_DATA_PATH = os.path.join(Path(__file__).parent.parent, "data", "whittaker_biomes.csv")

    # Whittaker Biomes Diagram - Interactive Plotly visualization using real data
    @render_widget
    def whittaker_diagram():
        # Get selected climate and biome types
        selected_climates = input.climate_types() or []
        selected_biomes = input.biome_types() or []

        # Determine which Whittaker biomes should be highlighted
        highlighted_biomes = set()

        for climate in selected_climates:
            if climate in CLIMATE_TO_BIOMES:
                highlighted_biomes.update(CLIMATE_TO_BIOMES[climate])

        for biome in selected_biomes:
            if biome in BIOME_TYPE_TO_WHITTAKER:
                highlighted_biomes.update(BIOME_TYPE_TO_WHITTAKER[biome])

        # Load real Whittaker biome data from plotbiomes R package
        # Data source: Ricklefs (2008), The economy of nature, Figure 5.5
        # Citation: Valentin Ștefan & Sam Levin (2018), plotbiomes R package
        try:
            whittaker_df = pd.read_csv(WHITTAKER_DATA_PATH)
        except FileNotFoundError:
            # Fallback if CSV not found - create empty figure with message
            fig = go.Figure()
            fig.add_annotation(
                text="Whittaker biomes data not found. Please run data extraction script.",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
            return fig

        fig = go.Figure()

        # Check if any selection is made
        has_selection = len(highlighted_biomes) > 0

        # Get unique biomes and plot each as a polygon
        unique_biomes = whittaker_df['biome'].unique()

        # Order biomes for proper layering (bottom to top)
        biome_order = [
            "Subtropical desert",
            "Temperate grassland/desert",
            "Woodland/shrubland",
            "Tundra",
            "Boreal forest",
            "Temperate seasonal forest",
            "Tropical seasonal forest/savanna",
            "Temperate rain forest",
            "Tropical rain forest"
        ]

        # Plot biomes in order
        for biome_name in biome_order:
            if biome_name not in unique_biomes:
                continue

            biome_data = whittaker_df[whittaker_df['biome'] == biome_name]
            temp_coords = biome_data['temp_c'].tolist()
            precip_coords = biome_data['precp_cm'].tolist()

            # Get color for this biome
            base_color = WHITTAKER_COLORS.get(biome_name, "#CCCCCC")

            # Check if biome is highlighted
            is_highlighted = biome_name in highlighted_biomes

            # Determine colors based on selection state
            if has_selection:
                if is_highlighted:
                    fill_color = base_color
                    line_color = "rgba(0,0,0,0.8)"
                    line_width = 2
                    opacity = 1.0
                else:
                    # Dim non-selected biomes
                    fill_color = "rgba(200,200,200,0.3)"
                    line_color = "rgba(150,150,150,0.3)"
                    line_width = 1
                    opacity = 0.5
            else:
                # No selection - show all normally
                fill_color = base_color
                line_color = "rgba(255,255,255,0.8)"
                line_width = 1
                opacity = 0.9

            # Capitalize biome name for display
            display_name = biome_name.replace("/", " / ").title()

            fig.add_trace(go.Scatter(
                x=temp_coords,
                y=precip_coords,
                fill="toself",
                fillcolor=fill_color,
                line=dict(color=line_color, width=line_width),
                name=display_name,
                mode="lines",
                hoverinfo="name+text",
                text=f"<b>{display_name}</b>",
                hoveron="fills+points",
                opacity=opacity
            ))

        # Update layout - styled like reference image
        fig.update_layout(
            xaxis=dict(
                title="Temperature (°C)",
                range=[-17, 32],
                gridcolor="rgba(200,200,200,0.5)",
                zeroline=False,
                showgrid=True,
                dtick=10
            ),
            yaxis=dict(
                title="Precipitation (cm)",
                range=[-10, 420],
                gridcolor="rgba(200,200,200,0.5)",
                zeroline=False,
                showgrid=True,
                dtick=100
            ),
            plot_bgcolor="white",
            paper_bgcolor="white",
            height=500,
            showlegend=True,
            legend=dict(
                title=dict(text="<b>Whittaker biomes</b>", font=dict(size=12)),
                orientation="v",
                yanchor="top",
                y=0.95,
                xanchor="left",
                x=1.02,
                bgcolor="rgba(255,255,255,0.95)",
                bordercolor="rgba(200,200,200,0.5)",
                borderwidth=1,
                font=dict(size=11)
            ),
            margin=dict(l=60, r=180, t=30, b=60)
        )

        return fig


##Main Species — Discovery & Selection

    @render.ui
    def discovery_results():
        from database.connection import get_db, get_bioclim_at_coords

        search = (input.species_search() or "").strip().lower()

        gf = tuple(input.filter_growth_form() or ())
        use = tuple(input.filter_plant_use() or ())
        threat = tuple(input.filter_threat() or ())
        nfix = tuple(input.filter_nfix() or ())
        decid = tuple(input.filter_deciduousness() or ())

        selected = list(input.overview_plants() or [])
        selected_set = set(selected)

        has_filter = search or gf or use or threat or nfix or decid

        # --- Climate data for scoring ---
        bioclim = None
        has_climate = False
        try:
            lat_lon_str = input.longitude_latitude()
            if lat_lon_str:
                lat, lon = parse_lat_lon(lat_lon_str)
                bioclim = get_bioclim_at_coords(lat, lon)
                has_climate = bioclim is not None
        except Exception:
            pass

        # --- Section 1: New species from DB ---
        new_rows = []
        new_count = 0
        if has_filter:
            db = get_db()
            # Build dynamic SQL query
            conditions = []
            params = {}

            if search:
                conditions.append(
                    "(LOWER(cn_en.common_name) LIKE :search "
                    "OR LOWER(cn_pt.common_name) LIKE :search "
                    "OR LOWER(s.canonical_name) LIKE :search)"
                )
                params['search'] = f'%{search}%'

            if gf:
                gf_placeholders = []
                for i, g in enumerate(gf):
                    key = f'gf{i}'
                    gf_placeholders.append(f':{key}')
                    params[key] = g
                conditions.append(f"su.growth_form IN ({', '.join(gf_placeholders)})")

            if threat:
                th_placeholders = []
                for i, t in enumerate(threat):
                    key = f'th{i}'
                    th_placeholders.append(f':{key}')
                    params[key] = t
                conditions.append(f"su.threat_status IN ({', '.join(th_placeholders)})")

            if nfix:
                if "yes" in nfix and "no" not in nfix:
                    conditions.append("(su.nitrogen_fixer = TRUE OR s.family = 'Fabaceae')")
                elif "no" in nfix and "yes" not in nfix:
                    conditions.append("(su.nitrogen_fixer IS NOT TRUE AND s.family != 'Fabaceae')")

            if decid:
                decid_conds = []
                for i, d in enumerate(decid):
                    key = f'dc{i}'
                    decid_conds.append(f"su.deciduousness ILIKE :{key}")
                    params[key] = f'%{d}%'
                conditions.append(f"({' OR '.join(decid_conds)})")

            # Ecocrop categories for plant_use filter
            use_join = ""
            if use:
                use_join = "LEFT JOIN climate_envelope_ecocrop cee ON s.id = cee.species_id"
                use_conds = []
                # Map UI values to ecocrop category keywords
                use_map = {
                    'food': ['fruits', 'vegetables', 'roots', 'cereals', 'sugar', 'pulses', 'oil'],
                    'timber': ['forest', 'wood'],
                    'medicinal': ['medicinal', 'aromatic'],
                    'ornamental': ['ornamental', 'turf'],
                    'fodder': ['forage', 'pasture'],
                }
                for u in use:
                    keywords = use_map.get(u, [u])
                    for j, kw in enumerate(keywords):
                        key = f'use_{u}_{j}'
                        use_conds.append(f"cee.categories::text ILIKE :{key}")
                        params[key] = f'%{kw}%'
                conditions.append(f"({' OR '.join(use_conds)})")

            # Exclude already-selected (by common_en name)
            if selected_set:
                sel_placeholders = []
                for i, name in enumerate(selected_set):
                    key = f'sel{i}'
                    sel_placeholders.append(f':{key}')
                    params[key] = name
                conditions.append(f"cn_en.common_name NOT IN ({', '.join(sel_placeholders)})")

            # Only clean Latin-script names (skip Korean, corrupted U+FFFD, etc.)
            conditions.append("cn_en.common_name ~ '^[A-Za-z]'")
            conditions.append("cn_en.common_name NOT LIKE '%' || chr(65533) || '%'")
            where_clause = " AND ".join(conditions) if conditions else "TRUE"

            # Climate scoring: if location available, compute score and sort by it
            if has_climate:
                params.update({
                    'bio1': bioclim['bio1'], 'bio5': bioclim['bio5'],
                    'bio6': bioclim['bio6'], 'bio12': bioclim['bio12'],
                    'bio15': bioclim['bio15'],
                })
                query = f"""
                    SELECT DISTINCT ON (s.id)
                           cn_en.common_name AS common_en,
                           cn_pt.common_name AS common_pt,
                           s.canonical_name AS sci_name,
                           COALESCE(
                               calculate_climate_match(s.id, :bio1, :bio5, :bio6, :bio12, :bio15),
                               0
                           ) AS score
                    FROM species s
                    JOIN species_unified su ON s.id = su.species_id
                    JOIN common_names cn_en ON s.id = cn_en.species_id AND cn_en.language = 'en'
                    LEFT JOIN LATERAL (
                        SELECT common_name FROM common_names
                        WHERE species_id = s.id AND language = 'pt' LIMIT 1
                    ) cn_pt ON TRUE
                    LEFT JOIN species_climate_envelope sce ON s.id = sce.species_id
                    {use_join}
                    WHERE su.growth_form IS NOT NULL
                      AND {where_clause}
                    ORDER BY s.id
                """
                # Wrap to sort by score and limit
                query = f"""
                    SELECT common_en, common_pt, sci_name, score
                    FROM ({query}) sub
                    ORDER BY score DESC
                    LIMIT 100
                """
            else:
                query = f"""
                    SELECT DISTINCT ON (s.id)
                           cn_en.common_name AS common_en,
                           cn_pt.common_name AS common_pt,
                           s.canonical_name AS sci_name,
                           NULL::float AS score
                    FROM species s
                    JOIN species_unified su ON s.id = su.species_id
                    JOIN common_names cn_en ON s.id = cn_en.species_id AND cn_en.language = 'en'
                    LEFT JOIN LATERAL (
                        SELECT common_name FROM common_names
                        WHERE species_id = s.id AND language = 'pt' LIMIT 1
                    ) cn_pt ON TRUE
                    {use_join}
                    WHERE su.growth_form IS NOT NULL
                      AND {where_clause}
                    ORDER BY s.id
                """
                query = f"""
                    SELECT common_en, common_pt, sci_name, score
                    FROM ({query}) sub
                    ORDER BY common_en
                    LIMIT 100
                """

            try:
                rows = db.execute(query, params)
                new_count = len(rows)
            except Exception as e:
                logging.warning(f"[DISCOVERY] DB query failed: {e}")
                rows = []
                new_count = 0

            import html as _html
            import re as _re

            def _js_sq(s):
                """Escape for JS single-quoted string inside HTML attribute."""
                return s.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '\\r')

            for r in rows:
                cn_en = r[0] or ''
                cn_pt = r[1] or ''
                sci = r[2] or ''
                score_val = r[3]

                # Skip non-Latin names (Korean, Japanese, etc.)
                if cn_en and not _re.match(r'^[A-Za-z]', cn_en):
                    new_count -= 1
                    continue

                pct = int(round(score_val * 100)) if score_val and score_val > 0 else None

                safe = _js_sq(cn_en)
                cb_id = "cb_" + _re.sub(r'[^A-Za-z0-9_]', '', cn_en.replace(' ', '_'))

                add_js = (
                    f"var s=$('#overview_plants')[0].selectize;"
                    f"s.addOption({{value:'{safe}',text:'{safe}'}});"
                    f"s.addItem('{safe}');"
                )

                label_parts = []
                if cn_en:
                    label_parts.append(_html.escape(cn_en))
                if cn_pt and cn_pt != cn_en:
                    label_parts.append(_html.escape(cn_pt))
                if sci:
                    label_parts.append(_html.escape(sci))
                label_text = " &middot; ".join(label_parts)

                score_span = ""
                if pct is not None:
                    score_span = f' <span class="discovery-score">({pct}%)</span>'

                new_rows.append(
                    ui.HTML(
                        f'<div class="discovery-checkbox-item" onclick="var cb=this.querySelector(\'input\');if(!cb.checked){{cb.checked=true;{add_js}}}">'
                        f'<input type="checkbox" id="{cb_id}" onchange="if(this.checked){{{add_js}}}">'
                        f'<label for="{cb_id}">{label_text}{score_span}</label>'
                        f'</div>'
                    )
                )

        # --- Section 2: Selected species ---
        sel_rows = []
        if selected:
            # Look up selected species in both CSV and DB
            df = open_csv(FILE_NAME)
            db = get_db()
            for name in selected:
                cn_pt = ''
                sci = ''
                pct = None

                # Try CSV first (has chart data)
                csv_row = df[df['common_en'] == name]
                if len(csv_row):
                    if pd.notna(csv_row.iloc[0].get('common_pt')):
                        cn_pt = str(csv_row.iloc[0]['common_pt'])
                    if pd.notna(csv_row.iloc[0].get('sci_name')):
                        sci = str(csv_row.iloc[0]['sci_name'])

                # If not in CSV, try DB
                if not sci:
                    try:
                        db_rows = db.execute("""
                            SELECT s.canonical_name,
                                   (SELECT common_name FROM common_names
                                    WHERE species_id = s.id AND language = 'pt' LIMIT 1)
                            FROM species s
                            JOIN common_names cn ON s.id = cn.species_id
                                AND cn.language = 'en' AND cn.common_name = :name
                            LIMIT 1
                        """, {'name': name})
                        if db_rows:
                            sci = db_rows[0][0] or ''
                            cn_pt = db_rows[0][1] or ''
                    except Exception:
                        pass

                # Climate score
                if has_climate and sci:
                    try:
                        score_rows = db.execute("""
                            SELECT calculate_climate_match(s.id, :bio1, :bio5, :bio6, :bio12, :bio15)
                            FROM species s WHERE s.canonical_name = :sci LIMIT 1
                        """, {**{k: bioclim[k] for k in ['bio1','bio5','bio6','bio12','bio15']}, 'sci': sci})
                        if score_rows and score_rows[0][0]:
                            pct = int(round(float(score_rows[0][0]) * 100))
                    except Exception:
                        pass

                import html as _html

                label_parts = [_html.escape(name)]
                if cn_pt and cn_pt != name:
                    label_parts.append(_html.escape(cn_pt))
                if sci:
                    label_parts.append(_html.escape(sci))
                label_text = " &middot; ".join(label_parts)

                score_span = ""
                if pct is not None:
                    score_span = f' <span class="discovery-score">({pct}%)</span>'

                safe = name.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')
                remove_js = (
                    f"var s=$('#overview_plants')[0].selectize;"
                    f"s.removeItem('{safe}');"
                    f"setTimeout(function(){{var i=s.$control_input[0];if(i)i.blur();s.close();}},50);"
                )

                sel_rows.append(
                    ui.HTML(
                        f'<div class="selected-item">'
                        f'<span style="color:#4a7c3f;">&#10003;</span>'
                        f'<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{label_text}{score_span}</span>'
                        f'<span class="remove-btn" onclick="{remove_js}" title="Remove">&times;</span>'
                        f'</div>'
                    )
                )

        # --- Build container ---
        sections = []

        # New species section
        if has_filter:
            header_text_pt = f"Novas espécies ({new_count}):" if new_count else "Nenhuma espécie encontrada"
            header_text_en = f"New species ({new_count}):" if new_count else "No species found"
            sections.append(ui.HTML(
                f'<div class="discovery-section-header">'
                f'<span class="i18n-pt">{header_text_pt}</span>'
                f'<span class="i18n-en">{header_text_en}</span>'
                f'</div>'
            ))
            sections.append(ui.div(*new_rows, class_="discovery-section") if new_rows else ui.span())
        else:
            sections.append(ui.HTML(
                '<div class="discovery-section" style="display:flex;align-items:center;justify-content:center;min-height:120px;">'
                '<p style="color:#888;text-align:center;">'
                '<span class="i18n-pt">Use a busca ou filtros para descobrir espécies</span>'
                '<span class="i18n-en">Use search or filters to discover species</span>'
                '</p></div>'
            ))

        # Selected section
        if sel_rows:
            sel_header_pt = f"Selecionadas ({len(selected)}):"
            sel_header_en = f"Selected ({len(selected)}):"
            sections.append(ui.HTML(
                f'<div class="discovery-section-header selected-section">'
                f'<span class="i18n-pt">{sel_header_pt}</span>'
                f'<span class="i18n-en">{sel_header_en}</span>'
                f'</div>'
            ))
            sections.append(ui.div(*sel_rows, class_="discovery-section"))

        return ui.div(*sections, class_="discovery-results-container")

    @render.ui
    @reactive.event(input.overview_plants, input.stratum_bins, input.harvest_bins)
    def intercrops():
        if input.database_choice() == "try":
            df = open_csv(FILE_NAME)
            plants = list(input.overview_plants())

            if not plants:
                empty_option = {
                    'title': {
                        'text': 'Período de colheita × Estrato',
                        'left': 'center', 'top': 25,
                        'textStyle': {'fontSize': 13, 'fontFamily': 'Inter, sans-serif', 'color': '#bbb'},
                    },
                    'grid': {'left': 140, 'right': 20, 'top': 60, 'bottom': 80},
                    'xAxis': {
                        'type': 'value', 'name': 'Período de colheita (anos após plantio)',
                        'nameLocation': 'middle', 'nameGap': 35,
                        'nameTextStyle': {'color': '#ccc', 'fontSize': 14, 'fontFamily': 'Inter, sans-serif'},
                        'min': 0, 'max': 6,
                        'splitLine': {'show': False},
                        'axisLabel': {'color': '#ccc', 'fontFamily': 'Inter, sans-serif'},
                    },
                    'yAxis': {
                        'type': 'value', 'min': 0, 'max': 9,
                        'splitLine': {'show': False},
                        'axisLabel': {'color': '#ccc', 'fontFamily': 'Inter, sans-serif'},
                    },
                    'series': [],
                    'backgroundColor': 'transparent',
                }
                return ui.HTML(echarts_html(empty_option, 'echart_intercrops', height=700))

            # Categorize species by available data
            complete_data = []
            missing_harvest = []
            missing_stratum = []
            missing_both = []

            from database.connection import get_db as _get_db
            _db = _get_db()

            for plant in plants:
                query = df[df['common_en'] == plant][
                    ['common_en', 'growth_form', 'yrs_ini_prod', 'longev_prod', 'stratum']
                ].values.tolist()

                # Also try matching by sci_name (DB may use different common_en)
                if not query:
                    sci_match = df[df['sci_name'] == plant]
                    if sci_match.empty:
                        # Look up sci_name from DB for this common_en, then find in CSV
                        try:
                            sci_rows = _db.execute("""
                                SELECT s.canonical_name FROM species s
                                JOIN common_names cn ON s.id = cn.species_id
                                    AND cn.language = 'en' AND cn.common_name = :name
                                LIMIT 1
                            """, {'name': plant})
                            if sci_rows and sci_rows[0][0]:
                                sci_match = df[df['sci_name'] == sci_rows[0][0]]
                        except Exception:
                            pass
                    if not sci_match.empty:
                        query = sci_match[
                            ['common_en', 'growth_form', 'yrs_ini_prod', 'longev_prod', 'stratum']
                        ].values.tolist()
                        # Use original plant name for display
                        if query:
                            query[0][0] = plant

                if not query:
                    # Fallback: look up growth_form, max_height, lifespan from DB
                    try:
                        db_rows = _db.execute("""
                            SELECT su.growth_form, su.max_height_m, su.lifespan_years
                            FROM species s
                            JOIN species_unified su ON s.id = su.species_id
                            JOIN common_names cn ON s.id = cn.species_id
                                AND cn.language = 'en' AND cn.common_name = :name
                            LIMIT 1
                        """, {'name': plant})
                        if db_rows:
                            gf = db_rows[0][0] or 'other'
                            db_height = float(db_rows[0][1]) if db_rows[0][1] else None
                            db_lifespan = float(db_rows[0][2]) if db_rows[0][2] else None
                        else:
                            gf, db_height, db_lifespan = 'other', None, None
                    except Exception:
                        gf, db_height, db_lifespan = 'other', None, None

                    # Estimate stratum from max_height_m (0-9 scale)
                    # 0-0.5m→1, 0.5-2m→2, 2-5m→3, 5-10m→4, 10-15m→5, 15-25m→6, 25-35m→7, >35m→8
                    db_stratum = None
                    if db_height is not None:
                        if db_height <= 0.5:
                            db_stratum = 1.0
                        elif db_height <= 2:
                            db_stratum = 2.0
                        elif db_height <= 5:
                            db_stratum = 3.0
                        elif db_height <= 10:
                            db_stratum = 4.0
                        elif db_height <= 15:
                            db_stratum = 5.0
                        elif db_height <= 25:
                            db_stratum = 6.0
                        elif db_height <= 35:
                            db_stratum = 7.0
                        else:
                            db_stratum = 8.0

                    # Use lifespan as longevity proxy
                    db_duration = db_lifespan if db_lifespan else None

                    has_s = db_stratum is not None
                    has_d = db_duration is not None

                    if has_s and has_d:
                        # Has stratum + duration but no harvest start
                        missing_harvest.append([plant, gf, None, db_duration, db_stratum])
                    elif has_s:
                        missing_harvest.append([plant, gf, None, None, db_stratum])
                    elif has_d:
                        missing_stratum.append([plant, gf, 0, db_duration, None])
                    else:
                        missing_both.append([plant, gf, None, None, None])
                    continue

                query = query[0]
                name, growth_type, x_start, duration_raw, y_position = query

                has_harvest = str(x_start) != 'nan'
                has_stratum = str(y_position) != 'nan'
                has_duration = str(duration_raw) != 'nan'

                duration = duration_raw if has_duration else 5.0

                if has_harvest and has_stratum:
                    complete_data.append([name, growth_type, x_start, duration, y_position])
                elif has_harvest and not has_stratum:
                    missing_stratum.append([name, growth_type, x_start, duration, None])
                elif not has_harvest and has_stratum:
                    # Keep original duration_raw so ℹ️ only shows for real data
                    missing_harvest.append([name, growth_type, None, duration_raw, y_position])
                else:
                    missing_both.append([name, growth_type, None, None, None])

            # Get stratum resolution from slider
            num_y_bins = int(input.stratum_bins())
            stratum_config = STRATUM[num_y_bins]
            y_bins = stratum_config[0]
            y_labels = stratum_config[1]

            # Determine X range in real years, then convert to sqrt-space
            all_x_values_real = []
            if complete_data:
                for plant in complete_data:
                    all_x_values_real.append(plant[2])
                    all_x_values_real.append(plant[2] + plant[3])
            if missing_stratum:
                for plant in missing_stratum:
                    all_x_values_real.append(plant[2])
                    all_x_values_real.append(plant[2] + plant[3])

            if all_x_values_real:
                min_x_real = 0  # Always start at year 0
                max_x_real = round(max(all_x_values_real), 2)
            else:
                min_x_real, max_x_real = 0, 10

            if max_x_real - min_x_real < 1:
                max_x_real = min_x_real + 10

            # Convert to sqrt-space: bins are uniform in sqrt = quadratic in real years
            min_x_sqrt = sqrt_transform(min_x_real)
            max_x_sqrt = sqrt_transform(max_x_real)

            num_x_bins = int(input.harvest_bins())
            x_bins_sqrt = [round(x, 4) for x in np.linspace(min_x_sqrt, max_x_sqrt, num_x_bins + 1).tolist()]
            # Real-year labels for each bin edge
            x_bins_real = [round(sx ** 2, 1) for sx in x_bins_sqrt]

            # Use sqrt-space bins for all positioning
            x_bins = x_bins_sqrt
            min_x = min_x_sqrt
            max_x = max_x_sqrt

            x_bin_width = (max_x - min_x) / num_x_bins if num_x_bins > 0 else 1
            y_bin_height = 9 / len(y_bins)

            # Growth Form Mappings (legend order matches user spec)
            gf_list = ['tree', 'shrub', 'subshrub', 'forb', 'graminoid', 'palm', 'liana', 'vine', 'scrambler', 'bamboo', 'other']
            gf_colors = ['#2a43d1', '#0095c6', '#612e14', '#d77d28', '#633096', '#63a355', '#be2843', '#cc4fb9', '#017201', '#fd2f6d', '#171717']
            color_map = dict(zip(gf_list, gf_colors))
            # Legacy aliases
            color_map['herb'] = color_map['forb']
            color_map['climber'] = color_map['vine']
            color_map['cactus'] = '#49d1d5'

            def get_offset_position(count):
                if count == 0:
                    return (0, 0)
                if count % 2 == 1:
                    position = (count + 1) // 2
                    return (0.2 * position, 0)
                else:
                    position = count // 2
                    return (-0.2 * position, 0)

            # Build markArea data for grid cells
            mark_area_data = []
            for i in range(len(x_bins) - 1):
                for j in range(len(y_bins) - 1):
                    mark_area_data.append([
                        {'xAxis': x_bins[i], 'yAxis': y_bins[j], 'itemStyle': {'color': 'white', 'borderColor': '#e0e0e0', 'borderWidth': 1}},
                        {'xAxis': x_bins[i+1], 'yAxis': y_bins[j+1]}
                    ])

            # Left margin (missing harvest)
            left_x0 = round(min_x - (max_x - min_x) * 0.1, 2)
            mark_area_data.append([
                {'xAxis': left_x0, 'yAxis': 0, 'itemStyle': {'color': 'rgba(255,200,150,0.1)', 'borderColor': 'orange', 'borderWidth': 2, 'borderType': 'dashed'}},
                {'xAxis': min_x, 'yAxis': 9}
            ])

            # Bottom margin (missing stratum)
            mark_area_data.append([
                {'xAxis': min_x, 'yAxis': -2, 'itemStyle': {'color': 'rgba(255,150,150,0.1)', 'borderColor': 'red', 'borderWidth': 2, 'borderType': 'dashed'}},
                {'xAxis': max_x, 'yAxis': 0}
            ])

            # Build species series
            species_series = []
            added_species = set()
            legend_names = []

            # 1. Complete data
            bin_counters = {}
            for plant in complete_data:
                name, growth_type, x_start, duration, y_position = plant
                if name in added_species:
                    continue

                # Transform x_start to sqrt-space for bin lookup
                x_start_sqrt = sqrt_transform(x_start)

                x_bin_index = 0
                for i in range(len(x_bins) - 1):
                    if x_start_sqrt >= x_bins[i] and x_start_sqrt < x_bins[i+1]:
                        x_bin_index = i
                        break
                if x_start_sqrt >= x_bins[-1]:
                    x_bin_index = len(x_bins) - 2

                y_bin_index = 0
                for i in range(len(y_bins) - 1):
                    if y_position >= y_bins[i] and y_position < y_bins[i+1]:
                        y_bin_index = i
                        break
                if y_position >= y_bins[-1]:
                    y_bin_index = len(y_bins) - 2

                bin_key = (x_bin_index, y_bin_index)
                if bin_key not in bin_counters:
                    bin_counters[bin_key] = 0
                else:
                    bin_counters[bin_key] += 1

                offset_x, offset_y = get_offset_position(bin_counters[bin_key])
                x_center = round((x_bins[x_bin_index] + x_bins[x_bin_index + 1]) / 2, 4)
                y_center = round((y_bins[y_bin_index] + y_bins[y_bin_index + 1]) / 2, 2)
                x_final = x_center + offset_x * x_bin_width * 0.3
                y_final = y_center + offset_y * y_bin_height * 0.3

                # Tooltip shows real years (not sqrt)
                safe_name = name
                tooltip_text = (f"<b>{safe_name}</b><br/>Forma: {growth_type}<br/>"
                                f"Início colheita: {round(x_start, 2)} anos<br/>"
                                f"Duração: {round(duration, 2)} anos<br/>"
                                f"Estrato: {round(y_position, 2)}")

                gf_symbol = ECHARTS_PATHS.get(growth_type, 'circle')
                gf_color = color_map.get(growth_type, '#999')

                # Harvest period line endpoints (in sqrt-space)
                x_line_start = round(sqrt_transform(x_start), 4)
                x_line_end = round(sqrt_transform(x_start + duration), 4)

                species_series.append({
                    'type': 'scatter',
                    'name': name,
                    'data': [[x_line_end, round(y_final, 3)]],
                    'symbol': gf_symbol,
                    'symbolSize': ECHARTS_SYMBOL_SIZE.get(growth_type, _DEFAULT_SYMBOL_SIZE),
                    'symbolOffset': [10, 0],
                    'itemStyle': _gf_item_style(growth_type, gf_color),
                    'label': {
                        'show': True,
                        'formatter': f'{name}',
                        'fontSize': 11,
                        'position': 'right',
                        'distance': 4,
                        'color': '#333',
                        'fontFamily': 'Inter, sans-serif',
                    },
                    'tooltip': {'formatter': f'__JS__function(){{return {json.dumps(tooltip_text)};}}__JSEND__'},
                    'markLine': {
                        'silent': True,
                        'symbol': ['circle', 'none'],
                        'symbolSize': [4, 0],
                        'label': {'show': False},
                        'lineStyle': {'color': gf_color, 'width': 2.5, 'type': 'solid'},
                        'data': [[
                            {'coord': [x_line_start, round(y_final, 3)]},
                            {'coord': [x_line_end, round(y_final, 3)]},
                        ]],
                    },
                })
                legend_names.append(name)
                added_species.add(name)

            # 2. Missing harvest (left margin)
            stratum_counters = {}
            partial_info_count = 0
            for plant in missing_harvest:
                name, growth_type, _, exit_duration, y_position = plant
                if name in added_species:
                    continue

                y_rounded = round(y_position, 1)
                if y_rounded not in stratum_counters:
                    stratum_counters[y_rounded] = 0
                else:
                    stratum_counters[y_rounded] += 1

                y_offset = (stratum_counters[y_rounded] % 3 - 1) * 0.3
                x_offset = (stratum_counters[y_rounded] // 3) * 0.02 * (max_x - min_x)
                px_val = round(min_x - (max_x - min_x) * 0.05 - x_offset, 4)
                py_val = round(y_position + y_offset, 3)

                # Feature 1: check if species has exit time but no entry time
                has_exit_time = exit_duration is not None and str(exit_duration) != 'nan'
                exit_years = round(exit_duration, 1) if has_exit_time else None

                safe_name = name
                if has_exit_time:
                    tooltip_text = (f"<b>{safe_name}</b><br/>Forma: {growth_type}<br/>"
                                    f"ℹ️ Tempo de saída: {exit_years} anos, entrada desconhecida<br/>"
                                    f"Estrato: {round(y_position, 2)}")
                    partial_info_count += 1
                else:
                    tooltip_text = (f"<b>{safe_name}</b><br/>Forma: {growth_type}<br/>"
                                    f"⚠️ Colheita: Desconhecida<br/>"
                                    f"Estrato: {round(y_position, 2)}")

                gf_symbol = ECHARTS_PATHS.get(growth_type, 'circle')
                gf_color_margin = color_map.get(growth_type, '#999')
                label_text = f'ℹ️ {name}' if has_exit_time else name

                series_entry = {
                    'type': 'scatter',
                    'name': name,
                    'data': [[px_val, py_val]],
                    'symbol': gf_symbol,
                    'symbolSize': ECHARTS_SYMBOL_SIZE.get(growth_type, _DEFAULT_SYMBOL_SIZE),
                    'itemStyle': _gf_item_style(growth_type, gf_color_margin),
                    'label': {
                        'show': True,
                        'formatter': f'{label_text}',
                        'fontSize': 11,
                        'offset': [0, 0],
                        'color': '#333',
                        'fontFamily': 'Inter, sans-serif',
                    },
                    'tooltip': {'formatter': f'__JS__function(){{return {json.dumps(tooltip_text)};}}__JSEND__'},
                }

                species_series.append(series_entry)
                legend_names.append(name)
                added_species.add(name)

            # 3. Missing stratum (bottom margin)
            x_position_counters = {}
            for plant in missing_stratum:
                name, growth_type, x_start, duration, _ = plant
                if name in added_species:
                    continue

                # Transform x_start to sqrt-space for bin lookup
                x_start_sqrt = sqrt_transform(x_start)

                x_bin_index = 0
                for i in range(len(x_bins) - 1):
                    if x_start_sqrt >= x_bins[i] and x_start_sqrt < x_bins[i+1]:
                        x_bin_index = i
                        break
                if x_start_sqrt >= x_bins[-1]:
                    x_bin_index = len(x_bins) - 2

                if x_bin_index not in x_position_counters:
                    x_position_counters[x_bin_index] = 0
                else:
                    x_position_counters[x_bin_index] += 1

                x_center = round((x_bins[x_bin_index] + x_bins[x_bin_index + 1]) / 2, 4)
                x_off = (x_position_counters[x_bin_index] % 3 - 1) * 0.15 * x_bin_width
                y_off = -(x_position_counters[x_bin_index] // 3) * 0.3

                # Tooltip shows real years
                safe_name = name
                tooltip_text = (f"<b>{safe_name}</b><br/>Forma: {growth_type}<br/>"
                                f"Início colheita: {round(x_start, 2)} anos<br/>"
                                f"Duração: {round(duration, 2)} anos<br/>"
                                f"⚠️ Estrato: Desconhecido")

                gf_symbol = ECHARTS_PATHS.get(growth_type, 'circle')
                gf_color = color_map.get(growth_type, '#999')

                # Harvest period line (in sqrt-space)
                x_line_start = round(sqrt_transform(x_start), 4)
                x_line_end = round(sqrt_transform(x_start + duration), 4)
                y_pt = round(-1 + y_off, 3)

                species_series.append({
                    'type': 'scatter',
                    'name': name,
                    'data': [[x_line_end, y_pt]],
                    'symbol': gf_symbol,
                    'symbolSize': ECHARTS_SYMBOL_SIZE.get(growth_type, _DEFAULT_SYMBOL_SIZE),
                    'symbolOffset': [10, 0],
                    'itemStyle': _gf_item_style(growth_type, gf_color),
                    'label': {
                        'show': True,
                        'formatter': f'{name}',
                        'fontSize': 11,
                        'position': 'right',
                        'distance': 4,
                        'color': '#333',
                        'fontFamily': 'Inter, sans-serif',
                    },
                    'tooltip': {'formatter': f'__JS__function(){{return {json.dumps(tooltip_text)};}}__JSEND__'},
                    'markLine': {
                        'silent': True,
                        'symbol': ['circle', 'none'],
                        'symbolSize': [4, 0],
                        'label': {'show': False},
                        'lineStyle': {'color': gf_color, 'width': 2.5, 'type': 'solid'},
                        'data': [[
                            {'coord': [x_line_start, y_pt]},
                            {'coord': [x_line_end, y_pt]},
                        ]],
                    },
                })
                legend_names.append(name)
                added_species.add(name)

            # 4. Missing both (bottom-left corner)
            cols = 2
            for idx, plant in enumerate(missing_both):
                name, growth_type = plant[0], plant[1]
                if name in added_species:
                    continue

                row = idx // cols
                col = idx % cols
                x_pos = round(min_x - (max_x - min_x) * 0.07 + col * 0.03 * (max_x - min_x), 4)
                y_pos = round(-1 - row * 0.4, 3)

                safe_name = name
                tooltip_text = (f"<b>{safe_name}</b><br/>Forma: {growth_type}<br/>"
                                f"⚠️ Colheita: Desconhecida<br/>"
                                f"⚠️ Estrato: Desconhecido")

                gf_symbol = ECHARTS_PATHS.get(growth_type, 'circle')
                gf_color_corner = color_map.get(growth_type, '#999')
                species_series.append({
                    'type': 'scatter',
                    'name': name,
                    'data': [[x_pos, y_pos]],
                    'symbol': gf_symbol,
                    'symbolSize': ECHARTS_SYMBOL_SIZE.get(growth_type, _DEFAULT_SYMBOL_SIZE),
                    'itemStyle': _gf_item_style(growth_type, gf_color_corner),
                    'label': {
                        'show': True,
                        'formatter': f'{name}',
                        'fontSize': 11,
                        'offset': [0, 0],
                        'color': '#333',
                        'fontFamily': 'Inter, sans-serif',
                    },
                    'tooltip': {'formatter': f'__JS__function(){{return {json.dumps(tooltip_text)};}}__JSEND__'},
                })
                legend_names.append(name)
                added_species.add(name)

            # Build Y-axis label formatter as JS function
            sorted_label_items = sorted(y_labels.items(), key=lambda x: x[0])
            y_label_map_js = json.dumps({str(pos): label for pos, label in sorted_label_items}, ensure_ascii=False)
            js_y_formatter = f"__JS__function(value){{var v=Math.round(value*2)/2;var m={y_label_map_js};return m[String(v)]||'';}}__JSEND__"

            # Graphic elements for annotations
            graphic_elements = []

            # "Formas de crescimento" title at top
            graphic_elements.append({
                'type': 'text',
                'left': 'center',
                'top': 8,
                'style': {
                    'text': 'Formas de crescimento',
                    'fontSize': 14,
                    'fontWeight': 'bold',
                    'fontFamily': 'Inter, sans-serif',
                    'fill': '#333',
                },
                'z': 100,
            })

            # Growth form legend row at top of chart (emoji + PT name)
            gf_display_pt = {
                'tree': 'Árvore', 'shrub': 'Arbusto', 'subshrub': 'Sub-arbusto',
                'forb': 'Herbácea', 'graminoid': 'Gram. e afins', 'palm': 'Palmeira',
                'liana': 'T. lenhosa', 'vine': 'T. herbácea', 'scrambler': 'Rasteira',
                'bamboo': 'Bambu', 'other': 'Outro',
            }

            # Fixed legend as graphic elements above the grid (● dot + PT name)
            n_gf = len(gf_list)
            for i, gf in enumerate(gf_list):
                pt_name = gf_display_pt.get(gf, gf)
                color = COLOR.get(gf, '#333')
                # Distribute evenly across grid width
                pct = (i + 0.5) / n_gf * 100
                graphic_elements.append({
                    'type': 'text',
                    'left': f'{pct}%',
                    'top': 70,
                    'style': {
                        'text': f'● {pt_name}',
                        'fontSize': 10,
                        'fontFamily': 'Inter, sans-serif',
                        'fill': color,
                        'fontWeight': 600,
                        'textAlign': 'center',
                    },
                    'z': 100,
                })

            # Annotation labels for margin areas
            if missing_harvest:
                annot_text = '⚠️ Colheita desconhecida'
                if partial_info_count > 0:
                    annot_text += f' (ℹ️ {partial_info_count} com saída)'
                graphic_elements.append({
                    'type': 'text',
                    'left': 20,
                    'top': 55,
                    'style': {
                        'text': annot_text,
                        'fontSize': 11,
                        'fill': 'darkorange',
                        'fontFamily': 'Inter, sans-serif',
                        'backgroundColor': 'rgba(255,255,255,0.8)',
                        'borderColor': 'orange',
                        'borderWidth': 1,
                        'padding': [3, 6],
                    },
                    'z': 50,
                })

            if missing_stratum:
                graphic_elements.append({
                    'type': 'text',
                    'left': 90,
                    'bottom': 90,
                    'style': {
                        'text': '⚠️ Estrato desconhecido',
                        'fontSize': 11,
                        'fill': 'darkred',
                        'fontFamily': 'Inter, sans-serif',
                        'backgroundColor': 'rgba(255,255,255,0.8)',
                        'borderColor': 'red',
                        'borderWidth': 1,
                        'padding': [3, 6],
                    },
                    'z': 50,
                })

            if missing_both:
                graphic_elements.append({
                    'type': 'text',
                    'left': 10,
                    'bottom': 75,
                    'style': {
                        'text': '⚠️ Ambos desconhecidos',
                        'fontSize': 9,
                        'fill': 'darkred',
                        'fontFamily': 'Inter, sans-serif',
                        'backgroundColor': 'rgba(255,255,255,0.8)',
                        'borderColor': 'darkred',
                        'borderWidth': 1,
                        'padding': [2, 4],
                    },
                    'z': 50,
                })

            # Title
            complete_count = len(complete_data)
            missing_h_count = len(missing_harvest)
            missing_s_count = len(missing_stratum)
            missing_b_count = len(missing_both)
            title_parts = [f"Mostrando {len(added_species)} espécies selecionadas"]
            if complete_count:
                title_parts.append(f"{complete_count} completas")
            if missing_h_count:
                title_parts.append(f"{missing_h_count} sem colheita")
            if missing_s_count:
                title_parts.append(f"{missing_s_count} sem estrato")
            if missing_b_count:
                title_parts.append(f"{missing_b_count} sem ambos")

            x_axis_min = round(min_x - (max_x - min_x) * 0.12, 4)
            x_axis_max = round(max_x + (max_x - min_x) * 0.05, 4)

            # X-axis formatter: convert sqrt-space value → real years (hide labels in unknown margin)
            js_x_formatter = "__JS__function(v){if(v<0)return '';var r=v*v; return r<1 ? (Math.round(r*12)+'m') : (Math.round(r*10)/10+'a');}__JSEND__"

            option = {
                'title': {
                    'text': ' | '.join(title_parts),
                    'left': 'center',
                    'top': 25,
                    'textStyle': {'fontSize': 13, 'fontFamily': 'Inter, sans-serif', 'color': '#555'},
                },
                'tooltip': {'trigger': 'item', 'confine': True},
                'toolbox': {
                    'feature': {'brush': {'type': ['rect'], 'title': {'rect': 'Selecionar setor'}}},
                    'right': 210, 'top': 10,
                },
                'brush': {
                    'toolbox': ['rect'],
                    'xAxisIndex': 0, 'yAxisIndex': 0,
                    'brushMode': 'single',
                    'brushStyle': {
                        'borderWidth': 2,
                        'color': 'rgba(120,180,120,0.15)',
                        'borderColor': 'rgba(120,180,120,0.6)',
                    },
                    'throttleType': 'debounce', 'throttleDelay': 300,
                },
                'legend': {'show': False},
                'grid': {'left': 140, 'right': 180, 'top': 110, 'bottom': 100},
                'xAxis': {
                    'type': 'value',
                    'name': 'Período de colheita (anos após plantio)',
                    'nameLocation': 'middle',
                    'nameGap': 35,
                    'nameTextStyle': {'color': '#555', 'fontSize': 14, 'fontFamily': 'Inter, sans-serif'},
                    'axisLabel': {
                        'formatter': js_x_formatter,
                        'fontFamily': 'Inter, sans-serif',
                        'fontSize': 12,
                        'color': '#171717',
                    },
                    'min': x_axis_min,
                    'max': x_axis_max,
                    'splitLine': {'show': False},
                },
                'yAxis': {
                    'type': 'value',
                    'min': -2.5,
                    'max': 11,
                    'interval': 0.5,
                    'axisLabel': {
                        'formatter': js_y_formatter,
                        'fontFamily': 'Inter, sans-serif',
                        'fontSize': 12,
                        'color': '#171717',
                    },
                    'axisTick': {'show': False},
                    'splitLine': {'show': False},
                },
                'series': [
                    {
                        'type': 'scatter',
                        'data': [],
                        'silent': True,
                        'tooltip': {'show': False},
                        'markArea': {'silent': True, 'data': mark_area_data},
                    },
                    *species_series,
                ],
                'graphic': {'elements': graphic_elements},
                'textStyle': {'fontFamily': 'Inter, sans-serif'},
                'backgroundColor': 'transparent',
            }

            # Brush handler JS — shows clickable overlay, then sends to Shiny on click
            brush_js = """
            // Remove any existing overlay
            var oldOv = document.getElementById('brush-overlay');
            if (oldOv) oldOv.remove();

            // Auto-activate brush tool ("Selecionar setor" always on)
            setTimeout(function() {
                chart.dispatchAction({ type: 'takeGlobalCursor', key: 'brush', brushOption: { brushType: 'rect', brushMode: 'single' } });
            }, 200);

            // Persist hide state across chart re-renders
            if (window._brushActive) {
                var w = document.getElementById('lifetime-growth-wrapper');
                if (w) w.style.display = 'none';
            }

            chart.on('brushEnd', function(params) {
                if (!params.areas || !params.areas.length) return;
                var area = params.areas[0];
                if (!area.coordRange) return;
                var xR = area.coordRange[0], yR = area.coordRange[1];

                // Store range data for later
                var rangeData = {
                    x0: xR[0]*xR[0], x1: xR[1]*xR[1],
                    y0: yR[0], y1: yR[1],
                    timestamp: Date.now()
                };

                // Convert coord range to pixel for overlay positioning
                var p1 = chart.convertToPixel({xAxisIndex:0, yAxisIndex:0}, [xR[0], yR[1]]);
                var p2 = chart.convertToPixel({xAxisIndex:0, yAxisIndex:0}, [xR[1], yR[0]]);
                var cx = (p1[0] + p2[0]) / 2;
                var cy = (p1[1] + p2[1]) / 2;

                // Remove old overlay
                var old = document.getElementById('brush-overlay');
                if (old) old.remove();

                // Create clickable overlay
                var ov = document.createElement('div');
                ov.id = 'brush-overlay';
                ov.className = 'brush-click-overlay';
                ov.innerHTML = 'Clique para conhecer<br>espécies novas!';
                ov.style.left = cx + 'px';
                ov.style.top = cy + 'px';
                el.style.position = 'relative';
                el.appendChild(ov);

                ov.addEventListener('click', function() {
                    ov.remove();
                    window._brushActive = true;
                    var w = document.getElementById('lifetime-growth-wrapper');
                    if (w) w.style.display = 'none';
                    if (window.Shiny) {
                        Shiny.setInputValue('brush_range', rangeData, {priority:'event'});
                        setTimeout(function() {
                            var panel = document.querySelector('.brush-results-panel');
                            if (panel) panel.scrollIntoView({behavior:'smooth', block:'center'});
                        }, 300);
                    }
                });
            });

            // Clear overlay when brush is cleared
            chart.on('brush', function(params) {
                if (!params.areas || !params.areas.length) {
                    var o = document.getElementById('brush-overlay');
                    if (o) o.remove();
                    window._brushActive = false;
                    if (window.Shiny) Shiny.setInputValue('brush_range', null, {priority:'event'});
                    var w = document.getElementById('lifetime-growth-wrapper');
                    if (w) w.style.display = '';
                }
            });
            """

            return ui.HTML(echarts_html(option, 'echart_intercrops', height=700, post_init_js=brush_js))
        
    # Brush selection results — shows species matching the selected sector
    @render.ui
    @reactive.event(input.brush_range)
    def brush_results():
        br = input.brush_range()
        if not br:
            return ui.span()

        x0_real = float(br.get('x0', 0))
        x1_real = float(br.get('x1', 100))
        y0 = float(br.get('y0', 0))
        y1 = float(br.get('y1', 9))

        # Ensure correct order
        if x0_real > x1_real:
            x0_real, x1_real = x1_real, x0_real
        if y0 > y1:
            y0, y1 = y1, y0

        df = open_csv(FILE_NAME)
        selected_plants = set(input.overview_plants() or [])

        # Filter species that overlap with selected sector
        candidates = []
        for _, row in df.iterrows():
            name = row.get('common_en', '')
            if not name or name in selected_plants:
                continue

            yrs_ini = row.get('yrs_ini_prod')
            longev = row.get('longev_prod')
            stratum = row.get('stratum')

            # Must have stratum in range
            if pd.isna(stratum) or stratum < y0 or stratum > y1:
                continue

            # Must have harvest overlap with selected X range
            if pd.isna(yrs_ini) or pd.isna(longev):
                continue

            harvest_start = float(yrs_ini)
            harvest_end = harvest_start + float(longev)

            # Check overlap: species harvest period intersects [x0, x1]
            if harvest_end < x0_real or harvest_start > x1_real:
                continue

            gf = row.get('growth_form', '')
            gf = gf if pd.notna(gf) else ''
            candidates.append((name, gf, round(stratum, 1), round(harvest_start, 1)))

        if not candidates:
            return ui.div(
                ui.p("Nenhuma espécie encontrada neste setor.", style="color:#888; text-align:center;"),
            )

        # Cross-reference WCVP native distribution + climate scores
        native_region_names = set()  # common_en names native in TDWG region
        adapted_names = set()        # common_en names with climate score >= 0.75
        try:
            lat_lon_str = input.longitude_latitude()
            if lat_lon_str:
                lat, lon = parse_lat_lon(lat_lon_str)
                from database.connection import (
                    get_climate_match_scores,
                    get_tdwg_by_coords,
                    get_native_species_in_region,
                )

                # Build sci_name <-> common_en mappings from DataFrame
                common_to_sci = {}
                sci_to_common = {}
                for _, row in df.iterrows():
                    sn = row.get('sci_name')
                    cn = row.get('common_en')
                    if pd.notna(sn) and pd.notna(cn):
                        common_to_sci[cn] = sn
                        sci_to_common[sn] = cn

                sci_names = list(sci_to_common.keys())

                # 1. Get TDWG region and check native species
                tdwg = get_tdwg_by_coords(lat, lon)
                if tdwg:
                    native_sci = get_native_species_in_region(
                        tdwg['level3_code'], sci_names
                    )
                    for sn in native_sci:
                        cn = sci_to_common.get(sn)
                        if cn:
                            native_region_names.add(cn)

                # 2. Climate match with threshold 0.70
                scores = get_climate_match_scores(
                    lat, lon, sci_names, threshold=0.70
                )
                for sn, score in scores.items():
                    cn = sci_to_common.get(sn)
                    if cn and cn not in native_region_names:
                        adapted_names.add(cn)
        except Exception:
            pass

        # Build add buttons
        def make_add_btn(name):
            safe = name.replace("'", "\\'").replace('"', '\\"')
            js = (f"var s=$('#overview_plants')[0].selectize;"
                  f"s.addOption({{value:'{safe}',text:'{safe}'}});"
                  f"s.addItem('{safe}');"
                  f"this.style.opacity='0.5';this.disabled=true;")
            return ui.tags.button(
                f"+ {name}",
                class_="btn btn-outline-success btn-sm brush-add-btn",
                onclick=js,
                style="margin: 3px;",
            )

        sections = []

        # Filter candidates into categories
        native_cands = [c for c in candidates if c[0] in native_region_names]
        adapted_cands = [c for c in candidates if c[0] in adapted_names]
        # Species in neither set are climatically incompatible — hide them

        if native_cands:
            sections.append(ui.h6(
                "\U0001f33f Nativas da região",
                style="color:#2E7D32; margin-top:8px;",
            ))
            sections.append(ui.div(
                *[make_add_btn(c[0]) for c in sorted(native_cands, key=lambda x: x[0])],
                style="display:flex; flex-wrap:wrap;",
            ))

        if adapted_cands:
            sections.append(ui.h6(
                "Não-nativas adaptadas",
                style="color:#555; margin-top:8px;",
            ))
            sections.append(ui.div(
                *[make_add_btn(c[0]) for c in sorted(adapted_cands, key=lambda x: x[0])],
                style="display:flex; flex-wrap:wrap;",
            ))

        # Fallback if no location set — show all candidates without classification
        if not native_cands and not adapted_cands:
            sections.append(ui.h6("Espécies disponíveis", style="color:#555; margin-top:8px;"))
            sections.append(ui.div(
                *[make_add_btn(c[0]) for c in sorted(candidates, key=lambda x: x[0])],
                style="display:flex; flex-wrap:wrap;",
            ))

        # Range info
        if x0_real < 1:
            range_label = f"{int(round(x0_real*12))}m – {round(x1_real, 1)}a"
        else:
            range_label = f"{round(x0_real, 1)}a – {round(x1_real, 1)}a"

        sections.insert(0, ui.p(
            f"Período: {range_label} | Estrato: {round(y0,1)}–{round(y1,1)} | {len(candidates)} espécies",
            style="font-size:0.85em; color:#777; margin-bottom:4px;",
        ))

        return ui.div(*sections)

    #This function creates a card showing what species are incompatible with each other
    @output
    @render.ui
    def compatibility():
        if input.database_choice() == "try": #Ignore the creation of the graph if the we don't select the good data source
            df=open_csv(FILE_NAME)
            plants=input.overview_plants()
            issue=[]
            cards=[]
            print(plants)
            for i in range(len(plants)-1):
                plant=plants[i]
                _match = df[df['common_en'] == plant][['common_en','yrs_ini_prod','longev_prod','stratum']].values.tolist()
                if not _match:
                    continue
                query = _match[0]
                if str(query[1])=='nan' or str(query[2])=='nan' or str(query[3])=='nan':
                    continue
                else:
                    for j in range(i+1,len(plants)):
                        other_plt=plants[j]
                        _omatch = df[df['common_en'] == other_plt][['common_en','yrs_ini_prod','longev_prod','stratum']].values.tolist()
                        if not _omatch:
                            continue
                        opposite = _omatch[0]
                        if str(opposite[1])=='nan' or str(opposite[2])=='nan' or str(opposite[3])=='nan':
                            continue
                        else:
                            if opposite[3]==query[3]:
                                if query[1]<=opposite[1] and query[1]+query[2]>=opposite[1]:
                                    issue.append((query[0],opposite[0]))
                                    
                                elif query[1]>=opposite[1] and query[1]<=opposite[1]+opposite[2]:
                                    issue.append((query[0],opposite[0]))
            for plants in issue:
                
                card=ui.card(
                        ui.div(
                            ui.h4("Non compatibilty", class_="card_title"),
                            ui.a(f"{plants[0]} and \n {plants[1]}"))
                        )
                cards.append(card)

            return ui.layout_columns(*cards, col_widths=[4,4,4])


    # This function is an auxiliary function used to separate a list of plants to make others function (card_wrong_plants and intercrops) run faster
    def tri():
        df=open_csv(FILE_NAME)
        plants=input.overview_plants()
        good,bad_year,bad_stratum=[],[],[]
        for plant in plants:
            _tmatch = df[df['common_en'] == plant][['common_en','growth_form','yrs_ini_prod','longev_prod','stratum']].values.tolist()
            if not _tmatch:
                continue
            query = _tmatch[0]
            if str(query[2])!='nan' and str(query[3])!='nan' and str(query[4])!='nan': 
                good.append(query)
            elif str(query[4])=='nan':
                bad_stratum.append(query[0])
            else:
                bad_year.append(query[0])
        return [good,bad_year,bad_stratum]

    # This function run the R code to get the new species list if the GIFT database is chosen. Otherwise it returns the Practitioner's Database
    @reactive.event(input.update_map)
    def get_new_species():
        if input.database_choice() == "gift":
            global SPECIES_GIFT_DATAFRAME
            flor_group=FLORISTIC_GROUP[input.floristic_group()]

            lat, lon = parse_lat_lon(input.longitude_latitude())
            robjects.r.assign("flor_group",flor_group)
            robjects.r.assign("long",float(lon))
            robjects.r.assign("lat",float(lat))
            data = robjects.r(f'''
                            library("GIFT")
                coord <- cbind(long,lat)
                natvasc <- GIFT_checklists(taxon_name="Tracheophyta",
                                        complete_taxon=F,
                                        floristic_group=flor_group,
                                        complete_floristic=F,
                                        coordinates = coord,
                                        overlap="extent_intersect",
                                        list_set_only=F,
                                        remove_overlap=T,
                                        area_threshold_mainland=100)
                natvasc[["lists"]]
                natvascl <- natvasc[["checklists"]]
                df <- data.frame(natvascl)
                df
                ''')
            with localconverter(robjects.default_converter + pandas2ri.converter):
                new_species = robjects.conversion.rpy2py(data)
            SPECIES_GIFT_DATAFRAME=new_species

            # Group by native vs non-native (Figma: "NATIVAS SUGERIDAS" / "NÃO-NATIVAS")
            grouped = {}
            native_key = "NATIVAS SUGERIDAS / NATIVE SUGGESTIONS"
            nonnative_key = "NÃO-NATIVAS ADAPTADAS / NON-NATIVE ADAPTED"

            native_species = {}
            nonnative_species = {}

            for _, row in new_species.iterrows():
                name = row.get("work_species", "")
                if not name:
                    continue
                is_native = row.get("native", 0)
                if is_native == 1:
                    native_species[name] = name
                else:
                    nonnative_species[name] = name

            # Sort each group
            if native_species:
                grouped[native_key] = dict(sorted(native_species.items()))
            if nonnative_species:
                grouped[nonnative_key] = dict(sorted(nonnative_species.items()))

            # Fallback: if no grouping possible, group by family
            if not grouped:
                families = new_species['family'].unique()
                families_clean = sorted(families.tolist())
                for family in families_clean:
                    grouped[family] = {}
                    plants = new_species.query("family == '%s'" % family)['work_species'].tolist()
                    plants.sort()
                    for plant in plants:
                        grouped[family][plant] = plant

            return grouped
        else:
            return _get_plants_with_climate_score()

    def _build_search_label(common_en, common_pt=None, sci_name=None, pct=None):
        """Build a selectize label searchable by common_en, common_pt and sci_name.

        Display: "avocado · abacate · Persea americana (85%)"
        Selectize searches the full label text, so typing any name matches.
        """
        parts = [common_en]
        if common_pt and str(common_pt) != common_en:
            parts.append(str(common_pt))
        if sci_name:
            parts.append(str(sci_name))
        label = " · ".join(parts)
        if pct is not None:
            label += f" ({pct}%)"
        return label

    def _get_plants_default(df=None):
        """Fallback: group by growth_form with searchable labels (common_pt + sci_name)."""
        if df is None:
            df = pd.read_csv(FILE_NAME)
        life_forms = sorted([f for f in df["growth_form"].dropna().unique()])
        result = {}
        for gf in life_forms:
            group = {}
            subset = df[df["growth_form"] == gf]
            for _, row in subset.iterrows():
                cn = row.get('common_en')
                if not pd.notna(cn):
                    continue
                pt = row.get('common_pt')
                pt = pt if pd.notna(pt) else None
                sn = row.get('sci_name')
                sn = sn if pd.notna(sn) else None
                group[cn] = _build_search_label(cn, pt, sn)
            if group:
                result[gf] = dict(sorted(group.items()))
        return result

    def _get_plants_with_climate_score():
        """Return selectize choices ordered by climate match score when location is available.

        Groups:
        1. ADAPTADAS AO CLIMA - CSV species with climate score
        2. CULTIVADAS ADAPTADAS - EcoCrop cultivated species with climate score
        3. OUTRAS ESPÉCIES - CSV species without score
        """
        df = pd.read_csv(FILE_NAME)

        # Build lookup tables for common_pt and sci_name
        common_pt_map = {}
        sci_name_map = {}
        for _, row in df.iterrows():
            cn = row.get('common_en')
            if pd.notna(cn):
                pt = row.get('common_pt')
                if pd.notna(pt):
                    common_pt_map[cn] = pt
                sn = row.get('sci_name')
                if pd.notna(sn):
                    sci_name_map[cn] = sn

        # Try to get coordinates from user's location input
        try:
            lat_lon_str = input.longitude_latitude()
            if lat_lon_str:
                lat, lon = parse_lat_lon(lat_lon_str)
            else:
                lat, lon = None, None
        except Exception:
            lat, lon = None, None

        # If we have coordinates, try to compute climate scores
        scores = {}
        if lat is not None and lon is not None:
            try:
                from database.connection import get_climate_match_scores
                sci_names = df['sci_name'].dropna().unique().tolist()
                scores = get_climate_match_scores(lat, lon, sci_names, threshold=0.3)
            except Exception as e:
                logging.warning(f"[SPECIES] Climate scoring unavailable: {e}")

        if scores:
            # Build a mapping from sci_name → common_en
            sci_to_common = {}
            for _, row in df.iterrows():
                sn = row.get('sci_name')
                cn = row.get('common_en')
                if pd.notna(sn) and pd.notna(cn):
                    sci_to_common[sn] = cn

            # Reverse mapping for dedup
            csv_sci_names = set(df['sci_name'].dropna().unique())

            # Build scored and unscored lists
            scored = []  # (common_en, score)
            unscored = []  # (common_en,)
            seen = set()

            for sci_name, score in scores.items():
                common = sci_to_common.get(sci_name)
                if common and common not in seen:
                    scored.append((common, score))
                    seen.add(common)

            # Add species without climate data
            for _, row in df.iterrows():
                cn = row.get('common_en')
                if pd.notna(cn) and cn not in seen:
                    unscored.append(cn)
                    seen.add(cn)

            # Sort scored by score desc, unscored alphabetically
            scored.sort(key=lambda x: (-x[1], x[0]))
            unscored.sort()

            # Build grouped dict: scored species first, then unscored
            result = {}
            adapted_key = "ADAPTADAS AO CLIMA / CLIMATE ADAPTED"
            cultivated_key = "CULTIVADAS ADAPTADAS / CULTIVATED SPECIES"
            other_key = "OUTRAS ESPÉCIES / OTHER SPECIES"

            adapted = {}
            for common, score in scored:
                pct = int(round(score * 100))
                label = _build_search_label(
                    common, common_pt_map.get(common), sci_name_map.get(common), pct
                )
                adapted[common] = label

            # Fetch cultivated species from EcoCrop with climate scoring
            cultivated = {}
            try:
                from database.connection import get_cultivated_species
                cult_species = get_cultivated_species(lat, lon, threshold=0.3)
                for sp in cult_species:
                    sci = sp['canonical_name']
                    # Skip if already in CSV (CSV has priority)
                    if sci in csv_sci_names:
                        continue
                    display = sp['common_name'] or sci
                    if display in seen:
                        continue
                    seen.add(display)
                    score_val = sp.get('score')
                    if score_val is not None and score_val > 0:
                        pct = int(round(score_val * 100))
                        label = _build_search_label(display, None, sci, pct)
                        cultivated[display] = label
            except Exception as e:
                logging.warning(f"[SPECIES] Cultivated species unavailable: {e}")

            others = {}
            for common in unscored:
                label = _build_search_label(
                    common, common_pt_map.get(common), sci_name_map.get(common)
                )
                others[common] = label

            if adapted:
                result[adapted_key] = adapted
            if cultivated:
                result[cultivated_key] = cultivated
            if others:
                result[other_key] = others

            return result
        else:
            # No climate data — fall back to default grouping
            return _get_plants_default(df)

    # This function updates the choices on the sidebar of main species
    @reactive.effect
    @reactive.event(input.update_map)
    def update_main_species():
        choices = get_new_species()
        ui.update_selectize(
            "overview_plants",
            choices=choices,
            selected=[],
        )

    # #This function allows to download the species
    # Replace both download functions with these modified versions
    # * for now we are removing this button.
    @output
    @render.download(filename=f"selected_species_data.csv")
    def export_df():
        if input.database_choice() == "try":
            # Get the full dataset
            df = open_csv(FILE_NAME)
            # Filter only selected plants
            plants = input.overview_plants()
            selected_df = df[df['common_en'].isin(plants)]
            # Return the filtered CSV
            yield selected_df.to_csv(index=False)
        else:
            # For GIFT database
            global SPECIES_GIFT_DATAFRAME
            selected_plants = input.overview_plants()
            
            if SPECIES_GIFT_DATAFRAME.empty:
                yield "No data available."
            elif 'work_species' in SPECIES_GIFT_DATAFRAME.columns:
                # Filter by selected plants
                selected_df = SPECIES_GIFT_DATAFRAME[SPECIES_GIFT_DATAFRAME['work_species'].isin(selected_plants)]
                yield selected_df.to_csv(index=False)
            else:
                yield "Unable to filter GIFT database."
                
    @output
    @render.download(filename=lambda: f"selected_{input.database_choice().replace(' ', '_').lower()}_data.csv")
    def export_df_os():
        if input.database_choice() == "try":
            df = open_csv(FILE_NAME)
            plants = input.overview_plants()
            
            # Filter to only include selected plants
            selected_df = df[df['common_en'].isin(plants)]
            
            # Keep only the columns we want
            selected_columns = ['common_en', 'growth_form', 'plant_max_height', 'stratum', 
                            'family', 'function', 'yrs_ini_prod', 'life_hist', 
                            'longev_prod', 'threat_status']
            
            # Select columns that exist in the dataframe
            columns_to_keep = [col for col in selected_columns if col in selected_df.columns]
            selected_df = selected_df[columns_to_keep]
            
            # Format the dataframe
            selected_df = selected_df.fillna("-")
            selected_df = selected_df.sort_values(by='common_en')
            
            yield selected_df.to_csv(index=False)
        else:
            global SPECIES_GIFT_DATAFRAME
            if SPECIES_GIFT_DATAFRAME.empty:
                print("SPECIES_GIFT_DATAFRAME is not populated.")
                yield "Data not available."
            else:
                # Filter by selected plants
                selected_plants = input.overview_plants()
                
                if 'work_species' in SPECIES_GIFT_DATAFRAME.columns:
                    selected_df = SPECIES_GIFT_DATAFRAME[SPECIES_GIFT_DATAFRAME['work_species'].isin(selected_plants)]
                    
                    # Format the dataframe
                    selected_df = selected_df.fillna("-")
                    selected_df = selected_df.sort_values("family")
                    
                    # Remove unnecessary columns
                    unnecessary_columns = ['ref_ID', 'list_ID', 'entity_ID', 'work_ID', 'genus_ID', 
                                        'questionable', 'quest_native', 'endemic_ref', 
                                        'quest_end_ref', 'quest_end_list']
                    
                    # Only drop columns that exist
                    columns_to_drop = [col for col in unnecessary_columns if col in selected_df.columns]
                    if columns_to_drop:
                        selected_df = selected_df.drop(columns=columns_to_drop)
                    
                    yield selected_df.to_csv(index=False)
                else:
                    yield "Unable to filter GIFT database. Column structure may be different than expected."
##Growth Form

    #  This functions creates the barchart and make it evolve depending on the lifetime chosen

    @render.ui
    @reactive.event(input.life_time, input.overview_plants)
    def plot_plants():
        if input.database_choice() == "try":
            size = input.life_time()
            df = open_csv(FILE_NAME)
            plants = input.overview_plants()

            color_discrete_map = color_mapping.copy()
            color_discrete_map['removed'] = 'black'

            if not plants:
                return ui.HTML('<div style="text-align:center;padding:40px;color:#888;">Nenhuma espécie selecionada</div>')

            species_names = []
            bar_data = []
            color_change = set()

            for plant in plants:
                query = df[df['common_en'] == plant][
                    [
                        'common_en', 'growth_form', 'plant_max_height',
                        'family', 'function', 'yrs_ini_prod',
                        'life_hist', 'longev_prod', 'threat_status', 'ref'
                    ]
                ].values.tolist()

                if not query:
                    continue

                query = query[0]
                name = query[0]
                growth_type = str(query[1])
                max_height = 3 if pd.isna(query[2]) else query[2]
                fam = str(query[3])
                func = str(query[4])
                ttfh = str(query[5])
                lh = str(query[6])
                lp = str(query[7])

                expect = 7 if pd.isna(query[7]) or query[7] == 0 else query[7]

                if size == 0:
                    graph_y_value = 0.1
                else:
                    graph_y_value = min(max_height, size * max_height / expect)

                is_dead = size > expect
                if is_dead:
                    color_change.add(name)

                bar_color = 'black' if is_dead else color_discrete_map.get(growth_type, 'grey')

                tooltip_text = (
                    f"<b>{name}</b><br/>"
                    f"Altura máxima: {round(max_height, 1)} m<br/>"
                    f"Família: {fam}<br/>"
                    f"Forma: {growth_type}<br/>"
                    f"Função: {func}<br/>"
                    f"Tempo até colheita: {ttfh}<br/>"
                    f"Ciclo de vida: {lh}<br/>"
                    f"Longevidade: {lp}"
                )

                species_names.append(name)
                bar_data.append({
                    'value': round(graph_y_value, 2),
                    'itemStyle': {'color': bar_color},
                    'tooltip_text': tooltip_text,
                })

            if not species_names:
                return ui.HTML('<div style="text-align:center;padding:40px;color:#888;">Nenhuma espécie selecionada</div>')

            # Build tooltip formatter that reads from data
            bar_series_data = []
            for d in bar_data:
                bar_series_data.append({
                    'value': d['value'],
                    'itemStyle': d['itemStyle'],
                })

            # Build tooltip texts array for JS
            tooltip_texts = [d['tooltip_text'] for d in bar_data]
            tooltip_texts_json = json.dumps(tooltip_texts, ensure_ascii=False)

            option = {
                'title': {
                    'text': f'Crescimento das espécies no ano {size}',
                    'left': 'center',
                    'textStyle': {'fontSize': 14, 'fontFamily': 'Inter, sans-serif'},
                },
                'tooltip': {
                    'trigger': 'axis',
                    'axisPointer': {'type': 'shadow'},
                    'formatter': f'__JS__function(params){{var t={tooltip_texts_json};var i=params[0].dataIndex;return t[i]||"";}}__JSEND__',
                },
                'grid': {'left': 60, 'right': 30, 'top': 50, 'bottom': 80},
                'xAxis': {
                    'type': 'category',
                    'data': species_names,
                    'axisLabel': {
                        'rotate': 45,
                        'fontFamily': 'Inter, sans-serif',
                        'fontSize': 11,
                        'color': '#171717',
                    },
                },
                'yAxis': {
                    'type': 'value',
                    'name': 'Altura (m)',
                    'nameTextStyle': {'fontFamily': 'Inter, sans-serif', 'fontSize': 13},
                    'splitLine': {'show': False},
                },
                'series': [{
                    'type': 'bar',
                    'data': bar_series_data,
                }],
                'backgroundColor': '#d3d3d3',
                'textStyle': {'fontFamily': 'Inter, sans-serif'},
            }

            return ui.HTML(echarts_html(option, 'echart_plot_plants', height=650))
        
## * Results
    # Define available columns based on database choice
    def get_available_columns():
        if input.database_choice() == "try":
            # Columns for Practitioner's Database
            return [
                "common_en", "growth_form", "plant_max_height", "stratum", 
                "family", "function", "yrs_ini_prod", "life_hist", 
                "longev_prod", "threat_status", "ref"
            ]
        else:
            # Columns for GIFT Database
            # Adjust these based on your actual GIFT database structure
            gift_columns = [
                "work_species", "taxon_name", "taxon_rank", "family", 
                "genus", "endemic", "native", "naturalized"
            ]
            # Add any other columns that exist in SPECIES_GIFT_DATAFRAME
            if not SPECIES_GIFT_DATAFRAME.empty:
                # Get all columns except those that are typically unnecessary
                unnecessary = ['ref_ID', 'list_ID', 'entity_ID', 'work_ID', 'genus_ID', 
                            'questionable', 'quest_native', 'endemic_ref', 
                            'quest_end_ref', 'quest_end_list']
                all_cols = [col for col in SPECIES_GIFT_DATAFRAME.columns 
                            if col not in unnecessary]
                # Update gift_columns with any missing columns
                for col in all_cols:
                    if col not in gift_columns:
                        gift_columns.append(col)
            return gift_columns

    # Update checkbox options based on database selection
    @reactive.effect
    @reactive.event(input.database_choice, input.update_map)
    def update_column_choices():
        available_cols = get_available_columns()
        
        # Get readable column names for display (PT-BR from Figma)
        readable_cols = {col: COLUMN_DISPLAY_NAMES.get(col, col.replace('_', ' ').title()) for col in available_cols}
        
        # Set default selections (first few columns)
        default_selected = available_cols[:5] if len(available_cols) >= 5 else available_cols
        
        ui.update_checkbox_group(
            "selected_columns",
            choices=readable_cols,
            selected=default_selected
        )

    # Modified suggestion_plants function to use selected columns
    @output
    @render.ui
    @reactive.event(input.update_map, input.selected_columns, input.overview_plants)
    def suggestion_plants():
        if input.database_choice() == "try":
            df = open_csv(FILE_NAME)
            plants = input.overview_plants()
            
            # Filter the dataframe to only include the selected plants
            selected_plants_df = df[df['common_en'].isin(plants)]
            
            # Get selected columns (convert from readable back to actual column names if needed)
            columns = list(input.selected_columns())

            # Ensure "common_en" is always included for identification
            if "common_en" not in columns and "common_en" in df.columns:
                columns = ["common_en"] + columns
                
            # Filter to only include columns that exist in the dataframe
            valid_columns = [col for col in columns if col in selected_plants_df.columns]
            
            if not valid_columns:
                return ui.p("Please select at least one valid column to display.")
                
            # Select only the desired columns
            selected_plants_df = selected_plants_df[valid_columns]
            
            # Fill NA values with "-" for better display
            table = selected_plants_df.fillna("-")
            
            # Sort by common_en for consistent ordering (if available)
            if "common_en" in valid_columns:
                table = table.sort_values(by='common_en')
            table = table.reset_index(drop=True)
            
            # Display custom HTML table (Figma design)
            return ui.HTML(_render_results_table(table, valid_columns))

        else:  # For GIFT database
            if SPECIES_GIFT_DATAFRAME.empty:
                return ui.p("No species data available. Please update your location.")
            
            # Filter GIFT dataframe to only include selected plants
            selected_plants = input.overview_plants()
            
            # Check if we have plant names in the work_species column
            if 'work_species' in SPECIES_GIFT_DATAFRAME.columns:
                selected_gift_df = SPECIES_GIFT_DATAFRAME[SPECIES_GIFT_DATAFRAME['work_species'].isin(selected_plants)]
            else:
                # If not, we might need to adapt this based on your GIFT dataframe structure
                return ui.p("Unable to filter GIFT database. Please check column structure.")
            
            # Get selected columns from input
            columns = list(input.selected_columns())

            # Ensure species identifier column is always included
            id_column = 'work_species' if 'work_species' in selected_gift_df.columns else None
            if id_column and id_column not in columns:
                columns = [id_column] + columns
                
            # Filter to only include valid columns
            valid_columns = [col for col in columns if col in selected_gift_df.columns]
            
            if not valid_columns:
                return ui.p("Please select at least one valid column to display.")
                
            # Select only the chosen columns
            selected_gift_df = selected_gift_df[valid_columns]
            
            # Clean up the dataframe
            table = selected_gift_df.fillna("-")
            
            # Sort by appropriate column
            if id_column and id_column in valid_columns:
                table = table.sort_values(id_column)
            elif 'family' in valid_columns:
                table = table.sort_values('family')
                
            table = table.reset_index(drop=True)
            
            return ui.HTML(_render_results_table(table, valid_columns))

    # Also update the export function to use selected columns
    @output
    @render.download(filename=lambda: f"selected_{input.database_choice().replace(' ', '_').lower()}_data.csv")
    def export_df_os():
        if input.database_choice() == "try":
            df = open_csv(FILE_NAME)
            plants = input.overview_plants()
            
            # Filter to only include selected plants
            selected_df = df[df['common_en'].isin(plants)]
            
            # Get selected columns
            columns = list(input.selected_columns())

            # Ensure "common_en" is always included
            if "common_en" not in columns and "common_en" in df.columns:
                columns = ["common_en"] + columns
                
            # Only use columns that exist
            valid_columns = [col for col in columns if col in selected_df.columns]
            
            if valid_columns:
                selected_df = selected_df[valid_columns]
            
            # Format the dataframe
            selected_df = selected_df.fillna("-")
            
            if "common_en" in valid_columns:
                selected_df = selected_df.sort_values(by='common_en')

            # Rename columns to PT-BR display names for the CSV
            rename_map = {c: COLUMN_DISPLAY_NAMES.get(c, c) for c in valid_columns}
            yield selected_df.rename(columns=rename_map).to_csv(index=False)
        else:
            global SPECIES_GIFT_DATAFRAME
            if SPECIES_GIFT_DATAFRAME.empty:
                print("SPECIES_GIFT_DATAFRAME is not populated.")
                yield "Data not available."
            else:
                # Filter by selected plants
                selected_plants = input.overview_plants()
                
                if 'work_species' in SPECIES_GIFT_DATAFRAME.columns:
                    selected_df = SPECIES_GIFT_DATAFRAME[SPECIES_GIFT_DATAFRAME['work_species'].isin(selected_plants)]
                    
                    # Get selected columns
                    columns = list(input.selected_columns())

                    # Ensure species identifier is always included
                    if "work_species" not in columns and "work_species" in selected_df.columns:
                        columns = ["work_species"] + columns
                    
                    # Only use columns that exist
                    valid_columns = [col for col in columns if col in selected_df.columns]
                    
                    if valid_columns:
                        selected_df = selected_df[valid_columns]
                    
                    # Format the dataframe
                    selected_df = selected_df.fillna("-")
                    
                    if "work_species" in valid_columns:
                        selected_df = selected_df.sort_values("work_species")
                    elif "family" in valid_columns:
                        selected_df = selected_df.sort_values("family")
                    
                    yield selected_df.to_csv(index=False)
                else:
                    yield "Unable to filter GIFT database. Column structure may be different than expected."
                    
    @render.image
    def climate_image():
        img_path = "data/img/climate.png"  # Replace with your image file name
        return {"src": img_path, "alt": "Climate Image"}


    @render.image
    def main_species_image():
        img_path = "data/img/main_species.png"  # Replace with your image file name
        return {"src": img_path, "alt": "Main Species Image"}

    @render.image
    def growth_form_image():
        img_path = "data/img/growth_form_graph.png"  # Replace with your image file name
        return {"src": img_path, "alt": "Growth Form"}