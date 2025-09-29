import os
import pandas as pd
import json

# Absolute path relative to this .py file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
excel_path = os.path.join(BASE_DIR, "mega_sena.xlsx")

# Read spreadsheet
df = pd.read_excel(excel_path, skiprows=1, header=None)

# Manually set column names
df.columns = ['Contest', 'Date', 'ball 1', 'ball 2', 'ball 3', 'ball 4', 'ball 5', 'ball 6']

# Convert dates, forcing errors to NaT
df['Date'] = pd.to_datetime(df['Date'], format="%d/%m/%Y", errors='coerce')

# Skip rows without a valid date
df = df[df['Date'].notna()]

json_list = []
for _, row in df.iterrows():
    date_str = row['Date'].strftime("%d %m %Y")
    numbers = " ".join(str(row[f'ball {i}']) for i in range(1, 7))
    json_list.append({
        "number": int(row['Contest']),
        "prompt": f"Digits: {date_str} -> Numbers:",
        "completion": f" {numbers}"
    })

output_path = os.path.join(BASE_DIR, "dataset.json")
with open(output_path, "w") as f:
    json.dump(json_list, f, indent=4)

print(f"File generated at {output_path}")
