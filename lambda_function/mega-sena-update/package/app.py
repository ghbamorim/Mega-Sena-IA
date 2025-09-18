import json
import boto3
import logging
from botocore.exceptions import ClientError
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    bucket_name = "megasena-json"
    file_key = "dataset.json"
    s3 = boto3.client("s3")

    # Tenta baixar arquivo do S3
    try:
        response = s3.get_object(Bucket=bucket_name, Key=file_key)
        file_content = response["Body"].read().decode("utf-8")
        data_array = json.loads(file_content)
        logger.info(f"Arquivo encontrado com {len(data_array)} registros")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            data_array = []
            logger.warning("Arquivo não encontrado no S3. Criando array vazio")
        else:
            logger.error(f"Erro ao acessar S3: {e}")
            raise

    # Configuração do Chrome headless
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.binary_location = "/opt/headless-chromium"  # layer

    service = Service("/opt/chromedriver")  # caminho do chromedriver na layer
    driver = webdriver.Chrome(service=service, options=chrome_options)



    try:
        url = "https://loterias.caixa.gov.br/Paginas/Mega-Sena.aspx"
        logger.info(f"Acessando página: {url}")
        driver.get(url)
        time.sleep(5)  # aguarda carregamento da página

        # Seleciona concurso e dezenas
        concurso = driver.find_element(By.CSS_SELECTOR, ".resultado-loteria .numero-concurso").text
        dezenas = [elem.text for elem in driver.find_elements(By.CSS_SELECTOR, ".resultado-loteria .numeros-sorteio li")]

        prompt = f"Digits: {concurso.replace('/', ' ')} -> Numbers:"
        completion = " " + " ".join(dezenas)
        formatted = {"prompt": prompt, "completion": completion}

        if formatted not in data_array:
            data_array.append(formatted)
            logger.info("Novo registro adicionado")
        else:
            logger.info("Registro já existente")

    finally:
        driver.quit()

    # Salva no S3
    try:
        s3.put_object(
            Bucket=bucket_name,
            Key=file_key,
            Body=json.dumps(data_array),
            ContentType="application/json"
        )
        logger.info(f"Arquivo salvo no S3 com {len(data_array)} registros")
    except ClientError as e:
        logger.error(f"Erro ao salvar no S3: {e}")
        raise

    return {"statusCode": 200, "body": json.dumps(formatted)}
