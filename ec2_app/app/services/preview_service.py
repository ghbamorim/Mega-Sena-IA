import os
import json
import logging
import re
from datetime import datetime
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import random

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class MegaSenaService:
    def __init__(self):
        self.use_s3 = os.getenv("USE_S3", "False").lower() == "true"
        self.bucket = os.getenv("S3_BUCKET", "my-bucket")
        self.dataset_file = os.getenv("DATASET_FILE", "dataset.json")
        self.region = os.getenv("REGION", "us-east-1")
        self.localstack_url = os.getenv("LOCALSTACK_URL_CONTAINER", "http://localstack:4566")
        self.output_dir = os.getenv("OUTPUT_DIR", "./finetuned_mega")
        self.model_path = os.path.abspath(self.output_dir)
        self.local_dataset_path = os.getenv("DATASET_PATH_LOCAL", "./dataset.json")

        self.tokenizer = None
        self.model = None
        self.past_numbers = {}

        self.load_model()
        self.load_dataset()

    def _extract_date_from_string(self, text: str) -> datetime | None:
        if not text:
            return None
        patterns = [
            r"(\d{1,2})[\/\-\s](\d{1,2})[\/\-\s](\d{4})",
            r"(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})"
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if not m:
                continue
            groups = m.groups()
            try:
                if len(groups) == 3:
                    if len(groups[0]) == 4:
                        year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                    else:
                        day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                    return datetime(year=year, month=month, day=day)
            except ValueError:
                continue
        return None

    def _register_past_numbers(self, date_obj: datetime, numbers: list[int]):
        if not date_obj:
            return
        key_slash = date_obj.strftime("%d/%m/%Y")
        self.past_numbers[key_slash] = numbers

    def load_model(self):
        logger.info("🔧 Loading model...")
        if os.path.isdir(self.model_path) and (
            os.path.exists(os.path.join(self.model_path, "pytorch_model.bin")) or
            os.path.exists(os.path.join(self.model_path, "model.safetensors"))
        ):
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
                self.model = AutoModelForCausalLM.from_pretrained(self.model_path, device_map="auto")
                if self.tokenizer.pad_token is None:
                    self.tokenizer.pad_token = self.tokenizer.eos_token
                logger.info(f"✅ Model loaded successfully from {self.model_path}")
            except Exception as e:
                logger.error(f"❌ Error loading model: {e}")
                self.tokenizer = None
                self.model = None
        else:
            logger.warning(f"⚠️ No model found in {self.model_path}. Run fine-tuning first.")

    def load_dataset(self):
        logger.info("🔧 Loading dataset...")
        dataset = []
        if self.use_s3:
            try:
                import boto3
                s3 = boto3.client("s3", endpoint_url=self.localstack_url, region_name=self.region)
                response = s3.get_object(Bucket=self.bucket, Key=self.dataset_file)
                dataset = json.loads(response["Body"].read())
                logger.info(f"✅ Dataset loaded from S3 ({self.bucket}/{self.dataset_file})")
            except Exception as e:
                logger.error(f"❌ Error loading dataset from S3: {e}")
        else:
            try:
                with open(self.local_dataset_path, "r", encoding="utf-8") as f:
                    dataset = json.load(f)
                    logger.info("✅ Dataset loaded locally")
            except Exception as e:
                logger.error(f"❌ Error loading local dataset: {e}")

        for entry in dataset:
            prompt = entry.get("prompt", "")
            completion = entry.get("completion", "")
            date_obj = self._extract_date_from_string(prompt) or self._extract_date_from_string(completion)
            if not date_obj:
                continue
            numbers_tokens = re.findall(r"\b\d+\b", completion)
            numbers = [int(x) for x in numbers_tokens]
            self._register_past_numbers(date_obj, numbers)

    def generate_prediction(self, date_str: str) -> list[int]:
        if self.tokenizer is None or self.model is None:
            raise RuntimeError("Model not loaded yet. Run fine-tuning first.")

        date_obj = self._extract_date_from_string(date_str)
        if not date_obj:
            normalized_try = " ".join(date_str.replace("/", " ").strip().split())
            date_obj = self._extract_date_from_string(normalized_try)
        if not date_obj:
            raise ValueError("Invalid date format. Use DD/MM/YYYY (or similar).")

        key_slash = date_obj.strftime("%d/%m/%Y")
        if key_slash in self.past_numbers:
            logger.info(f"🔹 Found past numbers for {key_slash}: {self.past_numbers[key_slash]}")
            return self.past_numbers[key_slash]

        today = datetime.today().date()
        if date_obj.date() <= today:
            logger.info("⚠️ Date is in the past or today. No prediction possible.")
            return []

        prompt = f"Predict numbers for {key_slash}:"
        logger.info(f"📝 Prompt sent to model: {prompt}")

        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            padding="max_length",
            max_length=128
        )

        input_ids = inputs.input_ids.to(self.model.device)
        attention_mask = inputs.attention_mask.to(self.model.device)

        output_ids = self.model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            max_new_tokens=32,
            do_sample=True,
            temperature=0.8,
            top_p=0.9,
            eos_token_id=self.tokenizer.eos_token_id,
            pad_token_id=self.tokenizer.pad_token_id
        )[0]

        output_text = self.tokenizer.decode(output_ids, skip_special_tokens=True)
        logger.info(f"📤 Raw model output: {output_text}")

        numbers = [int(x) for x in re.findall(r"\b\d+\b", output_text)]
        numbers = [n for n in numbers if 1 <= n <= 60]

        # Ensure exactly 6 unique numbers
        final_numbers = []
        for n in numbers:
            if n not in final_numbers:
                final_numbers.append(n)
            if len(final_numbers) == 6:
                break
        while len(final_numbers) < 6:
            candidate = random.randint(1, 60)
            if candidate not in final_numbers:
                final_numbers.append(candidate)

        logger.info(f"🎯 Final prediction: {final_numbers}")
        return final_numbers


mega_service = MegaSenaService()

def generate_prediction(date_str: str) -> list[int]:
    return mega_service.generate_prediction(date_str)
