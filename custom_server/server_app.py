import os
import numpy as np
import pandas as pd
from pathlib import Path
import plotly.express as px
from shinywidgets import render_widget
from shiny import render, ui
import plotly.graph_objects as go
from custom_server.agroforestry_server import open_csv


FILE_NAME = os.path.join(Path(__file__).parent.parent,"data","MgmtTraitData_CSV.csv")

COLOR = {'Herb' : '#f8827a','Climber':"#dbb448",'Subshrub' : "#779137",'Shrub' :'#45d090','Cactus' : '#49d1d5','Bamboo' : '#53c5ff','Tree' : '#d7a0ff','Palm' : '#ff8fda'}

def server_app(input,output,session):

    @output
    @render.text
    def text_plant():
        return input.overview_plants()

    @render_widget
    def plot_plants():
        size=input.life_time()
        df=open_csv(FILE_NAME)
        plants=input.overview_plants()
        variables_x,variables_y,color,family,function,time_to_fh,life_hist,longev_prod,links,graph_y,color_change=[],[],[],[],[],[],[],[],[],[],[]

        for plant in plants:
            query=df.query("common_pt == '%s'" % plant)[['common_pt','growth_form','plant_max_height','family','function','yrs_ini_prod','life_hist','longev_prod','threat_status','ref']].values.tolist()[0]
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
             labels={'Plant Name':'Plant Name', 'Graph height':'Graph Height'},
             category_orders={'Plant Name' : variables_x},
             hover_name="Plant Name",
             hover_data={'Maximum height':True, 'Family':True, 'Growth form':True, 'Function':True,'Time before harvest':True,'Life history':True,'Longevity':True,'Graph height':False})
        
        fig.update_layout(height=650)
        return fig

    @output
    @render.ui
    def suggestion():
        df=open_csv(FILE_NAME)
        plants=input.overview_plants()
        stratum=input.number_of_division()
        cards_suggestion=[]
        true_plants=[]
        stratums=[]
        for plant in plants:
            query=df.query("common_pt == '%s'" % plant)[['common_pt','yrs_ini_prod','longev_prod','stratum']].values.tolist()[0]
            
            if str(query[3])!='nan' and str(query[2])!='nan' and str(query[1])!='nan':
                true_plants.append(query)
                stratums.append(query[3])
        
        first_sgg = df[~df['stratum'].isin(stratums)]
        first_sgg = first_sgg[first_sgg['stratum'].notna()]
        first_sgg = first_sgg[['common_pt','growth_form','plant_max_height','stratum','family','function','yrs_ini_prod','life_hist','longev_prod','threat_status']]
        
        total_sgg = first_sgg[~df['common_pt'].isin(plants)]

        if len(total_sgg)>12:
            total_sgg=total_sgg.sample(n=12)
        
        list_of_card = total_sgg.values.tolist()
        print(list_of_card)
        for info in list_of_card:
            card=ui.card(
                ui.div(
                    ui.h4(info[0].capitalize(), class_="card_title"),
                        ui.p(ui.tags.b("Growth form: "), ui.a(f"{info[1]}")),
                        ui.p(ui.tags.b("Maximum height: "), ui.a(f"{info[2]}")),
                        ui.p(ui.tags.b("Stratum: "), ui.a(f"{info[3]}")),
                        ui.p(ui.tags.b("Family: "), ui.a(f"{info[4]}")),
                        ui.p(ui.tags.b("Function: "), ui.a(f"{info[5]}")),
                        ui.p(ui.tags.b("Time before harvest: "), ui.a(f"{info[6]}")),
                        ui.p(ui.tags.b("Life history: "), ui.a(f"{info[7]}")),
                        ui.p(ui.tags.b("Longevity: "), ui.a(f"{info[8]}"))
                )
            )
            cards_suggestion.append(card)
        return ui.layout_columns(*cards_suggestion, col_widths=[4,4,4])

    def tri():
        df=open_csv(FILE_NAME)
        plants=input.overview_plants()
        good,bad_year,bad_stratum=[],[],[]
        for plant in plants:
            query=df.query("common_pt == '%s'" % plant)[['common_pt','growth_form','yrs_ini_prod','longev_prod','stratum']].values.tolist()[0]
            if str(query[2])!='nan' and str(query[3])!='nan' and str(query[4])!='nan': 
                good.append(query)
            elif str(query[4])=='nan':
                bad_stratum.append(query[0])
            else:
                bad_year.append(query[0])
        return [good,bad_year,bad_stratum]
 
    @render_widget
    def intercrops():
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
        for i in range (9):
            fig.add_trace(go.Scatter(x=[0, max], y=[i, i], mode='lines',line=dict(color='black', width=0.5),showlegend=False))
        custom_y_labels = {0.5: "Ground",1.5: "Ground-Low",2.5: "Low",3.5: "Low-Medium",4.5: "Medium",5.5: "Medium-High",6.5: "High",7.5: "High-Emergent",8.5: "Emergent"}
        growth_forms=['Bamboo', 'Cactus', 'Climber', 'Herb', 'Palm', 'Shrub','Subshrub','Tree']
        colors = ['#53c5ff', '#49d1d5', "#dbb448", '#f8827a', '#ff8fda','#45d090',"#779137",'#d7a0ff']
        for growth, colr in zip(growth_forms, colors):
            fig.add_trace(go.Scatter(
                x=[None],  # Trace invisible
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

    @output
    @render.ui
    def card_wrong_plant():
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
    
