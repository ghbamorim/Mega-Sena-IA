import os
import json
import logging
import re
from datetime import datetime
import boto3
from transformers import AutoTokenizer, AutoModelForCausalLM

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class MegaSenaService:
    def __init__(self):
        self.use_s3 = os.getenv("USE_S3", "False").lower() == "true"
        self.bucket = os.getenv("S3_BUCKET", "meu-bucket")
        self.dataset_file = os.getenv("DATASET_FILE", "dataset.json")
        self.region = os.getenv("REGION", "us-east-1")
        self.localstack_url = os.getenv("LOCALSTACK_URL_CONTAINER", "http://localstack:4566")

        self.output_dir = os.getenv("OUTPUT_DIR", "./finetuned_mega")
        self.model_path = os.path.abspath(self.output_dir)
        self.local_dataset_path = os.getenv("DATASET_PATH_LOCAL", "./dataset.json")
        
        if self.use_s3:
            self.s3 = boto3.client(
                "s3",
                endpoint_url=self.localstack_url,
                region_name=self.region
            )        
        self.tokenizer = None
        self.model = None        
        self.past_numbers = {}
        
        self.load_model()
        self.load_dataset()


    def _extract_date_from_string(self, text: str) -> datetime | None:
        """Try to find a date inside the given text and return a datetime.date object.

        Accept formats like: `DD/MM/YYYY`, `DD-MM-YYYY`, `DD MM YYYY`, `YYYY-MM-DD`.
        Returns None if no date found or invalid.
        """
        if not text:
            return None
        
        patterns = [
            r"(\d{1,2})[\/\-\s](\d{1,2})[\/\-\s](\d{4})",  # day month year
            r"(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})"  # year-month-day
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

    def _register_past_numbers(self, date_obj: datetime, numbers: list[int], source_preview: str = ""):
        """Store the numbers under a few normalized keys so lookups are robust.

        Stored forms:
          - DD/MM/YYYY (primary)
          - DD MM YYYY
          - YYYY-MM-DD
        """
        if not date_obj:
            return

        key_slash = date_obj.strftime("%d/%m/%Y")
        key_space = date_obj.strftime("%d %m %Y")
        key_iso = date_obj.strftime("%Y-%m-%d")
        
        self.past_numbers[key_slash] = numbers
        self.past_numbers[key_space] = numbers
        self.past_numbers[key_iso] = numbers

        logger.debug(f"Registered past numbers for {key_slash} (source: {source_preview}) -> {numbers}")
    
    def load_model(self):
        logger.info("🔧 Loading model...")
        if os.path.isdir(self.model_path) and (
            os.path.exists(os.path.join(self.model_path, "model.safetensors")) or
            os.path.exists(os.path.join(self.model_path, "config.json"))
        ):
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
                self.model = AutoModelForCausalLM.from_pretrained(self.model_path, device_map="auto")
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
                logger.info(f"📦 Reading {self.dataset_file} from bucket {self.bucket}...")
                response = self.s3.get_object(Bucket=self.bucket, Key=self.dataset_file)
                body = response["Body"].read()
                dataset = json.loads(body)
                logger.info(f"✅ Dataset loaded from S3. Total records: {len(dataset)}")
            except self.s3.exceptions.NoSuchKey:
                logger.warning(f"⚠️ {self.dataset_file} not found in S3. Starting with empty dataset.")
            except Exception as e:
                logger.error(f"❌ Error loading dataset from S3: {e}")
        else:
            try:
                logger.info(f"📦 Loading local dataset from {self.local_dataset_path}...")
                with open(self.local_dataset_path, "r", encoding="utf-8") as f:
                    dataset = json.load(f)
                logger.info(f"✅ Dataset loaded locally. Total records: {len(dataset)}")
            except Exception as e:
                logger.error(f"❌ Error loading local dataset: {e}")
       
        logger.info("🔧 Preparing lookup table for past numbers...")
        for idx, entry in enumerate(dataset, start=1):
            prompt = entry.get("prompt", "")
            completion = entry.get("completion", "")
            
            date_obj = self._extract_date_from_string(prompt) or self._extract_date_from_string(completion)

            if not date_obj:
                logger.debug(f"Skipping entry {idx}: no date found in prompt/completion. Prompt preview: {prompt[:60]}")
                continue

            numbers_tokens = re.findall(r"\b\d+\b", completion)
            numbers = [int(x) for x in numbers_tokens]

            self._register_past_numbers(date_obj, numbers, source_preview=(prompt[:40] or completion[:40]))

            if idx <= 5:
                logger.info(f"  {idx}: {date_obj.strftime('%d/%m/%Y')} -> Numbers: {numbers}")

        logger.info(f"✅ Lookup table ready. Total past dates (unique keys): {len(self.past_numbers)}")

    def generate_prediction(self, date_str: str) -> list[int]:
        if self.tokenizer is None or self.model is None:
            raise RuntimeError("Model not loaded yet. Run fine-tuning first.")

        logger.info(f"🔹 Generating prediction for date: {date_str}")

        date_obj = self._extract_date_from_string(date_str)
        if not date_obj:
            normalized_try = " ".join(date_str.replace("/", " ").strip().split())
            date_obj = self._extract_date_from_string(normalized_try)

        if not date_obj:
            logger.error(f"❌ Invalid date format: {date_str}")
            raise ValueError("Invalid date format. Use DD/MM/YYYY (or similar).")

        key_slash = date_obj.strftime("%d/%m/%Y")
               
        if key_slash in self.past_numbers:
            logger.info(f"🔹 Date {key_slash} found in past numbers lookup (using key '{key_slash}').")
            return self.past_numbers[key_slash]
       
        today = datetime.today().date()
        if date_obj.date() <= today:
            logger.warning(f"⚠️ Date {key_slash} is not in the future and not found in dataset. Returning empty list.")
            return []
        
        prompt = f"Digits: {key_slash} -> Numbers:"
        input_ids = self.tokenizer(prompt, return_tensors="pt").input_ids

        output_ids = self.model.generate(
            input_ids,
            max_new_tokens=40,
            do_sample=True,
            temperature=0.8,
            top_p=0.9,
            eos_token_id=self.tokenizer.eos_token_id,
            pad_token_id=self.tokenizer.eos_token_id
        )[0]

        output_text = self.tokenizer.decode(output_ids, skip_special_tokens=True)
        numbers_str = output_text.split("Numbers")[-1]

        try:
            numbers = [int(x) for x in re.findall(r"\b\d+\b", numbers_str)]
        except Exception:
            numbers = []

        logger.info(f"🔹 Generated numbers: {numbers[:6]}")
        return numbers[:6]

mega_service = MegaSenaService()

def generate_prediction(date_str: str) -> list[int]:
    return mega_service.generate_prediction(date_str)
