import json
import boto3
import requests
from botocore.exceptions import ClientError

S3_BUCKET = "meu-bucket"
S3_KEY = "dataset.json"

def lambda_handler(event, context):
    # Criar cliente S3
    s3 = boto3.client(
        "s3",
        endpoint_url="http://host.docker.internal:4566",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1"
    )

    # -------------------------------
    # 1️⃣ Carregar dataset existente do S3
    # -------------------------------
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
        dataset = json.loads(response["Body"].read())
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            dataset = []
        else:
            raise e

    # -------------------------------
    # 2️⃣ Chamar API da Mega-Sena
    # -------------------------------
    url = "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://loterias.caixa.gov.br/",
        "Origin": "https://loterias.caixa.gov.br",
    }
    response = requests.get(url, headers=headers)
    api_data = response.json()

    # -------------------------------
    # 3️⃣ Verificar se o registro já existe
    # -------------------------------
    if not any(entry["numero"] == api_data["numero"] for entry in dataset):
        dataset.append(api_data)
        # Salvar de volta no S3
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=S3_KEY,
            Body=json.dumps(dataset).encode("utf-8")
        )

    return {
        "statusCode": 201,
        "body": dataset
    }
