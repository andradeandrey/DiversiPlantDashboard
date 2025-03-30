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

    #This function creates the stratum graph
    # @render_widget
    # def intercrops():
    #     if input.database_choice() == "Practitioner's Database": #Ignore the creation of the graph if the we don't select the good data source
    #         data=tri()[0]
    #         max=0
    #         fig=go.Figure()
    #         repartition={0:[], 1:[], 2:[], 3:[], 4:[], 5:[], 6:[], 7:[], 8:[]}
    #         for plant in data:
    #             repartition[plant[4]].append(plant)
    #         for indice in range(9):
    #             n=len(repartition[indice])
    #             if n == 0:
    #                 pass
    #             elif n == 1:
    #                 info=repartition[indice][0]
    #                 fig.add_trace(go.Scatter(x=[info[2], info[2]+info[3]], y=[indice+0.5, indice+0.5], name=info[0],mode='lines',line=dict(color=COLOR[info[1]], width=5), showlegend=False))
    #                 fig.add_annotation(x=info[2],y=indice+0.5,text=info[0],font=dict(color="black"), align="center",ax=-10,ay=-15,bgcolor="white")
    #                 if info[2]+info[3]>max:
    #                     max=info[2]+info[3]
    #             else:
    #                 for i in range(n):
    #                     info=repartition[indice][i]
    #                     fig.add_trace(go.Scatter(x=[info[2], info[2]+info[3]], y=[indice+(0.1+0.8*i/(n-1)), indice+(0.1+0.8*i/(n-1))],name=info[0], mode='lines',line=dict(color=COLOR[info[1]], width=5), showlegend=False))
    #                     fig.add_annotation(x=info[2],y=indice+(0.1+0.8*i/(n-1)),text=info[0],font=dict(color="black"),align="center",ax=-10,ay=-15,bgcolor="white")
    #                     if info[2]+info[3]>max:
    #                         max=info[2]+info[3]
    #         for i in STRATUM[input.number_of_division()][0]:
    #             fig.add_trace(go.Scatter(x=[0, max], y=[i, i], mode='lines',line=dict(color='black', width=0.5),showlegend=False))
    #         custom_y_labels = STRATUM[input.number_of_division()][1]
    #         growth_forms=['bamboo', 'cactus', 'climber', 'herb', 'palm', 'shrub','subshrub','tree']
    #         colors = ['#53c5ff', '#49d1d5', "#dbb448", '#f8827a', '#ff8fda','#45d090',"#779137",'#d7a0ff']
    #         for growth, colr in zip(growth_forms, colors):
    #             fig.add_trace(go.Scatter(
    #                 x=[None],  
    #                 y=[None],
    #                 mode='markers',
    #                 marker=dict(size=10, color=colr),
    #                 showlegend=True,
    #                 name=growth,
    #             ))
    #         fig.update_yaxes(tickvals=list(custom_y_labels.keys()),ticktext=list(custom_y_labels.values()))
    #         fig.update_xaxes(title_text = 'Growth Period (year)') 
    #         fig.update_yaxes(title_text = 'Stratum')
    #         fig.update_layout(height=600)
    #         return figimport plotly.graph_objects as go


# ! WORKS
    # @render_widget
    # def intercrops():
    #     if input.database_choice() == "Practitioner's Database":  
    #         data = tri()[0]  # Fetch Data
    #         # ✅ Check if data is empty
    #         if not data:
    #             return go.Figure()  # Return empty figure if no data
    #         # 1️⃣ Determine dynamic range for bins based on data
    #         min_x = min([plant[2] for plant in data])  # Minimum Harvest Period
    #         max_x = max([plant[2] + plant[3] for plant in data])  # Maximum Harvest Period (Start + Duration)

    #         min_y = min([plant[4] for plant in data])  # Minimum Light Demand (Stratum)
    #         max_y = max([plant[4] for plant in data])  # Maximum Light Demand (Stratum)

    #         # 2️⃣ Define number of divisions (keeping bins structured)
    #         num_x_bins = 4  # Define number of x bins (adjustable)
    #         num_y_bins = 4  # Define number of y bins (adjustable)

    #         # 3️⃣ Create dynamically divided bins
    #         x_bins = np.linspace(min_x, max_x, num_x_bins).tolist()  # Create evenly spaced X bins
    #         y_bins = np.linspace(min_y, max_y, num_y_bins).tolist()  # Create evenly spaced Y bins

    #         # 4️⃣ Define Colors for Growth Forms
    #         growth_forms = ['bamboo', 'cactus', 'climber', 'herb', 'palm', 'shrub', 'subshrub', 'tree']
    #         colors = ['#53c5ff', '#49d1d5', "#dbb448", '#f8827a', '#ff8fda', '#45d090', "#779137", '#d7a0ff']
    #         color_map = dict(zip(growth_forms, colors))

    #         # 5️⃣ Initialize Figure
    #         fig = go.Figure()

    #         # 6️⃣ Add Background Grid (Rectangles)
    #         for i in range(len(x_bins) - 1):
    #             for j in range(len(y_bins) - 1):
    #                 fig.add_shape(
    #                     type="rect",
    #                     x0=x_bins[i], x1=x_bins[i+1],
    #                     y0=y_bins[j], y1=y_bins[j+1],
    #                     line=dict(color="black", width=1),
    #                     fillcolor="rgba(100,100,100,0.2)",  # Light grey for grid cells
    #                 )

    #         # 7️⃣ Place Plants Inside Fixed Boxes
    #         for plant in data:
    #             name, growth_type, x_start, duration, y_position = plant[0], plant[1], plant[2], plant[3], plant[4]

    #             # 8️⃣ Determine the correct bin for placement (ensuring species are included)
    #             x_bin = min([xb for xb in x_bins if xb >= x_start], default=x_bins[-1])
    #             y_bin = min([yb for yb in y_bins if yb >= y_position], default=y_bins[-1])

    #             # 9️⃣ Prevent IndexError when accessing next bin
    #             x_bin_index = x_bins.index(x_bin)
    #             y_bin_index = y_bins.index(y_bin)

    #             if x_bin_index < len(x_bins) - 1:
    #                 x_center = (x_bin + x_bins[x_bin_index + 1]) / 2
    #             else:
    #                 x_center = x_bin  # Stay within bounds

    #             if y_bin_index < len(y_bins) - 1:
    #                 y_center = (y_bin + y_bins[y_bin_index + 1]) / 2
    #             else:
    #                 y_center = y_bin  # Stay within bounds

    #             # 🔟 Plot Species in the Assigned Box
    #             fig.add_trace(go.Scatter(
    #                 x=[x_center],  # Safe X placement
    #                 y=[y_center],  # Safe Y placement
    #                 mode="markers",
    #                 marker=dict(size=15, color=color_map.get(growth_type, "grey")),
    #                 name=name,
    #                 showlegend=False
    #             ))

    #             # 🔟 Add Label Inside the Box
    #             fig.add_annotation(
    #                 x=x_center,
    #                 y=y_center,
    #                 text=name, 
    #                 font=dict(color="white"), 
    #                 showarrow=False,
    #                 bgcolor="black"
    #             )

    #         # 🔟 Add Legend for Growth Forms
    #         for growth, colr in color_map.items():
    #             fig.add_trace(go.Scatter(
    #                 x=[None],  
    #                 y=[None],
    #                 mode='markers',
    #                 marker=dict(size=10, color=colr),
    #                 showlegend=True,
    #                 name=growth
    #             ))

    #         # 🔟 Configure Axes Labels and Grid
    #         fig.update_xaxes(title_text="Harvest Period (Years After Planting)", zeroline=False, tickvals=x_bins)
    #         fig.update_yaxes(title_text="Light Demand (Stratum)", zeroline=False, tickvals=y_bins)

    #         # 🔟 Set Graph Layout
    #         fig.update_layout(
    #             height=600,
    #             plot_bgcolor="white",
    #             showlegend=True
    #         )

    #         return fig
# ! UPDATED below:  
    # @render_widget
    # def intercrops():
    #     if input.database_choice() == "Practitioner's Database":  
    #         data = tri()[0]  # Fetch Data
    #         print(data)
    #         if not data:
    #             return go.Figure()  # Return empty figure if no data

    #         # Determine dynamic range for bins
    #         min_x = min([plant[2] for plant in data])  
    #         max_x = max([plant[2] + plant[3] for plant in data])  

    #         min_y = min([plant[4] for plant in data])  
    #         max_y = max([plant[4] for plant in data])  

    #         num_x_bins = 4  
    #         num_y_bins = 4  

    #         x_bins = np.linspace(min_x, max_x, num_x_bins).tolist()  
    #         y_bins = np.linspace(min_y, max_y, num_y_bins).tolist()  

    #         # Growth Form Mappings
    #         growth_forms = ['bamboo', 'cactus', 'climber', 'herb', 'palm', 'shrub', 'subshrub', 'tree']
    #         colors = ['#53c5ff', '#49d1d5', "#dbb448", '#f8827a', '#ff8fda', '#45d090', "#779137", '#d7a0ff']
    #         symbols = ['star', 'diamond', 'cross', 'circle', 'triangle-up', 'square', 'hexagram', 'x']

    #         color_map = dict(zip(growth_forms, colors))
    #         symbol_map = dict(zip(growth_forms, symbols))

    #         fig = go.Figure()

    #         # Add Background Grid
    #         for i in range(len(x_bins) - 1):
    #             for j in range(len(y_bins) - 1):
    #                 fig.add_shape(
    #                     type="rect",
    #                     x0=x_bins[i], x1=x_bins[i+1],
    #                     y0=y_bins[j], y1=y_bins[j+1],
    #                     line=dict(color="black", width=1),
    #                     fillcolor="rgba(100,100,100,0.2)",
    #                 )

    #         # Place Plants Inside Bins
    #         for plant in data:
    #             name, growth_type, x_start, duration, y_position = plant[0], plant[1], plant[2], plant[3], plant[4]

    #             x_bin = min([xb for xb in x_bins if xb >= x_start], default=x_bins[-1])
    #             y_bin = min([yb for yb in y_bins if yb >= y_position], default=y_bins[-1])

    #             x_bin_index = x_bins.index(x_bin)
    #             y_bin_index = y_bins.index(y_bin)

    #             x_center = (x_bin + x_bins[x_bin_index + 1]) / 2 if x_bin_index < len(x_bins) - 1 else x_bin
    #             y_center = (y_bin + y_bins[y_bin_index + 1]) / 2 if y_bin_index < len(y_bins) - 1 else y_bin

    #             # Add Plant Symbols with Tooltip
    #             fig.add_trace(go.Scatter(
    #                 x=[x_center],  
    #                 y=[y_center],  
    #                 mode="markers",
    #                 marker=dict(
    #                     size=15, 
    #                     color=color_map.get(growth_type, "grey"), 
    #                     symbol=symbol_map.get(growth_type, "circle")
    #                 ),
    #                 name=growth_type,
    #                 hoverinfo="text",
    #                 text=f"<b>{name}</b><br>Growth Form: {growth_type}<br>Harvest Start: {x_start} yrs<br> Duration: {duration} yrs<br> Stratum: {y_position}"
    #             ))

    #         # Add Legend for Growth Forms
    #         for growth, colr in color_map.items():
    #             fig.add_trace(go.Scatter(
    #                 x=[None],  
    #                 y=[None],
    #                 mode='markers',
    #                 marker=dict(size=10, color=colr, symbol=symbol_map[growth]),
    #                 showlegend=True,
    #                 name=growth
    #             ))

    #         # Configure Axes
    #         fig.update_xaxes(title_text="Harvest Period (Years After Planting)", zeroline=False, tickvals=x_bins)
    #         fig.update_yaxes(title_text="Light Demand (Stratum)", zeroline=False, tickvals=y_bins)

    #         # Set Graph Layout
    #         fig.update_layout(
    #             height=600,
    #             plot_bgcolor="white",
    #             showlegend=True
    #         )

    #         return fig
# ! UPDATED ABOVE
    # @render_widget
    # def intercrops():
    #     if input.database_choice() == "Practitioner's Database":  
    #         data = tri()[0]  # Fetch Data
    #         print(data)
    #         if not data:
    #             return None  # Return empty figure if no data

    #         # Determine dynamic range for bins
    #         min_x = min([plant[2] for plant in data])  
    #         max_x = max([plant[2] + plant[3] for plant in data])  

    #         min_y = min([plant[4] for plant in data])  
    #         max_y = max([plant[4] for plant in data])  

    #         num_x_bins = 4  
    #         num_y_bins = 4  

    #         x_bins = np.linspace(min_x, max_x, num_x_bins).tolist()  
    #         y_bins = np.linspace(min_y, max_y, num_y_bins).tolist()  

    #         # Growth Form Mappings
    #         growth_forms = ['bamboo', 'cactus', 'climber', 'herb', 'palm', 'shrub', 'subshrub', 'tree']
    #         colors = ['#53c5ff', '#49d1d5', "#dbb448", '#f8827a', '#ff8fda', '#45d090', "#779137", '#d7a0ff']
    #         symbols = ['star', 'diamond', 'cross', 'circle', 'triangle-up', 'square', 'hexagram', 'x']

    #         color_map = dict(zip(growth_forms, colors))
    #         symbol_map = dict(zip(growth_forms, symbols))

    #         fig = go.Figure()

    #         # 🎯 ADD FIXED LEGEND (TOP - SEPARATE FROM PLOTLY'S LEGEND)
    #         fixed_legend_x = np.linspace(min_x, max_x, len(growth_forms))  # Spread symbols evenly
    #         fixed_legend_y = [max_y + (max_y * 0.1)] * len(growth_forms)  # Position above plot

    #         for i, growth in enumerate(growth_forms):
    #             fig.add_trace(go.Scatter(
    #                 x=[fixed_legend_x[i]],  
    #                 y=[fixed_legend_y[i]],  
    #                 mode="markers+text",
    #                 marker=dict(size=15, color=color_map[growth], symbol=symbol_map[growth]),
    #                 text=growth,  # Growth form name
    #                 textposition="top center",
    #                 showlegend=False  # Hide from plotly legend
    #             ))

    #         # Add Background Grid
    #         for i in range(len(x_bins) - 1):
    #             for j in range(len(y_bins) - 1):
    #                 fig.add_shape(
    #                     type="rect",
    #                     x0=x_bins[i], x1=x_bins[i+1],
    #                     y0=y_bins[j], y1=y_bins[j+1],
    #                     line=dict(color="black", width=1),
    #                     fillcolor="rgba(100,100,100,0.2)",
    #                 )

    #         # Place Plants Inside Bins (Dynamic Legend)
    #         for plant in data:
    #             name, growth_type, x_start, duration, y_position = plant[0], plant[1], plant[2], plant[3], plant[4]

    #             x_bin = min([xb for xb in x_bins if xb >= x_start], default=x_bins[-1])
    #             y_bin = min([yb for yb in y_bins if yb >= y_position], default=y_bins[-1])

    #             x_bin_index = x_bins.index(x_bin)
    #             y_bin_index = y_bins.index(y_bin)

    #             x_center = (x_bin + x_bins[x_bin_index + 1]) / 2 if x_bin_index < len(x_bins) - 1 else x_bin
    #             y_center = (y_bin + y_bins[y_bin_index + 1]) / 2 if y_bin_index < len(y_bins) - 1 else y_bin

    #             # Add Plant Symbols with Tooltip
    #             fig.add_trace(go.Scatter(
    #                 x=[x_center],  
    #                 y=[y_center],  
    #                 mode="markers",
    #                 marker=dict(
    #                     size=15, 
    #                     color=color_map.get(growth_type, "grey"), 
    #                     symbol=symbol_map.get(growth_type, "circle")
    #                 ),
    #                 name=name,  # Only plant name appears in dynamic legend
    #                 showlegend=True,
    #                 hoverinfo="text",
    #                 text=f"<b>{name}</b><br>Growth Form: {growth_type}<br>Harvest Start: {x_start} yrs<br> Duration: {duration} yrs<br> Stratum: {y_position}"
    #             ))

    #         # Configure Axes
    #         fig.update_xaxes(title_text="Harvest Period (Years After Planting)", zeroline=False, tickvals=x_bins)
    #         fig.update_yaxes(title_text="Light Demand (Stratum)", zeroline=False, tickvals=y_bins)

    #         # Set Graph Layout
    #         fig.update_layout(
    #             height=600,
    #             plot_bgcolor="white",
    #             showlegend=True,
    #             legend=dict(
    #                 orientation="v",  # Dynamic legend remains vertical (on right)
    #                 yanchor="top",
    #                 y=0.98,  
    #                 xanchor="left",
    #                 x=1.02,  # Moves the dynamic legend to the right
    #                 tracegroupgap=5
    #             )
    #         )

    #         return fig
    @render_widget
    def intercrops():
        if input.database_choice() == "Practitioner's Database":  
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
        if input.database_choice() == "Practitioner's Database": #Ignore the creation of the graph if the we don't select the good data source
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
        if input.database_choice() == "Practitioner's Database": #Ignore the creation of the graph if the we don't select the good data source
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
    @reactive.event(input.update_database)
    def get_new_species():
        if input.database_choice() == "GIFT Database":
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
    @reactive.event(input.update_database)
    def update_main_species():
        dict=get_new_species()
        ui.update_selectize(
            "overview_plants",
            choices=dict,
            selected=[],
            server=True,
        )

    #This function allows to download the species
    @output
    @render.download(filename=f"studied_data.csv")
    def export_df():
        if input.database_choice()=="Practitioner's Database":
            yield open_csv(FILE_NAME).to_csv()
        else:
            yield SPECIES_GIFT_DATAFRAME.to_csv()
    ## Export the data:
    @output
    @render.download(filename=lambda: f"{input.database_choice().replace(' ', '_').lower()}_data.csv")
    def export_df_os():
        if input.database_choice() == "Practitioner's Database":
            df = open_csv(FILE_NAME)
            plants = input.overview_plants()
            stratums = []
            
            for plant in plants:
                query = df.query("common_en == '%s'" % plant)[['common_en','yrs_ini_prod','longev_prod','stratum']].values.tolist()[0]
                if str(query[3]) != 'nan' and str(query[2]) != 'nan' and str(query[1]) != 'nan':
                    stratums.append(query[3])

            first_sgg = df[~df['stratum'].isin(stratums)]
            first_sgg = first_sgg[first_sgg['stratum'].notna()]
            first_sgg = first_sgg[['common_en','growth_form','plant_max_height','stratum','family','function','yrs_ini_prod','life_hist','longev_prod','threat_status']]
            
            total_sgg = first_sgg[~df['common_en'].isin(plants)]
            total_sgg = total_sgg.fillna("-")
            total_sgg = total_sgg.sort_values(by='common_en')
            
            yield total_sgg.to_csv(index=False)

        else:
            global SPECIES_GIFT_DATAFRAME
            if SPECIES_GIFT_DATAFRAME.empty:
                print("SPECIES_GIFT_DATAFRAME is not populated.")
                yield "Data not available."  # You can customize this message as needed
            else:
                SPECIES_GIFT_DATAFRAME = SPECIES_GIFT_DATAFRAME.fillna("-")
                SPECIES_GIFT_DATAFRAME = SPECIES_GIFT_DATAFRAME.sort_values("family")
                unecessary_columns = ['ref_ID', 'list_ID', 'entity_ID', 'work_ID', 'genus_ID', 'questionable', 'quest_native', 'endemic_ref', 'quest_end_ref', 'quest_end_list']
                SPECIES_GIFT_DATAFRAME = SPECIES_GIFT_DATAFRAME.drop(columns=unecessary_columns)
                
                yield SPECIES_GIFT_DATAFRAME.to_csv(index=False)

##Growth Form

    # # This functions creates the barchart and make it evolve depending on the lifetime chosen
    @render_widget
    # def plot_plants():
    #     if input.database_choice() == "Practitioner's Database":
    #         size=input.life_time()
    #         df=open_csv(FILE_NAME)
    #         plants=input.overview_plants()
    #         variables_x,variables_y,color,family,function,time_to_fh,life_hist,longev_prod,links,graph_y,color_change=[],[],[],[],[],[],[],[],[],[],[]
    #         if not plants:
    #             print("No plants selected. Returning an empty figure.")
    #             return None
    #         for plant in plants:
    #             query=df.query("common_en == '%s'" % plant)[['common_en','growth_form','plant_max_height','family','function','yrs_ini_prod','life_hist','longev_prod','threat_status','ref']].values.tolist()[0]
    #             variables_x.append(query[0]),color.append(query[1]),family.append(str(query[3])),function.append(str(query[4])),time_to_fh.append(str(query[5])),life_hist.append(str(query[6])),longev_prod.append(str(query[7])),links.append([query[8]])
    #             if str(query[2])=='nan':
    #                 variables_y.append(3)
    #             else:
    #                 variables_y.append(query[2])
    #             if str(query[7])=='nan' or query[7]==0:
    #                 expect=7
    #             else:
    #                 expect=query[7]
    #             if str(query[2])=='nan':
    #                 graph_y_max=3
    #             else:
    #                 graph_y_max=query[2]
    #             graph_y.append(min(graph_y_max,size*graph_y_max/expect))
    #             if size==0:
    #                 graph_y[-1]=0.1
    #             print(graph_y)
    #             if size>expect:
    #                 color_change.append(query[0])
                
    #         dataframe=pd.DataFrame({
    #                     'Plant Name': variables_x,
    #                     'Maximum height': variables_y,
    #                     'Growth form' : color,
    #                     'Family' : family,
    #                     'Function':function,
    #                     'Time before harvest':time_to_fh,
    #                     'Life history':life_hist,
    #                     'Longevity':longev_prod,
    #                     'Graph height':graph_y,
    #                 })
    #         dataframe['Graph color'] = dataframe['Growth form']
    #         dataframe.loc[dataframe['Plant Name'].isin(color_change), 'Graph color'] = 'Dead'
    #         fig = px.bar(dataframe, 
    #             x='Plant Name', 
    #             y='Graph height', 
    #             color='Graph color', 
    #             labels={'Plant Name':'Plant Name', 'Graph height':'Graph Height (m)'},
    #             category_orders={'Plant Name' : variables_x},
    #             hover_name="Plant Name",
    #             hover_data={'Maximum height':True, 'Family':True, 'Growth form':True, 'Function':True,'Time before harvest':True,'Life history':True,'Longevity':True,'Graph height':False})
            
    #         fig.update_layout(height=650)
            
    #         return fig
    def plot_plants():
        if input.database_choice() == "Practitioner's Database":
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

##Other Species

    #This function return the table of all the species that are not selected. For the Practitioner's Database, it makes suggestion, incompatible plants won't be shown, and for the GIFT one, it just shows the list
    @output
    @render.ui
    def suggestion_plants():
        if input.database_choice()=="Practitioner's Database":
            df=open_csv(FILE_NAME)
            plants=input.overview_plants()
            cards_suggestion=[]
            true_plants=[]
            stratums=[]
            
            for plant in plants:
                query=df.query("common_en == '%s'" % plant)[['common_en','yrs_ini_prod','longev_prod','stratum']].values.tolist()[0]
                
                if str(query[3])!='nan' and str(query[2])!='nan' and str(query[1])!='nan':
                    true_plants.append(query)
                    stratums.append(query[3])
                
            first_sgg = df[~df['stratum'].isin(stratums)]
            first_sgg = first_sgg[first_sgg['stratum'].notna()]
            first_sgg = first_sgg[['common_en','growth_form','plant_max_height','stratum','family','function','yrs_ini_prod','life_hist','longev_prod','threat_status']]
            
            total_sgg = first_sgg[~df['common_en'].isin(plants)]
            
            table = total_sgg.fillna("-")  # Nice looking na values
            table = table.sort_values(by='common_en')
            table=table.reset_index(drop=True)

            with pd.option_context("display.float_format", "{:,.2f}".format):
                return ui.HTML(DT(table))

        else:
            print(SPECIES_GIFT_DATAFRAME)
            
            table = SPECIES_GIFT_DATAFRAME.fillna("-")
            table = table.sort_values("family")
            unecessary_columns=['ref_ID','list_ID','entity_ID','work_ID','genus_ID','questionable','quest_native','endemic_ref','quest_end_ref','quest_end_list']
            table=table.drop(columns=unecessary_columns)
            table=table.reset_index(drop=True)

            with pd.option_context("display.float_format", "{:,.2f}".format):
                    return ui.HTML(DT(table))

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

    # @render.image
    # def homepage_image():
    #     img_path = "data/img/homepage.jpg"
    #     return {"src": img_path}