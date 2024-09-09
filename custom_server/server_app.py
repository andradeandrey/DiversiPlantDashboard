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

from rpy2.robjects.conversion import localconverter
from rpy2 import robjects
from rpy2.robjects.packages import importr
from rpy2.robjects.vectors import StrVector
import rpy2.robjects.packages as rpackages, data
from rpy2.robjects import r, pandas2ri 

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

def server_app(input,output,session):

##Location

    #This function creates the world map and update it if you click on "Update map"
    @render_widget
    @reactive.event(input.update_map,ignore_none=None)
    def world_map():

        world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        

        world['color'] = 'grey'


        fig = px.choropleth(world, 
                            locations='iso_a3',  
                            color='color', 
                            hover_name='name', 
                            hover_data={'continent': True, 'color': False, 'iso_a3': False}, 
                            projection='natural earth',
                            color_discrete_sequence=['grey']) 

        fig.update_geos(showcountries=True, showcoastlines=True, showland=True, fitbounds="locations")


        #If the user inputs longitude AND latitude, add a red point on the location
        if input.longitude()!='' and input.latitude()!='':

            fig.add_scattergeo(lat=[input.latitude()], lon=[input.longitude()], mode='markers',
                   marker=dict(color='red', size=10))
            
        fig.update_layout(showlegend=False)

        fig.update_layout(
                height=600
            )
        
        return fig


##Climate

    #As long as we can't create a graph, nothing should appears except the wireframes


##Main Species

    #This function creates the stratum graph
    @render_widget
    def intercrops():
        if input.database_choice() == "Normal Database": #Ignore the creation of the graph if the we don't select the good data source
            data=tri()[0]
            max=0
            fig=go.Figure()
            repartition={0:[], 1:[], 2:[], 3:[], 4:[], 5:[], 6:[], 7:[], 8:[]}
            for plant in data:
                repartition[plant[4]].append(plant)
            for indice in range(9):
                n=len(repartition[indice])
                if n == 0:
                    pass
                elif n == 1:
                    info=repartition[indice][0]
                    fig.add_trace(go.Scatter(x=[info[2], info[2]+info[3]], y=[indice+0.5, indice+0.5], name=info[0],mode='lines',line=dict(color=COLOR[info[1]], width=5), showlegend=False))
                    fig.add_annotation(x=info[2],y=indice+0.5,text=info[0],font=dict(color="black"), align="center",ax=-10,ay=-15,bgcolor="white")
                    if info[2]+info[3]>max:
                        max=info[2]+info[3]
                else:
                    for i in range(n):
                        info=repartition[indice][i]
                        fig.add_trace(go.Scatter(x=[info[2], info[2]+info[3]], y=[indice+(0.1+0.8*i/(n-1)), indice+(0.1+0.8*i/(n-1))],name=info[0], mode='lines',line=dict(color=COLOR[info[1]], width=5), showlegend=False))
                        fig.add_annotation(x=info[2],y=indice+(0.1+0.8*i/(n-1)),text=info[0],font=dict(color="black"),align="center",ax=-10,ay=-15,bgcolor="white")
                        if info[2]+info[3]>max:
                            max=info[2]+info[3]
            for i in STRATUM[input.number_of_division()][0]:
                fig.add_trace(go.Scatter(x=[0, max], y=[i, i], mode='lines',line=dict(color='black', width=0.5),showlegend=False))
            custom_y_labels = STRATUM[input.number_of_division()][1]
            growth_forms=['bamboo', 'cactus', 'climber', 'herb', 'palm', 'shrub','subshrub','tree']
            colors = ['#53c5ff', '#49d1d5', "#dbb448", '#f8827a', '#ff8fda','#45d090',"#779137",'#d7a0ff']
            for growth, colr in zip(growth_forms, colors):
                fig.add_trace(go.Scatter(
                    x=[None],  
                    y=[None],
                    mode='markers',
                    marker=dict(size=10, color=colr),
                    showlegend=True,
                    name=growth,
                ))
            fig.update_yaxes(tickvals=list(custom_y_labels.keys()),ticktext=list(custom_y_labels.values()))
            fig.update_xaxes(title_text = 'Growth Period (year)') 
            fig.update_yaxes(title_text = 'Stratum')
            fig.update_layout(height=600)
            return fig

    #This function creates the cards for the missing informations on growth and strata
    @output
    @render.ui
    def card_wrong_plant():
        if input.database_choice() == "Normal Database": #Ignore the creation of the graph if the we don't select the good data source
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
        if input.database_choice() == "Normal Database": #Ignore the creation of the graph if the we don't select the good data source
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
 
    #This function run the R code to get the new species list if the GIFT database is chosen. Otherwise it returns the Normal Database
    @reactive.event(input.update_database)
    def get_new_species():
        if input.database_choice() == "GIFT Database":
            global SPECIES_GIFT_DATAFRAME
            flor_group=FLORISTIC_GROUP[input.floristic_group()]
            
            robjects.r.assign("flor_group",flor_group)
            robjects.r.assign("long",float(input.longitude()))
            robjects.r.assign("lat",float(input.latitude()))
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
        if input.database_choice()=="Normal Database":
            yield open_csv(FILE_NAME).to_csv()
        else:
            yield SPECIES_GIFT_DATAFRAME.to_csv()

##Growth Form

    #This functions creates the barchart and make it evolve depending on the lifetime chosen
    @render_widget
    def plot_plants():
        if input.database_choice() == "Normal Database": #Ignore the creation of the graph if the we don't select the good data source
            size=input.life_time()
            df=open_csv(FILE_NAME)
            plants=input.overview_plants()
            variables_x,variables_y,color,family,function,time_to_fh,life_hist,longev_prod,links,graph_y,color_change=[],[],[],[],[],[],[],[],[],[],[]

            for plant in plants:
                query=df.query("common_en == '%s'" % plant)[['common_en','growth_form','plant_max_height','family','function','yrs_ini_prod','life_hist','longev_prod','threat_status','ref']].values.tolist()[0]
                variables_x.append(query[0]),color.append(query[1]),family.append(str(query[3])),function.append(str(query[4])),time_to_fh.append(str(query[5])),life_hist.append(str(query[6])),longev_prod.append(str(query[7])),links.append([query[8]])
                if str(query[2])=='nan':
                    variables_y.append(3)
                else:
                    variables_y.append(query[2])
                if str(query[7])=='nan' or query[7]==0:
                    expect=7
                else:
                    expect=query[7]
                if str(query[2])=='nan':
                    graph_y_max=3
                else:
                    graph_y_max=query[2]
                graph_y.append(min(graph_y_max,size*graph_y_max/expect))
                if size==0:
                    graph_y[-1]=0.1
                print(graph_y)
                if size>expect:
                    color_change.append(query[0])
                
            dataframe=pd.DataFrame({
                        'Plant Name': variables_x,
                        'Maximum height': variables_y,
                        'Growth form' : color,
                        'Family' : family,
                        'Function':function,
                        'Time before harvest':time_to_fh,
                        'Life history':life_hist,
                        'Longevity':longev_prod,
                        'Graph height':graph_y,
                    })
            dataframe['Graph color'] = dataframe['Growth form']
            dataframe.loc[dataframe['Plant Name'].isin(color_change), 'Graph color'] = 'Dead'
            fig = px.bar(dataframe, 
                x='Plant Name', 
                y='Graph height', 
                color='Graph color', 
                labels={'Plant Name':'Plant Name', 'Graph height':'Graph Height (m)'},
                category_orders={'Plant Name' : variables_x},
                hover_name="Plant Name",
                hover_data={'Maximum height':True, 'Family':True, 'Growth form':True, 'Function':True,'Time before harvest':True,'Life history':True,'Longevity':True,'Graph height':False})
            
            fig.update_layout(height=650)
            return fig


##Other Species

    #This function return the table of all the species that are not selected. For the normal database, it makes suggestion, incompatible plants won't be shown, and for the GIFT one, it just shows the list
    @output
    @render.ui
    def suggestion_plants():
        if input.database_choice()=="Normal Database":
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
        return {"src": img_path, "alt": "Climate Image", "style": "width: 100%; height: auto;"}

