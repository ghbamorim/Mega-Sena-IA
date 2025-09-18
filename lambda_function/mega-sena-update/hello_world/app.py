import json
import boto3
import requests
import logging
from botocore.exceptions import ClientError

# Configuração básica de logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):

    # logger.info(f"Fazendo requisição GET para https://jsonplaceholder.typicode.com/posts/1")
    
    # try:
    #     response = requests.get("https://jsonplaceholder.typicode.com/posts/1")
    #     logger.info(f"Status code da resposta: {response.status_code}")
    # except Exception as e:
    #     logger.error(f"Exceção durante a requisição: {e}")
    #     return {
    #         "statusCode": 500,
    #         "body": json.dumps({"error": str(e)})
    #     }


    url = "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/"
    bucket_name = "megasena-json"
    file_key = "dataset.json"

    s3 = boto3.client("s3")
    
    logger.info("Iniciando execução da função Lambda")

    # Tenta baixar o arquivo do S3
    try:
        logger.info(f"Tentando baixar arquivo do S3: s3://{bucket_name}/{file_key}")
        response = s3.get_object(Bucket=bucket_name, Key=file_key)
        file_content = response["Body"].read().decode("utf-8")
        data_array = json.loads(file_content)
        logger.info(f"Arquivo encontrado com {len(data_array)} registros")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            data_array = []  # arquivo não existe
            logger.warning("Arquivo não encontrado no S3. Criando um novo array vazio")
        else:
            logger.error(f"Erro ao acessar S3: {e}")
            raise

    # Faz a requisição GET
    logger.info(f"Fazendo requisição GET para {url}")
    headers = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/116.0.0.0 Safari/537.36"
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        logger.error(f"Erro ao acessar API. Status code: {response.status_code}")
        return {
            "statusCode": response.status_code,
            "body": json.dumps({"error": "Error accessing API"})
        }

    data = response.json()
    logger.info(f"Dados recebidos da API: {data}")

    # Monta o formato desejado
    prompt = f"Digits: {data['dataApuracao'].replace('/', ' ')} -> Numbers:"
    completion = " " + " ".join(data['listaDezenas'])
    formatted = {
        "prompt": prompt,
        "completion": completion
    }
    logger.info(f"Registro formatado: {formatted}")

    # Adiciona ao array somente se ainda não estiver lá
    if formatted not in data_array:
        data_array.append(formatted)
        logger.info("Novo registro adicionado ao array")
    else:
        logger.info("Registro já existente. Nenhuma alteração feita")

    # Salva de volta no S3
    try:
        s3.put_object(
            Bucket=bucket_name,
            Key=file_key,
            Body=json.dumps(data_array),
            ContentType="application/json"
        )
        logger.info(f"Arquivo salvo no S3: s3://{bucket_name}/{file_key} com {len(data_array)} registros")
    except ClientError as e:
        logger.error(f"Erro ao salvar arquivo no S3: {e}")
        raise

    logger.info("Função Lambda finalizada com sucesso")

    return {
        "statusCode": 200,
        "body": json.dumps(formatted)
    }
