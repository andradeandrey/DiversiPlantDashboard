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

    #As long as we can't create a graph, nothing should appears except the wireframes


##Main Species

    @render_widget
    def intercrops():
        if input.database_choice() == "✔️ Practical management traits. ✔️ Fast.  ❌ Few common species. ❌ Ignores location.":  
            data = tri()[0]  # Fetch Data
            print(data)
            if not data:
                return None  # Return empty figure if no data

            # Determine dynamic range for bins
            min_x = round(min([plant[2] for plant in data]), 2)  
            max_x = round(max([plant[2] + plant[3] for plant in data]), 2)  

            min_y = round(min([plant[4] for plant in data]), 2)  
            max_y = round(max([plant[4] for plant in data]), 2)  

            num_x_bins = 4  
            num_y_bins = 4  

            # Create rounded bins
            x_bins = [round(x, 2) for x in np.linspace(min_x, max_x, num_x_bins).tolist()]
            y_bins = [round(y, 2) for y in np.linspace(min_y, max_y, num_y_bins).tolist()]

            # Growth Form Mappings
            growth_forms = ['bamboo', 'cactus', 'climber', 'herb', 'palm', 'shrub', 'subshrub', 'tree']
            colors = ['#53c5ff', '#49d1d5', "#dbb448", '#f8827a', '#ff8fda', '#45d090', "#779137", '#d7a0ff']
            symbols = ['star', 'diamond', 'cross', 'circle', 'triangle-up', 'square', 'hexagram', 'x']

            color_map = dict(zip(growth_forms, colors))
            symbol_map = dict(zip(growth_forms, symbols))

            fig = go.Figure()

            # 🎯 ADD FIXED LEGEND (TOP - SEPARATE FROM PLOTLY'S LEGEND)
            fixed_legend_x = np.linspace(min_x, max_x, len(growth_forms)).tolist()  # Spread symbols evenly
            fixed_legend_y = [round(max_y + (max_y * 0.1), 2)] * len(growth_forms)  # Position above plot

            for i, growth in enumerate(growth_forms):
                fig.add_trace(go.Scatter(
                    x=[round(fixed_legend_x[i], 2)],  
                    y=[fixed_legend_y[i]],  
                    mode="markers+text",
                    marker=dict(size=15, color=color_map[growth], symbol=symbol_map[growth]),
                    text=growth,  # Growth form name
                    textposition="top center",
                    showlegend=False  # Hide from plotly legend
                ))

            # Add Background Grid
            for i in range(len(x_bins) - 1):
                for j in range(len(y_bins) - 1):
                    fig.add_shape(
                        type="rect",
                        x0=x_bins[i], x1=x_bins[i+1],
                        y0=y_bins[j], y1=y_bins[j+1],
                        line=dict(color="black", width=1),
                        fillcolor="rgba(100,100,100,0.2)",
                    )

            # Place Plants Inside Bins (Dynamic Legend)
            for plant in data:
                name, growth_type, x_start, duration, y_position = plant[0], plant[1], plant[2], plant[3], plant[4]

                x_bin = min([xb for xb in x_bins if xb >= x_start], default=x_bins[-1])
                y_bin = min([yb for yb in y_bins if yb >= y_position], default=y_bins[-1])

                x_bin_index = x_bins.index(x_bin)
                y_bin_index = y_bins.index(y_bin)

                x_center = round((x_bin + x_bins[x_bin_index + 1]) / 2 if x_bin_index < len(x_bins) - 1 else x_bin, 2)
                y_center = round((y_bin + y_bins[y_bin_index + 1]) / 2 if y_bin_index < len(y_bins) - 1 else y_bin, 2)

                # Add Plant Symbols with Tooltip
                fig.add_trace(go.Scatter(
                    x=[x_center],  
                    y=[y_center],  
                    mode="markers",
                    marker=dict(
                        size=15, 
                        color=color_map.get(growth_type, "grey"), 
                        symbol=symbol_map.get(growth_type, "circle")
                    ),
                    name=name,  # Only plant name appears in dynamic legend
                    showlegend=True,
                    hoverinfo="text",
                    text=f"<b>{name}</b><br>Growth Form: {growth_type}<br>Harvest Start: {round(x_start, 2)} yrs<br> Duration: {round(duration, 2)} yrs<br> Stratum: {round(y_position, 2)}"
                ))

            # Configure Axes with Rounded Tick Values
            fig.update_xaxes(
                title_text="Harvest Period (Years After Planting)", 
                zeroline=False, 
                tickvals=x_bins,
                tickformat=".2f"  # Display ticks rounded to 2 decimal places
            )
            fig.update_yaxes(
                title_text="Light Demand (Stratum)", 
                zeroline=False, 
                tickvals=y_bins,
                tickformat=".2f"  # Display ticks rounded to 2 decimal places
            )

            # Set Graph Layout
            fig.update_layout(
                height=600,
                plot_bgcolor="white",
                showlegend=True,
                legend=dict(
                    orientation="v",  # Dynamic legend remains vertical (on right)
                    yanchor="top",
                    y=0.98,  
                    xanchor="left",
                    x=1.02,  # Moves the dynamic legend to the right
                    tracegroupgap=5
                )
            )

            return fig

    #This function creates the cards for the missing informations on growth and strata
    @output
    @render.ui
    def card_wrong_plant():
        if input.database_choice() == "✔️ Practical management traits. ✔️ Fast.  ❌ Few common species. ❌ Ignores location.": #Ignore the creation of the graph if the we don't select the good data source
            cards = []
            card_one,card_two=tri()[1],tri()[2]
            first_list,second_list=[],[]
            for name in card_one:
                first_list.append(ui.h6(f"{name}"))
            for name in card_two:
                second_list.append(ui.h6(f"{name}"))
            first_card = ui.card(
                ui.div(
                    ui.h5("Missing growth years informations :"),
                    *first_list
                )
            )
            cards.append(first_card)
            second_card = ui.card(
                ui.div(
                    ui.h5("Missing stratum informations :"),
                    *second_list
                )
            )
            cards.append(second_card)
            
            return ui.layout_columns(*cards,col_widths=[6,6])
    
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


    #This function is an auxiliary function used to separate a list of plants to make others function (card_wrong_plants and intercrops) run faster
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

    #This function run the R code to get the new species list if the GIFT database is chosen. Otherwise it returns the Practitioner's Database
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

    #This function updates the choices on the sidebar of main species
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

    # # This functions creates the barchart and make it evolve depending on the lifetime chosen
    def plot_plants():
        if input.database_choice() == "✔️ Practical management traits. ✔️ Fast.  ❌ Few common species. ❌ Ignores location.":
            size = input.life_time()
            df = open_csv(FILE_NAME)
            plants = input.overview_plants()

            # Growth form -> color mapping:
            growth_forms = ['bamboo', 'cactus', 'climber', 'herb', 'palm', 'shrub', 'subshrub', 'tree']
            colors = ['#53c5ff', '#49d1d5', '#dbb448', '#f8827a', '#ff8fda', '#45d090', '#779137', '#d7a0ff']
            
            # Create a dictionary from growth form to color:
            color_discrete_map = dict(zip(growth_forms, colors))
            # Add the "Dead" color mapping:
            color_discrete_map['Dead'] = 'black'
            
            if not plants:
                print("No plants selected. Returning an empty figure.")
                return None

            # Prepare data containers
            variables_x, variables_y = [], []
            color, family, function = [], [], []
            time_to_fh, life_hist, longev_prod = [], [], []
            links, graph_y, color_change = [], [], []

            for plant in plants:
                query = df.query("common_en == '%s'" % plant)[
                    [
                        'common_en',     # 0
                        'growth_form',   # 1
                        'plant_max_height',
                        'family',
                        'function',
                        'yrs_ini_prod',
                        'life_hist',
                        'longev_prod',
                        'threat_status', # 8
                        'ref'           # 9
                    ]
                ].values.tolist()[0]

                variables_x.append(query[0])  # Plant name
                color.append(str(query[1]))   # Growth form
                family.append(str(query[3]))
                function.append(str(query[4]))
                time_to_fh.append(str(query[5]))
                life_hist.append(str(query[6]))
                longev_prod.append(str(query[7]))
                links.append([query[8]])

                # Handle missing max height
                if pd.isna(query[2]):
                    variables_y.append(3)
                else:
                    variables_y.append(query[2])

                # Calculate expected longevity
                if pd.isna(query[7]) or query[7] == 0:
                    expect = 7
                else:
                    expect = query[7]

                # graph_y_max is the "full" height
                if pd.isna(query[2]):
                    graph_y_max = 3
                else:
                    graph_y_max = query[2]

                # Scale the bar height by size relative to expect
                graph_y_value = min(graph_y_max, size * graph_y_max / expect)
                if size == 0:
                    graph_y_value = 0.1
                graph_y.append(graph_y_value)

                # Check if size > expect => "Dead"
                if size > expect:
                    color_change.append(query[0])

            # Build final dataframe
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

            # Default color is 'Growth form', but mark dead plants
            dataframe['Graph color'] = dataframe['Growth form']
            dataframe.loc[dataframe['Plant Name'].isin(color_change), 'Graph color'] = 'Dead'

            # Create the bar chart
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

            fig.update_layout(height=650)
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(showgrid=False)
            fig.update_layout(plot_bgcolor='lightgrey')
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