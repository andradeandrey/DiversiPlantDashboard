import pandas as pd
from math import *

def open_csv(file):
    return pd.read_csv(file)

def get_Variables(file):
    df = pd.read_csv(file)
    lifeForm=list(set(df["growth_form"].tolist()))
    lifeForm=[form for form in lifeForm if type(form)!=float]
    lifeForm.sort()
    VARIABLES={}
    for growth_form in lifeForm:
        VARIABLES[growth_form]={}
        plants=df.query("growth_form == '%s'" % growth_form)['common_pt'].tolist()
        plants.sort()
        for plant in plants:
            VARIABLES[growth_form][plant]=plant

    return VARIABLES

