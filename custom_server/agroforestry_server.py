import pandas as pd
from math import *

def open_csv(file):
    return pd.read_csv(file)


#Give the list of the plants, groupes by growth_form
# Label includes common_pt + sci_name so selectize search works with popular names
def get_Plants(file):
    df = pd.read_csv(file)
    lifeForm=list(set(df["growth_form"].tolist()))
    lifeForm=[form for form in lifeForm if type(form)!=float]
    lifeForm.sort()
    VARIABLES={}
    for growth_form in lifeForm:
        VARIABLES[growth_form]={}
        subset = df[df["growth_form"] == growth_form]
        for _, row in subset.iterrows():
            cn = row.get('common_en')
            if not isinstance(cn, str):
                continue
            parts = [cn]
            pt = row.get('common_pt')
            if isinstance(pt, str) and pt != cn:
                parts.append(pt)
            sn = row.get('sci_name')
            if isinstance(sn, str):
                parts.append(sn)
            VARIABLES[growth_form][cn] = " · ".join(parts)

    return VARIABLES