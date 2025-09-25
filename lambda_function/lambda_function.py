import json
import boto3
import os
import requests
import time

S3_BUCKET = os.environ.get("S3_BUCKET", "meu-bucket")
s3 = boto3.client("s3", endpoint_url="http://s3.localhost.localstack.cloud:4566")

def lambda_handler(event, context):
    dataset = []

    # Carregar dataset existente do S3
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key="dataset.json")
        dataset = json.loads(response["Body"].read())
    except s3.exceptions.NoSuchKey:
        dataset = []
    except Exception as e:
        print(f"Erro ao carregar dataset: {e}")
        dataset = []

    # Consultar API da Caixa com retry
    url = "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://loterias.caixa.gov.br/",
        "Origin": "https://loterias.caixa.gov.br",
    }

    novo_registro = None
    for attempt in range(3):  # 3 tentativas
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                novo_registro = response.json()
            break
        except Exception as e:
            print(f"Tentativa {attempt+1} falhou: {e}")
            time.sleep(2)

    if novo_registro:
        # Extrair número e data
        number = novo_registro.get("numero")
        data = novo_registro.get("dataApuracao", "")  # "20/09/2025"
        digits = data.replace("/", " ")  # "20 09 2025"

        # Extrair dezenas
        dezenas = " ".join(novo_registro.get("listaDezenas", []))  # "06 19 38 41 46 57"

        # Montar novo formato
        novo_formato = {
            "number": number,
            "prompt": f"Digits: {digits} -> Numbers:",
            "completion": f" {dezenas}"
        }

        # Adicionar ao dataset se não existir
        if not any(item.get("number") == number for item in dataset):
            dataset.append(novo_formato)

            # Salvar dataset atualizado no S3
            try:
                s3.put_object(
                    Bucket=S3_BUCKET,
                    Key="dataset.json",
                    Body=json.dumps(dataset, ensure_ascii=False, indent=2),
                    ContentType="application/json"
                )
            except Exception as e:
                print(f"Erro ao salvar dataset: {e}")

    return {"dataset": dataset, "total_registros": len(dataset)}
