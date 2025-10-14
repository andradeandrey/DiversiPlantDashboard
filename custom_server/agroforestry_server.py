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


# #Give the list of all the different functions 
# def get_Function(file):
#     df = pd.read_csv(file)
#     functions=list(set(df["function"].tolist()))
#     functions2=list(set(df["function2"].tolist()))
#     total=functions+functions2
#     FUNCTIONS=[]
#     for fct in total:
#         if str(fct)!='nan':
#             FUNCTIONS.append(fct)

#     FUNCTIONS.sort()
    
#     return FUNCTIONS

# import pandas as pd
# from math import *

# def open_csv(file):
#     return pd.read_csv(file)

# def _safe_sorted_strings(values):
#     # Keep only non-empty strings and sort case-insensitively
#     return sorted(
#         [v.strip() for v in values if isinstance(v, str) and v.strip()],
#         key=str.casefold
#     )

# # Give the list of the plants, grouped by growth_form
# def get_Plants(file):
#     df = pd.read_csv(file)

#     # Normalize the relevant columns
#     for col in ["growth_form", "common_en"]:
#         if col in df.columns:
#             df[col] = df[col].where(pd.notna(df[col]), None)  # turn NaN -> None
#             # cast everything to string where possible without crashing sort
#             df[col] = df[col].apply(lambda x: x if isinstance(x, str) else x)

#     life_forms = _safe_sorted_strings(df["growth_form"].dropna().tolist())

#     VARIABLES = {}
#     for growth_form in life_forms:
#         plants_series = df.loc[df["growth_form"] == growth_form, "common_en"].dropna()
#         plants = _safe_sorted_strings(plants_series.tolist())
#         VARIABLES[growth_form] = {plant: plant for plant in plants}

#     return VARIABLES

# # Give the list of all the different functions
# def get_Function(file):
#     df = pd.read_csv(file)

#     col_a = df["function"] if "function" in df.columns else pd.Series([], dtype=object)
#     col_b = df["function2"] if "function2" in df.columns else pd.Series([], dtype=object)

#     total = pd.concat([col_a, col_b], ignore_index=True)
#     total = total.dropna().tolist()
#     FUNCTIONS = _safe_sorted_strings(total)

#     return FUNCTIONS