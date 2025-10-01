import os
import logging
import json
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    Trainer,
    TrainingArguments,
    DataCollatorForLanguageModeling,
)
import boto3

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class TrainService:
    def __init__(self):
        self.model_name = "EleutherAI/gpt-neo-125M"
        self.output_dir = "./finetuned_mega"
        self.use_s3 = os.getenv("USE_S3", "False").lower() == "true"
        self.bucket = os.getenv("S3_BUCKET", "my-bucket")
        self.dataset_file = os.getenv("DATASET_FILE", "dataset.json")
        self.region = os.getenv("REGION", "us-east-1")
        self.localstack_url = os.getenv("LOCALSTACK_URL_CONTAINER", "http://localstack:4566")

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForCausalLM.from_pretrained(self.model_name)

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    def _load_dataset(self):
        """Load dataset from S3 or local file"""
        data = []
        if self.use_s3:
            try:
                s3 = boto3.client(
                    "s3",
                    endpoint_url=self.localstack_url,
                    region_name=self.region
                )
                response = s3.get_object(Bucket=self.bucket, Key=self.dataset_file)
                data = json.loads(response["Body"].read())
                logger.info(f"✅ Dataset loaded from S3 ({self.bucket}/{self.dataset_file})")
            except Exception as e:
                logger.error(f"❌ Failed to load dataset from S3: {e}")
                raise
        else:
            if not os.path.exists(self.dataset_file):
                raise FileNotFoundError(f"❌ {self.dataset_file} not found!")
            with open(self.dataset_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info("✅ Dataset loaded locally")

        texts = [item.get("prompt", "") + item.get("completion", "") for item in data]
        return Dataset.from_dict({"text": texts})

    def _tokenize(self, examples):
        """Tokenize dataset samples"""
        return self.tokenizer(
            examples["text"],
            truncation=True,
            padding="max_length",
            max_length=64,
        )

    def train(self):
        logger.info("📥 Loading dataset...")
        dataset = self._load_dataset()

        logger.info("🔄 Tokenizing dataset...")
        tokenized = dataset.map(self._tokenize, batched=True)

        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer, mlm=False
        )

        training_args = TrainingArguments(
            output_dir=self.output_dir,
            overwrite_output_dir=True,
            num_train_epochs=10,
            per_device_train_batch_size=2,
            save_strategy="epoch",
            logging_dir="./logs",
            logging_steps=10,
            learning_rate=1e-4,
            weight_decay=0.01,
        )

        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=tokenized,
            tokenizer=self.tokenizer,
            data_collator=data_collator,
        )

        logger.info("🚀 Starting training...")
        trainer.train()

        logger.info("💾 Saving model to %s", self.output_dir)
        trainer.save_model(self.output_dir)
        self.tokenizer.save_pretrained(self.output_dir)
        logger.info("✅ Training completed!")


def train_model():
    """Wrapper called by controller"""
    service = TrainService()
    service.train()
