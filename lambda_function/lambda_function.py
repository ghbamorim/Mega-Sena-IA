import os
import json
import boto3
import logging
import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET = os.getenv("S3_BUCKET", "meu-bucket")
DATASET_FILE = os.getenv("DATASET_FILE", "dataset.json")
REGION = os.getenv("REGION", "us-east-1")
LOCALSTACK_URL = os.getenv("LOCALSTACK_URL_CONTAINER", "http://localstack:4566")

s3 = boto3.client(
    "s3",
    endpoint_url=LOCALSTACK_URL,
    region_name=REGION
)

def lambda_handler(event, context):
    dataset = []
    try:
        # Ler dataset existente
        logger.info(f"Lendo {DATASET_FILE} do bucket {BUCKET}...")
        response = s3.get_object(Bucket=BUCKET, Key=DATASET_FILE)
        dataset = json.loads(response["Body"].read())
        logger.info(f"Dataset carregado. Total de registros: {len(dataset)}")
    except s3.exceptions.NoSuchKey:
        logger.warning(f"{DATASET_FILE} não encontrado. Criando novo dataset...")
        dataset = []
    except Exception as e:
        logger.error(f"Erro ao carregar dataset: {e}")
        return {"dataset": dataset, "total_registros": len(dataset)}

    # Encontrar o último número de concurso no dataset
    last_number = dataset[0]["number"] if dataset else 0
    logger.info(f"Último concurso no dataset: {last_number}")

    # Consultar API para descobrir o último concurso
    try:
        r = requests.get("https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena",
                         timeout=10)
        r.raise_for_status()
        last_concurso_api = int(r.json()["numero"])
        logger.info(f"Último concurso na API: {last_concurso_api}")
    except Exception as e:
        logger.error(f"Erro ao buscar último concurso da API: {e}")
        last_concurso_api = last_number

    # Loop do último número do dataset até o último concurso da API
    loop_count = 0
    max_iterations = 10
    for concurso_num in range(last_number + 1, last_concurso_api + 1):
        if loop_count >= max_iterations:
            break

        url = f"https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/{concurso_num}"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            if "listaDezenas" in data and data["listaDezenas"]:
                numbers = " ".join(data["listaDezenas"])
                dataset.insert(0, {
                    "number": int(data["numero"]),
                    "prompt": f"Digits: {data['dataApuracao']} -> Numbers:",
                    "completion": f" {numbers}"
                })
                logger.info(f"Concurso {concurso_num} adicionado ao dataset.")
            else:
                logger.warning(f"Nenhum resultado para o concurso {concurso_num}")
        except Exception as e:
            logger.error(f"Erro ao buscar concurso {concurso_num}: {e}")

        loop_count += 1

    # Salvar dataset atualizado no S3
    try:
        s3.put_object(
            Bucket=BUCKET,
            Key=DATASET_FILE,
            Body=json.dumps(dataset, ensure_ascii=False).encode("utf-8")
        )
        logger.info(f"Dataset atualizado com sucesso. Total de registros: {len(dataset)}")
    except Exception as e:
        logger.error(f"Erro ao salvar dataset: {e}")

    # Retornar os 5 registros mais recentes
    return {"dataset": dataset[:5], "total_registros": len(dataset)}
