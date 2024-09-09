import pandas as pd
from math import *

def open_csv(file):
    return pd.read_csv(file)


#Give the list of the plants, groupes by growth_form
def get_Plants(file):
    df = pd.read_csv(file)
    lifeForm=list(set(df["growth_form"].tolist()))
    lifeForm=[form for form in lifeForm if type(form)!=float]
    lifeForm.sort()
    VARIABLES={}
    for growth_form in lifeForm:
        VARIABLES[growth_form]={}
        plants=df.query("growth_form == '%s'" % growth_form)['common_en'].tolist()
        plants.sort()
        for plant in plants:
            VARIABLES[growth_form][plant]=plant

    return VARIABLES


#Give the list of all the different functions 
def get_Function(file):
    df = pd.read_csv(file)
    functions=list(set(df["function"].tolist()))
    functions2=list(set(df["function2"].tolist()))
    total=functions+functions2
    FUNCTIONS=[]
    for fct in total:
        if str(fct)!='nan':
            FUNCTIONS.append(fct)

    FUNCTIONS.sort()
    
    return FUNCTIONS

