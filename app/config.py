import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    USE_S3: bool = os.getenv("USE_S3", "False").lower() == "true"
    S3_BUCKET: str = os.getenv("S3_BUCKET", "")
    DATASET_PATH_S3: str = os.getenv("DATASET_PATH_S3", "")
    DATASET_PATH_LOCAL: str = os.getenv("DATASET_PATH_LOCAL", "./dataset.json")
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "./finetuned_mega")
    BASE_MODEL: str = os.getenv("BASE_MODEL", "EleutherAI/gpt-neo-125M")

config = Config()
