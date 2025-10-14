import pandas as pd

# Read Excel file
df = pd.read_excel("data/GIFT_practitioners.xlsx", sheet_name="GIFT_pract_traits")

# Export to UTF-8 encoded CSV (handles accents correctly)
df.to_csv("data/GIFT_practitioners.csv", index=False, encoding="utf-8-sig")

df = pd.read_excel("data/practitioners.xlsx", sheet_name="pract_spp_cons_status")
df.to_csv("data/practitioners.csv", index=False, encoding="utf-8-sig")