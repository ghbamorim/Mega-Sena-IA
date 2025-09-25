import json
import requests

def lambda_handler(event, context):
    url = "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://loterias.caixa.gov.br/",
        "Origin": "https://loterias.caixa.gov.br",
    }
    response = requests.get(url, headers=headers)
    return {
        "statusCode": response.status_code,
        "body": response.json()
    }
