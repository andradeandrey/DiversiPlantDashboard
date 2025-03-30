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


def server_homepage(input, output, session):
        @render.image
        def homepage_image():
            img_path = "data/img/homepage.jpg"
            return {"src": img_path}