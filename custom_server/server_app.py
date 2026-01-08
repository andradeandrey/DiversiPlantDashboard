import os
import numpy as np
import pandas as pd
from pathlib import Path
import plotly.express as px
from shinywidgets import render_widget
from shiny import render, ui, reactive
import plotly.graph_objects as go
from itables.shiny import DT
from custom_server.agroforestry_server import open_csv, get_Plants
import geopandas as gpd
import folium
from folium import plugins
from rpy2.robjects.conversion import localconverter
from rpy2 import robjects
from rpy2.robjects.packages import importr
from rpy2.robjects.vectors import StrVector
import rpy2.robjects.packages as rpackages, data
from rpy2.robjects import r, pandas2ri 
from collections import Counter


FILE_NAME = os.path.join(Path(__file__).parent.parent,"data","MgmtTraitData_updated.csv")
# FILE_NAME = os.path.join(Path(__file__).parent.parent,"data","practitioners.csv")


COLOR = {'herb' : '#f8827a','climber':"#dbb448",'subshrub' : "#779137",'shrub' :'#45d090','cactus' : '#49d1d5','bamboo' : '#53c5ff','tree' : '#d7a0ff','palm' : '#ff8fda'}

STRATUM = [0,1,[[0,4,9],{2:"Shade tolerant", 6.5:"Light demanding"}],
            [[0,3,6,9],{1.5:"Shade tolerant", 4.5:"Medium", 7.5:"Light demanding"}],
            [[0,3,5,7,9],{1.5:"Low", 4:"Medium", 6:"High", 8:"Emergent"}],
            [[0,2,4,6,7,9],{1:"Ground", 3:"Low", 5:"Medium", 6.5:"High", 8:"Emergent"}],
            [[0,2,4,6,7,8,9],{1:"Ground", 3:"Low", 5:"Medium", 6.5:"High",7.5:"High-Emergent", 8.5:"Emergent"}],
            [[0,2,4,5,6,7,8,9],{1:"Ground", 3:"Low", 4.5:"Medium", 5.5:"Medium-High", 6.5:"High", 7.5:"High-Emergent", 8.5:"Emergent"}],
            [[0,2,3,4,5,6,7,8,9],{1:"Ground", 2.5:"Low", 3.5:"Low-Medium", 4.5:"Medium", 5.5:"Medium-High", 6.5:"High", 7.5:"High-Emergent", 8.5:"Emergent"}],
            [[0,1,2,3,4,5,6,7,8,9],{0.5: "Ground",1.5: "Ground-Low",2.5: "Low",3.5: "Low-Medium",4.5: "Medium",5.5: "Medium-High",6.5: "High",7.5: "High-Emergent",8.5: "Emergent"}]]

FLORISTIC_GROUP = {"Native": 'native', "Endemic":'endemic_list', "Naturalized":'naturalized',  "All Species":'all'}

SPECIES_GIFT_DATAFRAME = pd.DataFrame()

growth_forms = ['bamboo', 'cactus', 'climber', 'herb', 'palm', 'shrub', 'subshrub', 'tree']
colors = ['#53c5ff', '#49d1d5', '#dbb448', '#f8827a', '#ff8fda', '#45d090', '#779137', '#d7a0ff']
color_mapping = dict(zip(growth_forms, colors))


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

        # Return the Folium map as raw HTML
        return ui.HTML(world_map._repr_html_())


##Climate

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

    @render_widget
    @reactive.event(input.overview_plants, input.stratum_bins, input.harvest_bins)
    def intercrops():
        if input.database_choice() == "✔️ Practical management traits. ✔️ Fast.  ❌ Few common species. ❌ Ignores location.":  
            df = open_csv(FILE_NAME)
            plants = input.overview_plants()
            
            if not plants:
                return go.Figure().update_layout(
                    title="No species selected",
                    height=600
                )
            
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
                name, growth_type, x_start, duration, y_position = query
                
                has_harvest = str(x_start) != 'nan'
                has_stratum = str(y_position) != 'nan'
                
                # Use default duration if missing
                if str(duration) == 'nan':
                    duration = 5.0
                
                if has_harvest and has_stratum:
                    complete_data.append([name, growth_type, x_start, duration, y_position])
                elif has_harvest and not has_stratum:
                    missing_stratum.append([name, growth_type, x_start, duration, None])
                elif not has_harvest and has_stratum:
                    missing_harvest.append([name, growth_type, None, None, y_position])
                else:
                    missing_both.append([name, growth_type, None, None, None])
            
            # Get stratum resolution from slider
            num_y_bins = int(input.stratum_bins())
            stratum_config = STRATUM[num_y_bins]
            y_bins = stratum_config[0]
            y_labels = stratum_config[1]
            
            # Determine X range from complete data and missing_stratum
            all_x_values = []
            if complete_data:
                for plant in complete_data:
                    all_x_values.append(plant[2])
                    all_x_values.append(plant[2] + plant[3])
            if missing_stratum:
                for plant in missing_stratum:
                    all_x_values.append(plant[2])
                    all_x_values.append(plant[2] + plant[3])
            
            if all_x_values:
                min_x = round(min(all_x_values), 2)
                max_x = round(max(all_x_values), 2)
            else:
                min_x, max_x = 0, 10
            
            if max_x - min_x < 1:
                max_x = min_x + 10
            
            num_x_bins = int(input.harvest_bins()) 
            x_bins = [round(x, 2) for x in np.linspace(min_x, max_x, num_x_bins + 1).tolist()]
            
            # Calculate bin dimensions for offset calculations
            x_bin_width = (max_x - min_x) / num_x_bins
            y_bin_height = 9 / len(y_bins)
            
            # Growth Form Mappings
            growth_forms = ['bamboo', 'cactus', 'climber', 'herb', 'palm', 'shrub', 'subshrub', 'tree']
            colors = ['#53c5ff', '#49d1d5', "#dbb448", '#f8827a', '#ff8fda', '#45d090', "#779137", '#d7a0ff']
            symbols = ['star', 'diamond', 'cross', 'circle', 'triangle-up', 'square', 'hexagram', 'x']
            
            color_map = dict(zip(growth_forms, colors))
            symbol_map = dict(zip(growth_forms, symbols))
            
            fig = go.Figure()
            
            # === FIXED LEGEND AT TOP ===
            fixed_legend_x = np.linspace(min_x, max_x, len(growth_forms)).tolist()
            fixed_legend_y = [10.5] * len(growth_forms)
            
            for i, growth in enumerate(growth_forms):
                fig.add_trace(go.Scatter(
                    x=[round(fixed_legend_x[i], 2)],
                    y=[fixed_legend_y[i]],
                    mode="markers+text",
                    marker=dict(size=15, color=color_map[growth], symbol=symbol_map[growth]),
                    text=growth,
                    textposition="top center",
                    showlegend=False,
                    hoverinfo='skip'
                ))
            
            # === MAIN GRID BACKGROUND ===
            for i in range(len(x_bins) - 1):
                for j in range(len(y_bins) - 1):
                    fig.add_shape(
                        type="rect",
                        x0=x_bins[i], x1=x_bins[i+1],
                        y0=y_bins[j], y1=y_bins[j+1],
                        line=dict(color="black", width=1),
                        fillcolor="rgba(150,150,150,0.2)",
                    )
            
            # === LEFT MARGIN BACKGROUND (for species with unknown harvest) ===
            fig.add_shape(
                type="rect",
                x0=min_x - (max_x - min_x) * 0.2,
                x1=min_x,
                y0=0,
                y1=9,
                fillcolor="rgba(255,200,150,0.15)",
                line=dict(color="orange", width=2, dash="dash"),
                layer="below"
            )
            
            # === BOTTOM MARGIN BACKGROUND (for species with unknown stratum) ===
            fig.add_shape(
                type="rect",
                x0=min_x,
                x1=max_x,
                y0=-2,
                y1=0,
                fillcolor="rgba(255,150,150,0.15)",
                line=dict(color="red", width=2, dash="dash"),
                layer="below"
            )
            
            added_species = set()

            def get_offset_position(count):
                """
                Returns offset (dx, dy) for the nth item in a horizontal line pattern.
                Since bins are wider than tall, we spread species horizontally.
                """
                
                if count == 0:
                    return (0, 0)  # First species at center
                
                # Arrange in a horizontal line, alternating left and right
                # Pattern: center, right, left, right, left, right, left...
                if count % 2 == 1:  # Odd positions go right
                    position = (count + 1) // 2
                    return (0.2 * position, 0)
                else:  # Even positions go left
                    position = count // 2
                    return (-0.2 * position, 0)
            # === 1. PLACE SPECIES WITH COMPLETE DATA (in main grid) ===
            # Track how many species in each bin
            bin_counters = {}
            
            for plant in complete_data:
                name, growth_type, x_start, duration, y_position = plant
                
                if name in added_species:
                    continue
                
                # Find X bin
                x_bin_index = 0
                for i in range(len(x_bins) - 1):
                    if x_start >= x_bins[i] and x_start < x_bins[i+1]:
                        x_bin_index = i
                        break
                if x_start >= x_bins[-1]:
                    x_bin_index = len(x_bins) - 2
                
                # Find Y bin
                y_bin_index = 0
                for i in range(len(y_bins) - 1):
                    if y_position >= y_bins[i] and y_position < y_bins[i+1]:
                        y_bin_index = i
                        break
                if y_position >= y_bins[-1]:
                    y_bin_index = len(y_bins) - 2
                
                # Track which species is in which bin
                bin_key = (x_bin_index, y_bin_index)
                if bin_key not in bin_counters:
                    bin_counters[bin_key] = 0
                else:
                    bin_counters[bin_key] += 1
                
                # Get offset for this species
                offset_x, offset_y = get_offset_position(bin_counters[bin_key])
                
                # Calculate center with offset
                x_center = round((x_bins[x_bin_index] + x_bins[x_bin_index + 1]) / 2, 2)
                y_center = round((y_bins[y_bin_index] + y_bins[y_bin_index + 1]) / 2, 2)
                
                # Apply offset (scaled by bin size)
                x_final = x_center + offset_x * x_bin_width * 0.3
                y_final = y_center + offset_y * y_bin_height * 0.3
                
                fig.add_trace(go.Scatter(
                    x=[x_final],
                    y=[y_final],
                    mode="markers",
                    marker=dict(
                        size=15,
                        color=color_map.get(growth_type, "grey"),
                        symbol=symbol_map.get(growth_type, "circle")
                    ),
                    name=name,
                    showlegend=True,
                    legendgroup=name,
                    hoverinfo="text",
                    text=f"<b>{name}</b><br>Growth Form: {growth_type}<br>Harvest Start: {round(x_start, 2)} yrs<br>Duration: {round(duration, 2)} yrs<br>Stratum: {round(y_position, 2)}"
                ))
                added_species.add(name)
            
            # === 2. PLACE SPECIES WITH MISSING HARVEST (left side - at their ACTUAL stratum level) ===
            if missing_harvest:
                # Add label at top of left margin
                fig.add_annotation(
                    x=min_x - (max_x - min_x) * 0.1,
                    y=9.5,
                    text="⚠️ Unknown harvest period",
                    showarrow=False,
                    font=dict(size=11, color="darkorange"),
                    bgcolor="rgba(255,255,255,0.8)",
                    bordercolor="orange",
                    borderwidth=1
                )
                
                # Track species at each stratum level for offsetting
                stratum_counters = {}
                
                for plant in missing_harvest:
                    name, growth_type, _, _, y_position = plant
                    
                    if name in added_species:
                        continue
                    
                    # Round stratum to bin it
                    y_rounded = round(y_position, 1)
                    if y_rounded not in stratum_counters:
                        stratum_counters[y_rounded] = 0
                    else:
                        stratum_counters[y_rounded] += 1
                    
                    # Calculate offset
                    y_offset = (stratum_counters[y_rounded] % 3 - 1) * 0.3  # -0.3, 0, 0.3
                    x_offset = (stratum_counters[y_rounded] // 3) * 0.02 * (max_x - min_x)
                    
                    fig.add_trace(go.Scatter(
                        x=[min_x - (max_x - min_x) * 0.1 - x_offset],
                        y=[y_position + y_offset],
                        mode="markers",
                        marker=dict(
                            size=15,
                            color=color_map.get(growth_type, "grey"),
                            symbol=symbol_map.get(growth_type, "circle"),
                            line=dict(width=2, color="orange")
                        ),
                        name=name,
                        showlegend=True,
                        legendgroup=name,
                        hoverinfo="text",
                        text=f"<b>{name}</b><br>Growth Form: {growth_type}<br>⚠️ Harvest period: Unknown<br>Stratum: {round(y_position, 2)}"
                    ))
                    added_species.add(name)
            
            # === 3. PLACE SPECIES WITH MISSING STRATUM (bottom - at their ACTUAL harvest time) ===
            if missing_stratum:
                # Add label at left of bottom margin
                fig.add_annotation(
                    x=min_x,
                    y=-0.5,
                    text="⚠️ Unknown stratum",
                    showarrow=False,
                    xanchor="left",
                    font=dict(size=11, color="darkred"),
                    bgcolor="rgba(255,255,255,0.8)",
                    bordercolor="red",
                    borderwidth=1
                )
                
                # Track species at each x position for offsetting
                x_position_counters = {}
                
                for plant in missing_stratum:
                    name, growth_type, x_start, duration, _ = plant
                    
                    if name in added_species:
                        continue
                    
                    # Find X bin
                    x_bin_index = 0
                    for i in range(len(x_bins) - 1):
                        if x_start >= x_bins[i] and x_start < x_bins[i+1]:
                            x_bin_index = i
                            break
                    if x_start >= x_bins[-1]:
                        x_bin_index = len(x_bins) - 2
                    
                    # Track by bin
                    if x_bin_index not in x_position_counters:
                        x_position_counters[x_bin_index] = 0
                    else:
                        x_position_counters[x_bin_index] += 1
                    
                    x_center = round((x_bins[x_bin_index] + x_bins[x_bin_index + 1]) / 2, 2)
                    
                    # Calculate offset
                    x_offset = (x_position_counters[x_bin_index] % 3 - 1) * 0.15 * x_bin_width
                    y_offset = -(x_position_counters[x_bin_index] // 3) * 0.3
                    
                    fig.add_trace(go.Scatter(
                        x=[x_center + x_offset],
                        y=[-1 + y_offset],
                        mode="markers",
                        marker=dict(
                            size=15,
                            color=color_map.get(growth_type, "grey"),
                            symbol=symbol_map.get(growth_type, "circle"),
                            line=dict(width=2, color="red")
                        ),
                        name=name,
                        showlegend=True,
                        legendgroup=name,
                        hoverinfo="text",
                        text=f"<b>{name}</b><br>Growth Form: {growth_type}<br>Harvest Start: {round(x_start, 2)} yrs<br>Duration: {round(duration, 2)} yrs<br>⚠️ Stratum: Unknown"
                    ))
                    added_species.add(name)
            
            # === 4. PLACE SPECIES WITH MISSING BOTH (bottom-left corner) ===
            if missing_both:
                # Add label
                fig.add_annotation(
                    x=min_x - (max_x - min_x) * 0.15,
                    y=-1.5,
                    text="⚠️ Missing<br>both values",
                    showarrow=False,
                    font=dict(size=9, color="darkred"),
                    bgcolor="rgba(255,255,255,0.8)",
                    bordercolor="darkred",
                    borderwidth=1
                )
                
                # Arrange in a grid pattern
                cols = 2
                for idx, plant in enumerate(missing_both):
                    name, growth_type = plant[0], plant[1]
                    
                    if name in added_species:
                        continue
                    
                    row = idx // cols
                    col = idx % cols
                    
                    x_pos = min_x - (max_x - min_x) * 0.15 + col * 0.03 * (max_x - min_x)
                    y_pos = -1 - row * 0.4
                    
                    fig.add_trace(go.Scatter(
                        x=[x_pos],
                        y=[y_pos],
                        mode="markers",
                        marker=dict(
                            size=15,
                            color=color_map.get(growth_type, "grey"),
                            symbol=symbol_map.get(growth_type, "circle"),
                            line=dict(width=2, color="darkred")
                        ),
                        name=name,
                        showlegend=True,
                        legendgroup=name,
                        hoverinfo="text",
                        text=f"<b>{name}</b><br>Growth Form: {growth_type}<br>⚠️ Harvest period: Unknown<br>⚠️ Stratum: Unknown"
                    ))
                    added_species.add(name)
                    
            # === CONFIGURE AXES ===
            fig.update_xaxes(
                title_text="Harvest Period (Years After Planting)",
                zeroline=False,
                tickvals=x_bins,
                tickformat=".2f",
                range=[min_x - (max_x - min_x) * 0.25, max_x + (max_x - min_x) * 0.05]
            )

            # === CONFIGURE Y-AXIS WITH STRATUM TEXT LABELS ===
            # Extract tick positions and labels from STRATUM configuration
            # y_labels is a dict like {1.5: "Low", 4: "Medium", 6: "High", 8: "Emergent"}
            sorted_label_items = sorted(y_labels.items(), key=lambda x: x[0])  # Sort by position
            y_tick_positions = [pos for pos, label in sorted_label_items]
            y_tick_text = [label for pos, label in sorted_label_items]

            fig.update_yaxes(
                title_text="Light Demand (Stratum)",
                zeroline=False,
                range=[-2.5, 11],  # Always show full range 0-9 plus margins
                tickmode='array',  # Use custom tick positions
                tickvals=y_tick_positions,  # Numeric positions
                ticktext=y_tick_text,  # Text labels
                showgrid=True,
                gridcolor='lightgray'
            )
            
            # === LAYOUT ===
            complete_count = len(complete_data)
            missing_h_count = len(missing_harvest)
            missing_s_count = len(missing_stratum)
            missing_b_count = len(missing_both)

            title_parts = [f"Showing all {len(added_species)} selected species"]
            if complete_count:
                title_parts.append(f"{complete_count} complete")
            if missing_h_count:
                title_parts.append(f"{missing_h_count} missing harvest")
            if missing_s_count:
                title_parts.append(f"{missing_s_count} missing stratum")
            if missing_b_count:
                title_parts.append(f"{missing_b_count} missing both")

            fig.update_layout(
                height=700,
                plot_bgcolor="white",
                showlegend=True,
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=0.98,
                    xanchor="left",
                    x=1.02,
                    tracegroupgap=5,
                    title=dict(
                        text="<b>Plants selected</b>",  # Add title to right legend
                        font=dict(size=14)
                    )
                ),
                title=" | ".join(title_parts)
            )

            # === ADD "GROWTH FORMS" LABEL ABOVE TOP LEGEND ===
            fig.add_annotation(
                x=sum(fixed_legend_x) / len(fixed_legend_x),  # Center of the growth form symbols
                y=11.2,  # Above the growth form symbols
                text="<b>Growth forms</b>",
                showarrow=False,
                font=dict(size=14, color="black"),
                xanchor="center",
                yanchor="bottom"
            )
            return fig
        
    #This function creates a card showing what species are incompatible with each other
    @output
    @render.ui
    def compatibility():
        if input.database_choice() == "✔️ Practical management traits. ✔️ Fast.  ❌ Few common species. ❌ Ignores location.": #Ignore the creation of the graph if the we don't select the good data source
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
        if input.database_choice() == "✔️ Most known species. ✔️ Botanical details. ✔️ Filtered for your location. ❌ Slow.":
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
            families = new_species['family'].unique()
            families_clean = sorted(families.tolist())
            dict = {}
            for family in families_clean:
                print(dict)
                dict[family] = {}
                plants = new_species.query("family == '%s'" % family)['work_species'].tolist()
                plants.sort()
                for plant in plants:
                    dict[family][plant] = plant
            return dict
        else:
            return get_Plants(FILE_NAME)

    # This function updates the choices on the sidebar of main species
    @reactive.effect
    @reactive.event(input.update_map)
    def update_main_species():
        dict=get_new_species()
        ui.update_selectize(
            "overview_plants",
            choices=dict,
            selected=[],
            server=True,
        )

    # #This function allows to download the species
    # Replace both download functions with these modified versions
    # * for now we are removing this button.
    @output
    @render.download(filename=f"selected_species_data.csv")
    def export_df():
        if input.database_choice() == "✔️ Practical management traits. ✔️ Fast.  ❌ Few common species. ❌ Ignores location.":
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
        if input.database_choice() == "✔️ Practical management traits. ✔️ Fast.  ❌ Few common species. ❌ Ignores location.":
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

    @render_widget
    @reactive.event(input.life_time, input.overview_plants)
    def plot_plants():
        if input.database_choice() == "✔️ Practical management traits. ✔️ Fast.  ❌ Few common species. ❌ Ignores location.":
            size = input.life_time()
            df = open_csv(FILE_NAME)
            plants = input.overview_plants()

            # Growth form -> color mapping
            color_discrete_map = color_mapping.copy()
            color_discrete_map['removed'] = 'black'
            
            if not plants:
                return go.Figure().update_layout(
                    title="No plants selected",
                    height=650
                )

            # Prepare data containers
            variables_x, variables_y = [], []
            color, family, function = [], [], []
            time_to_fh, life_hist, longev_prod = [], [], []
            graph_y, color_change = [], []

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

                variables_x.append(query[0])
                color.append(str(query[1]))
                family.append(str(query[3]))
                function.append(str(query[4]))
                time_to_fh.append(str(query[5]))
                life_hist.append(str(query[6]))
                longev_prod.append(str(query[7]))

                # Handle missing max height
                max_height = 3 if pd.isna(query[2]) else query[2]
                variables_y.append(max_height)

                # Calculate expected longevity
                expect = 7 if pd.isna(query[7]) or query[7] == 0 else query[7]

                # Scale bar height by lifetime
                if size == 0:
                    graph_y_value = 0.1
                else:
                    graph_y_value = min(max_height, size * max_height / expect)
                graph_y.append(graph_y_value)

                # Mark dead plants
                if size > expect:
                    color_change.append(query[0])

            # Build dataframe
            dataframe = pd.DataFrame({
                'Plant Name': variables_x,
                'Maximum height': variables_y,
                'Growth form': color,
                'Family': family,
                'Function': function,
                'Time before harvest': time_to_fh,
                'Life history': life_hist,
                'Longevity': longev_prod,
                'Graph height': graph_y
            })

            # Set color (mark dead plants)
            dataframe['Graph color'] = dataframe['Growth form']
            dataframe.loc[dataframe['Plant Name'].isin(color_change), 'Graph color'] = 'removed'

            # Create bar chart
            fig = px.bar(
                dataframe,
                x='Plant Name',
                y='Graph height',
                color='Graph color',
                labels={
                    'Plant Name': 'Plant Name',
                    'Graph height': 'Height (m)'
                },
                category_orders={'Plant Name': variables_x},
                hover_name="Plant Name",
                hover_data={
                    'Maximum height': True,
                    'Family': True,
                    'Growth form': True,
                    'Function': True,
                    'Time before harvest': True,
                    'Life history': True,
                    'Longevity': True,
                    'Graph height': False
                },
                color_discrete_map=color_discrete_map
            )

            fig.update_layout(
                height=650,
                plot_bgcolor='lightgrey',
                title=f"Species Growth at Year {size}"
            )
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(showgrid=False, title_text="Height (m)")
            
            return fig
        
## * Results
    # Define available columns based on database choice
    def get_available_columns():
        if input.database_choice() == "✔️ Practical management traits. ✔️ Fast.  ❌ Few common species. ❌ Ignores location.":
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
        
        # Get readable column names for display
        readable_cols = {col: col.replace('_', ' ').title() for col in available_cols}
        
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
    @reactive.event(input.update_map, input.selected_columns)
    def suggestion_plants():
        if input.database_choice() == "✔️ Practical management traits. ✔️ Fast.  ❌ Few common species. ❌ Ignores location.":
            df = open_csv(FILE_NAME)
            plants = input.overview_plants()
            
            # Filter the dataframe to only include the selected plants
            selected_plants_df = df[df['common_en'].isin(plants)]
            
            # Get selected columns (convert from readable back to actual column names if needed)
            columns = input.selected_columns()
            
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
            
            # Display the table with DataTable
            with pd.option_context("display.float_format", "{:,.2f}".format):
                return ui.HTML(DT(table))
        
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
            columns = input.selected_columns()
            
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
            
            with pd.option_context("display.float_format", "{:,.2f}".format):
                return ui.HTML(DT(table))

    # Also update the export function to use selected columns
    @output
    @render.download(filename=lambda: f"selected_{input.database_choice().replace(' ', '_').lower()}_data.csv")
    def export_df_os():
        if input.database_choice() == "✔️ Practical management traits. ✔️ Fast.  ❌ Few common species. ❌ Ignores location.":
            df = open_csv(FILE_NAME)
            plants = input.overview_plants()
            
            # Filter to only include selected plants
            selected_df = df[df['common_en'].isin(plants)]
            
            # Get selected columns
            columns = input.selected_columns()
            
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
                    
                    # Get selected columns
                    columns = input.selected_columns()
                    
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