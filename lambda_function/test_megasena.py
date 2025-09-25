import json
from megasena_update import lambda_handler

if __name__ == "__main__":
    result = lambda_handler({}, None)
    print("Status:", result["statusCode"])
    print(json.dumps(result["body"], indent=2, ensure_ascii=False))
