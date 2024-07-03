import os
import dotenv
import pandas as pd
import plotly.express as px
from shinywidgets import render_widget
from shiny import render, ui
import plotly.graph_objects as go
from custom_server.agroforestry_server import open_csv
dotenv.load_dotenv("./db.env")

FILE_NAME = os.environ["FILE_NAME"]

COLOR = {'Herb' : '#f8827a','Climber':"#dbb448",'Subshrub' : "#779137",'Shrub' :'#45d090','Cactus' : '#49d1d5','Bamboo' : '#53c5ff','Tree' : '#d7a0ff','Palm' : '#ff8fda'}

def server_app(input,output,session):

    @output
    @render.text
    def text_plant():
        return input.overview_plants()

    @render_widget
    def plot_plants():
        df=open_csv(FILE_NAME)
        plants=input.overview_plants()
        variables_x,variables_y,color,family,function,time_to_fh,life_hist,longev_prod,links=[],[],[],[],[],[],[],[],[]
        for plant in plants:
            query=df.query("common_pt == '%s'" % plant)[['common_pt','growth_form','plant_max_height','family','function','yrs_ini_prod','life_hist','longev_prod','threat_status','ref']].values.tolist()[0]
            variables_x.append(query[0]),color.append(query[1]),family.append(str(query[3])),function.append(str(query[4])),time_to_fh.append(str(query[5])),life_hist.append(str(query[6])),longev_prod.append(str(query[7])),links.append([query[8]])
            if str(query[2])=='nan':
                variables_y.append(3)
            else:
                variables_y.append(query[2])
        dataframe=pd.DataFrame({
                    'Plant Name': variables_x,
                    'Maximum height': variables_y,
                    'Growth form' : color,
                    'Family' : family,
                    'Function':function,
                    'Time before harvest':time_to_fh,
                    'Life history':life_hist,
                    'Longevity':longev_prod
                })
        fig = px.bar(dataframe, 
             x='Plant Name', 
             y='Maximum height', 
             color='Growth form', 
             labels={'Plant Name':'Plant Name', 'Maximum height':'Maximum Height'},
             category_orders={'Plant Name' : variables_x},
             hover_name="Plant Name",
             hover_data=['Family','Function','Time before harvest','Life history','Longevity'])
        return fig
        """for i, link in enumerate(links):
            fig.add_annotation(
                x=i,
                y=variables_y[i],
                text=f"<a href='{link}'>{variables_x[i]}</a>",
                showarrow=False,
                font=dict(size=14)
            )"""
    @output
    @render.ui
    def suggestion():
        df=open_csv(FILE_NAME)
        plants=input.overview_plants()
        cards_suggestion=[]
        for plant in plants:
            query=df.query("common_pt == '%s'" % plant)[['common_pt','growth_form','yrs_ini_prod','longev_prod','stratum']].values.tolist()[0]
            info=[plant,query[4]]
            suggestion=[]
            if str(info[1])=='nan':
                suggestion.append(ui.a('Missing stratum information'))
            else:
                query_bis=df.query(f"stratum == {8-info[1]}")[['common_pt']].head(5).values.tolist()
                print(query_bis)
                for sugg in query_bis:
                    suggestion.append(ui.p(f"{sugg[0]}"))
            card=ui.card(
                ui.div(
                    ui.h5(f"Suggestion combination with {plant} :"),
                    *suggestion
                )
            )
            cards_suggestion.append(card)
        return ui.layout_columns(*cards_suggestion, col_widths=[3,3,3,3])

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
                fig.add_trace(go.Scatter(x=[info[2], info[2]+info[3]], y=[indice+0.5, indice+0.5], name=info[0],mode='lines',line=dict(color=COLOR[info[1]], width=5)))
                fig.add_annotation(x=info[2],y=indice+0.5,text=info[0],font=dict(color="black"), align="center",ax=-10,ay=-15,bgcolor="white")
                if info[2]+info[3]>max:
                    max=info[2]+info[3]
            else:
                for i in range(n):
                    info=repartition[indice][i]
                    fig.add_trace(go.Scatter(x=[info[2], info[2]+info[3]], y=[indice+(0.1+0.8*i/(n-1)), indice+(0.1+0.8*i/(n-1))],name=info[0], mode='lines',line=dict(color=COLOR[info[1]], width=5)))
                    fig.add_annotation(x=info[2],y=indice+(0.1+0.8*i/(n-1)),text=info[0],font=dict(color="black"),align="center",ax=-10,ay=-15,bgcolor="white")
                    if info[2]+info[3]>max:
                        max=info[2]+info[3]
        for i in range (9):
            fig.add_trace(go.Scatter(x=[0, max], y=[i, i], mode='lines',line=dict(color='black', width=0.5),showlegend=False))
        custom_y_labels = {0.5: "Ground",1.5: "Ground-Low",2.5: "Low",3.5: "Low-Medium",4.5: "Medium",5.5: "Medium-High",6.5: "High",7.5: "High-Emergent",8.5: "Emergent"}
        fig.update_yaxes(tickvals=list(custom_y_labels.keys()),ticktext=list(custom_y_labels.values()))
        fig.update_xaxes(title_text = 'Growth Period (year)') 
        fig.update_yaxes(title_text = 'Stratum')
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
        third_card = ui.card(
            ui.h5("Color of the graph :"),
            ui.a(ui.div("Bamboo",class_="bamboo")),
            ui.a(ui.div("Cactus",class_="cactus")),
            ui.a(ui.div("Climber"),class_="climber"),
            ui.a(ui.div("Herb"),class_="herb"),
            ui.a(ui.div("Palm"),class_="palm"),
            ui.a(ui.div("Shurb"),class_="shurb"),
            ui.a(ui.div("Subshurb"),class_="subshurb"),
            ui.a(ui.div("Tree"),class_="tree")
        )
        cards = [third_card] + cards
        return ui.layout_columns(*cards,col_widths=[4,4,4])
