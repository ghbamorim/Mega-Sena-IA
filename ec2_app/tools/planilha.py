import pandas as pd
import json

# Ler planilha sem cabeçalho, pulando linhas iniciais de texto
df = pd.read_excel("mega_sena.xlsx", skiprows=1, header=None)

# Definir manualmente os nomes das colunas
df.columns = ['Concurso', 'Data', 'bola 1', 'bola 2', 'bola 3', 'bola 4', 'bola 5', 'bola 6']

# Converter datas, forçando erros para NaT
df['Data'] = pd.to_datetime(df['Data'], format="%d/%m/%Y", errors='coerce')


# Pular linhas que não têm data válida
df = df[df['Data'].notna()]

json_list = []
for _, row in df.iterrows():
    date_str = row['Data'].strftime("%d %m %Y")
    numbers = " ".join(str(row[f'bola {i}']) for i in range(1, 7))
    json_list.append({
        "prompt": f"Digits: {date_str} -> Numbers:",
        "completion": f" {numbers}"
    })

with open("dataset_finetune.json", "w") as f:
    json.dump(json_list, f, indent=4)
