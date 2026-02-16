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

# Preload ecoregion shapefile in background thread at module import
_ECOREGION_SHP_PATH = os.path.join(Path(__file__).parent.parent, "data", "ecoregions_raster", "Ecoregions2017.shp")
_ECOREGION_GDF_CACHE = {"gdf": None}

def _preload_ecoregions():
    try:
        logging.info("[PRELOAD] Loading Ecoregions2017.shp into memory...")
        gdf = gpd.read_file(_ECOREGION_SHP_PATH)
        _ = gdf.sindex  # build spatial index
        _ECOREGION_GDF_CACHE["gdf"] = gdf
        logging.info(f"[PRELOAD] Ecoregions loaded: {len(gdf)} features, sindex ready")
    except Exception as e:
        logging.warning(f"[PRELOAD] Failed to load ecoregions: {e}")

import threading
threading.Thread(target=_preload_ecoregions, daemon=True).start()


COLOR = {'herb' : '#f8827a','climber':"#dbb448",'subshrub' : "#779137",'shrub' :'#45d090','cactus' : '#49d1d5','bamboo' : '#53c5ff','tree' : '#d7a0ff','palm' : '#ff8fda'}

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
colors = ['#53c5ff', '#49d1d5', '#dbb448', '#f8827a', '#ff8fda', '#45d090', '#779137', '#d7a0ff']
color_mapping = dict(zip(growth_forms, colors))

# ECharts emoji mapping per growth form
ECHARTS_EMOJIS = {
    'tree': '🌲',
    'shrub': '🌳',
    'subshrub': '🌿',
    'forb': '🌼',
    'herb': '🌼',
    'graminoid': '🌾',
    'palm': '🌴',
    'liana': '🪢',
    'vine': '🌱',
    'climber': '🌱',
    'scrambler': '🪴',
    'bamboo': '🎋',
    'cactus': '🌵',
    'other': '🍃',
}

# Keep old symbol dict for backwards compat (used nowhere else now)
ECHARTS_SYMBOLS = {k: 'circle' for k in ECHARTS_EMOJIS}


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
        # Add OpenStreetMap layer (default)
        folium.TileLayer("OpenStreetMap").add_to(world_map)

        # Add Satellite layer
        folium.TileLayer(
            tiles="https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
            attr="Map data © Google",
            name="Satellite",
            subdomains=["mt0", "mt1", "mt2", "mt3"]
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

        # Add a scale bar and a fullscreen button for better usability
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

        # Add ecoregion overlay — only the ecoregion at the user's point
        if lat is not None and lon is not None:
            try:
                eco_gdf = _find_ecoregion_at_point(lat, lon)
                if eco_gdf is not None:
                    # Simplify only this single polygon for fast rendering
                    display = eco_gdf[["geometry", "ECO_NAME", "BIOME_NAME", "BIOME_NUM", "REALM"]].copy()
                    display["geometry"] = display["geometry"].simplify(tolerance=0.01, preserve_topology=True)
                    folium.GeoJson(
                        display.to_json(),
                        name="Ecorregião",
                        style_function=_biome_style,
                        tooltip=folium.GeoJsonTooltip(
                            fields=["ECO_NAME", "BIOME_NAME"],
                            aliases=["Ecorregião:", "Bioma:"],
                            style="font-size: 12px;",
                        ),
                    ).add_to(m)
            except Exception:
                pass

        # Add marker
        if lat is not None and lon is not None:
            try:
                eco = _query_ecoregion(lat, lon)
                popup_text = f"Lat: {lat:.4f}, Lon: {lon:.4f}"
                if eco:
                    popup_text = (
                        f"<b>{eco['eco_name']}</b><br>"
                        f"Biome: {eco['biome_name']}<br>"
                        f"Realm: {eco['realm']}"
                    )
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


##Main Species

    @render.ui
    @reactive.event(input.overview_plants, input.stratum_bins, input.harvest_bins,
                    input.filter_growth_form, input.filter_plant_use, input.filter_threat,
                    input.filter_nfix, input.filter_deciduousness)
    def intercrops():
        if input.database_choice() == "try":
            df = open_csv(FILE_NAME)
            plants = list(input.overview_plants())

            if not plants:
                return ui.HTML('<div style="text-align:center;padding:40px;color:#888;">Nenhuma espécie selecionada</div>')

            # Apply filters to selected species
            f_growth = input.filter_growth_form()
            f_use = input.filter_plant_use()
            f_threat = input.filter_threat()
            f_nfix = input.filter_nfix()
            f_decid = input.filter_deciduousness()

            if f_growth or f_use or f_threat or f_nfix or f_decid:
                filtered = df[df['common_en'].isin(plants)]
                if f_growth:
                    filtered = filtered[filtered['growth_form'] == f_growth]
                if f_use:
                    filtered = filtered[
                        filtered['function'].str.contains(f_use, case=False, na=False) |
                        filtered['function2'].str.contains(f_use, case=False, na=False)
                    ] if 'function2' in filtered.columns else filtered[
                        filtered['function'].str.contains(f_use, case=False, na=False)
                    ]
                if f_threat:
                    filtered = filtered[filtered['threat_status'] == f_threat]
                if f_nfix:
                    if f_nfix == "yes":
                        filtered = filtered[filtered['family'] == 'Fabaceae']
                    else:
                        filtered = filtered[filtered['family'] != 'Fabaceae']
                if f_decid:
                    if f_decid == "semi":
                        filtered = filtered[filtered['leaf_phenol'].str.contains('semi', case=False, na=False)]
                    else:
                        filtered = filtered[filtered['leaf_phenol'].str.contains(f_decid, case=False, na=False)]
                plants = filtered['common_en'].tolist()

                if not plants:
                    return ui.HTML('<div style="text-align:center;padding:40px;color:#888;">Nenhuma espécie corresponde aos filtros</div>')

            # Categorize species by available data
            complete_data = []
            missing_harvest = []
            missing_stratum = []
            missing_both = []

            for plant in plants:
                query = df.query("common_en == '%s'" % plant)[
                    ['common_en', 'growth_form', 'yrs_ini_prod', 'longev_prod', 'stratum']
                ].values.tolist()

                if not query:
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
                min_x_real = round(min(all_x_values_real), 2)
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
            gf_colors = ['#d7a0ff', '#45d090', '#779137', '#f8827a', '#8BC34A', '#ff8fda', '#dbb448', '#66BB6A', '#26A69A', '#53c5ff', '#9E9E9E']
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
            left_x0 = round(min_x - (max_x - min_x) * 0.2, 2)
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
                safe_name = name.replace("'", "\\'")
                tooltip_text = (f"<b>{safe_name}</b><br/>Forma: {growth_type}<br/>"
                                f"Início colheita: {round(x_start, 2)} anos<br/>"
                                f"Duração: {round(duration, 2)} anos<br/>"
                                f"Estrato: {round(y_position, 2)}")

                gf_emoji = ECHARTS_EMOJIS.get(growth_type, '🍃')
                gf_color = color_map.get(growth_type, '#999')

                # Harvest period line endpoints (in sqrt-space)
                x_line_start = round(sqrt_transform(x_start), 4)
                x_line_end = round(sqrt_transform(x_start + duration), 4)

                species_series.append({
                    'type': 'scatter',
                    'name': name,
                    'data': [[round(x_final, 4), round(y_final, 3)]],
                    'symbol': 'circle',
                    'symbolSize': 24,
                    'itemStyle': {'color': 'transparent'},
                    'label': {
                        'show': True,
                        'formatter': f'{gf_emoji} {name}',
                        'fontSize': 11,
                        'offset': [0, 0],
                        'color': '#333',
                        'fontFamily': 'Inter, sans-serif',
                    },
                    'tooltip': {'formatter': f'__JS__function(){{return \'{tooltip_text}\';}}__JSEND__'},
                    'markLine': {
                        'silent': True,
                        'symbol': ['circle', 'arrow'],
                        'symbolSize': [4, 6],
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
                px_val = round(min_x - (max_x - min_x) * 0.1 - x_offset, 4)
                py_val = round(y_position + y_offset, 3)

                # Feature 1: check if species has exit time but no entry time
                has_exit_time = exit_duration is not None and str(exit_duration) != 'nan'
                exit_years = round(exit_duration, 1) if has_exit_time else None

                safe_name = name.replace("'", "\\'")
                if has_exit_time:
                    tooltip_text = (f"<b>{safe_name}</b><br/>Forma: {growth_type}<br/>"
                                    f"ℹ️ Tempo de saída: {exit_years} anos, entrada desconhecida<br/>"
                                    f"Estrato: {round(y_position, 2)}")
                    partial_info_count += 1
                else:
                    tooltip_text = (f"<b>{safe_name}</b><br/>Forma: {growth_type}<br/>"
                                    f"⚠️ Colheita: Desconhecida<br/>"
                                    f"Estrato: {round(y_position, 2)}")

                gf_emoji = ECHARTS_EMOJIS.get(growth_type, '🍃')
                # Combine emoji + ℹ️ when exit time is known
                label_text = f'{gf_emoji} ℹ️' if has_exit_time else gf_emoji

                series_entry = {
                    'type': 'scatter',
                    'name': name,
                    'data': [[px_val, py_val]],
                    'symbol': 'circle',
                    'symbolSize': 24,
                    'itemStyle': {'color': 'transparent'},
                    'label': {
                        'show': True,
                        'formatter': f'{label_text} {name}',
                        'fontSize': 11,
                        'offset': [0, 0],
                        'color': '#333',
                        'fontFamily': 'Inter, sans-serif',
                    },
                    'tooltip': {'formatter': f'__JS__function(){{return \'{tooltip_text}\';}}__JSEND__'},
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
                safe_name = name.replace("'", "\\'")
                tooltip_text = (f"<b>{safe_name}</b><br/>Forma: {growth_type}<br/>"
                                f"Início colheita: {round(x_start, 2)} anos<br/>"
                                f"Duração: {round(duration, 2)} anos<br/>"
                                f"⚠️ Estrato: Desconhecido")

                gf_emoji = ECHARTS_EMOJIS.get(growth_type, '🍃')
                gf_color = color_map.get(growth_type, '#999')

                # Harvest period line (in sqrt-space)
                x_line_start = round(sqrt_transform(x_start), 4)
                x_line_end = round(sqrt_transform(x_start + duration), 4)
                y_pt = round(-1 + y_off, 3)

                species_series.append({
                    'type': 'scatter',
                    'name': name,
                    'data': [[round(x_center + x_off, 4), y_pt]],
                    'symbol': 'circle',
                    'symbolSize': 24,
                    'itemStyle': {'color': 'transparent'},
                    'label': {
                        'show': True,
                        'formatter': f'{gf_emoji} {name}',
                        'fontSize': 11,
                        'offset': [0, 0],
                        'color': '#333',
                        'fontFamily': 'Inter, sans-serif',
                    },
                    'tooltip': {'formatter': f'__JS__function(){{return \'{tooltip_text}\';}}__JSEND__'},
                    'markLine': {
                        'silent': True,
                        'symbol': ['circle', 'arrow'],
                        'symbolSize': [4, 6],
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
                x_pos = round(min_x - (max_x - min_x) * 0.15 + col * 0.03 * (max_x - min_x), 4)
                y_pos = round(-1 - row * 0.4, 3)

                safe_name = name.replace("'", "\\'")
                tooltip_text = (f"<b>{safe_name}</b><br/>Forma: {growth_type}<br/>"
                                f"⚠️ Colheita: Desconhecida<br/>"
                                f"⚠️ Estrato: Desconhecido")

                gf_emoji = ECHARTS_EMOJIS.get(growth_type, '🍃')
                species_series.append({
                    'type': 'scatter',
                    'name': name,
                    'data': [[x_pos, y_pos]],
                    'symbol': 'circle',
                    'symbolSize': 24,
                    'itemStyle': {'color': 'transparent'},
                    'label': {
                        'show': True,
                        'formatter': f'{gf_emoji} {name}',
                        'fontSize': 11,
                        'offset': [0, 0],
                        'color': '#333',
                        'fontFamily': 'Inter, sans-serif',
                    },
                    'tooltip': {'formatter': f'__JS__function(){{return \'{tooltip_text}\';}}__JSEND__'},
                })
                legend_names.append(name)
                added_species.add(name)

            # Build Y-axis label formatter as JS function
            sorted_label_items = sorted(y_labels.items(), key=lambda x: x[0])
            y_label_map_js = json.dumps({str(pos): label for pos, label in sorted_label_items})
            js_y_formatter = f"__JS__function(value){{var m={y_label_map_js};return m[String(value)]||'';}}__JSEND__"

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
                'tree': 'Árvore', 'shrub': 'Arbusto', 'subshrub': 'Subarbusto',
                'forb': 'Erva', 'graminoid': 'Graminóide', 'palm': 'Palmeira',
                'liana': 'Liana', 'vine': 'Trepadeira', 'scrambler': 'Escandente',
                'bamboo': 'Bambu', 'other': 'Outro',
            }

            # Fixed legend series (growth forms at top)
            fixed_legend_x_vals = np.linspace(min_x, max_x, len(gf_list)).tolist()
            for i, gf in enumerate(gf_list):
                emoji = ECHARTS_EMOJIS.get(gf, '🍃')
                pt_name = gf_display_pt.get(gf, gf)
                species_series.append({
                    'type': 'scatter',
                    'data': [[round(fixed_legend_x_vals[i], 4), 10.5]],
                    'symbol': 'circle',
                    'symbolSize': 14,
                    'itemStyle': {'color': 'transparent'},
                    'label': {
                        'show': True,
                        'position': 'top',
                        'formatter': f'{emoji} {pt_name}',
                        'fontSize': 12,
                        'fontFamily': 'Inter, sans-serif',
                        'color': '#333',
                    },
                    'silent': True,
                    'z': 100,
                    'tooltip': {'show': False},
                    'showInLegend': False,
                    'legendHoverLink': False,
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

            x_axis_min = round(min_x - (max_x - min_x) * 0.25, 4)
            x_axis_max = round(max_x + (max_x - min_x) * 0.05, 4)

            # X-axis formatter: convert sqrt-space value → real years
            js_x_formatter = "__JS__function(v){var r=v*v; return r<1 ? (Math.round(r*12)+'m') : (Math.round(r*10)/10+'a');}__JSEND__"

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
                'legend': {
                    'type': 'scroll',
                    'orient': 'vertical',
                    'right': 10,
                    'top': 60,
                    'bottom': 20,
                    'data': legend_names,
                    'textStyle': {'fontFamily': 'Inter, sans-serif', 'fontSize': 12},
                },
                'grid': {'left': 80, 'right': 200, 'top': 60, 'bottom': 80},
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
                    'name': 'Demanda de luz / Estrato',
                    'nameLocation': 'middle',
                    'nameGap': 50,
                    'nameTextStyle': {'color': '#555', 'fontSize': 14, 'fontFamily': 'Inter, sans-serif'},
                    'min': -2.5,
                    'max': 11,
                    'axisLabel': {
                        'formatter': js_y_formatter,
                        'fontFamily': 'Inter, sans-serif',
                        'fontSize': 12,
                        'color': '#171717',
                    },
                    'splitLine': {'lineStyle': {'color': '#e6e6e6'}},
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

        # Try to split into native/non-native using climate scores
        native_names = set()
        try:
            lat_lon_str = input.longitude_latitude()
            if lat_lon_str:
                lat, lon = parse_lat_lon(lat_lon_str)
                from database.connection import get_climate_match_scores
                sci_names = df['sci_name'].dropna().unique().tolist()
                scores = get_climate_match_scores(lat, lon, sci_names, threshold=0.3)
                # Build sci_name → common_en mapping
                for _, row in df.iterrows():
                    sn = row.get('sci_name')
                    cn = row.get('common_en')
                    if pd.notna(sn) and pd.notna(cn) and sn in scores:
                        native_names.add(cn)
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

        # Native candidates
        native_cands = [c for c in candidates if c[0] in native_names]
        other_cands = [c for c in candidates if c[0] not in native_names]

        if native_cands:
            sections.append(ui.h6("Nativas sugeridas", style="color:#2E7D32; margin-top:8px;"))
            sections.append(ui.div(
                *[make_add_btn(c[0]) for c in sorted(native_cands, key=lambda x: x[0])],
                style="display:flex; flex-wrap:wrap;",
            ))

        if other_cands:
            label = "Não-nativas adaptadas" if native_cands else "Espécies disponíveis"
            sections.append(ui.h6(label, style="color:#555; margin-top:8px;"))
            sections.append(ui.div(
                *[make_add_btn(c[0]) for c in sorted(other_cands, key=lambda x: x[0])],
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
                query=df.query("common_en == '%s'" % plant)[['common_en','yrs_ini_prod','longev_prod','stratum']].values.tolist()[0]
                if str(query[1])=='nan' or str(query[2])=='nan' or str(query[3])=='nan':
                    continue
                else:
                    for j in range(i+1,len(plants)):
                        other_plt=plants[j]
                        opposite=df.query("common_en == '%s'" % other_plt)[['common_en','yrs_ini_prod','longev_prod','stratum']].values.tolist()[0]
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
            query=df.query("common_en == '%s'" % plant)[['common_en','growth_form','yrs_ini_prod','longev_prod','stratum']].values.tolist()[0]
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

    def _get_plants_with_climate_score():
        """Return selectize choices ordered by climate match score when location is available."""
        df = pd.read_csv(FILE_NAME)

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

            # Build scored and unscored lists
            scored = []  # (common_en, score, growth_form)
            unscored = []  # (common_en, growth_form)
            seen = set()

            for sci_name, score in scores.items():
                common = sci_to_common.get(sci_name)
                if common and common not in seen:
                    gf = df.loc[df['common_en'] == common, 'growth_form'].values
                    gf = gf[0] if len(gf) > 0 and pd.notna(gf[0]) else ''
                    scored.append((common, score, gf))
                    seen.add(common)

            # Add species without climate data
            for _, row in df.iterrows():
                cn = row.get('common_en')
                if pd.notna(cn) and cn not in seen:
                    gf = row.get('growth_form', '')
                    gf = gf if pd.notna(gf) else ''
                    unscored.append((cn, gf))
                    seen.add(cn)

            # Sort scored by score desc, unscored alphabetically
            scored.sort(key=lambda x: (-x[1], x[0]))
            unscored.sort(key=lambda x: x[0])

            # Build grouped dict: scored species first, then unscored
            result = {}
            adapted_key = "ADAPTADAS AO CLIMA / CLIMATE ADAPTED"
            other_key = "OUTRAS ESPÉCIES / OTHER SPECIES"

            adapted = {}
            for common, score, gf in scored:
                pct = int(round(score * 100))
                adapted[common] = f"{common} ({pct}%)"  # key=value, val=display label

            others = {}
            for common, gf in unscored:
                others[common] = common  # key=value=label

            if adapted:
                result[adapted_key] = adapted
            if others:
                result[other_key] = others

            return result
        else:
            # No climate data — fall back to default grouping
            return get_Plants(FILE_NAME)

    # This function updates the choices on the sidebar of main species
    @reactive.effect
    @reactive.event(input.update_map)
    def update_main_species():
        choices = get_new_species()
        ui.update_selectize(
            "overview_plants",
            choices=choices,
            selected=[],
            server=True,
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
                query = df.query("common_en == '%s'" % plant)[
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