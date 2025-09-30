import os
import tempfile
import boto3
import json
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    Trainer,
    TrainingArguments,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model

LOCALSTACK_URL = os.getenv("LOCALSTACK_URL_CONTAINER", "http://localstack:4566")
REGION = os.getenv("REGION", "us-east-1")
USE_S3 = os.getenv("USE_S3", "False").lower() == "true"
S3_BUCKET = os.getenv("S3_BUCKET", "")
DATASET_PATH_LOCAL: str = os.getenv("DATASET_PATH_LOCAL", "./dataset.json")
OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "./finetuned_mega")
BASE_MODEL: str = os.getenv("BASE_MODEL", "EleutherAI/gpt-neo-125M")
LOCAL_MODEL_PATH: str = os.getenv("LOCAL_MODEL_PATH", "./models/EleutherAI/gpt-neo-125M")
DATASET_FILE = os.getenv("DATASET_FILE", "dataset.json")
BUCKET = S3_BUCKET

def prepare_model():
    if os.path.isdir(LOCAL_MODEL_PATH) and os.path.exists(os.path.join(LOCAL_MODEL_PATH, "config.json")):
        print(f"✅ Local model found in {LOCAL_MODEL_PATH}")
    else:
        print(f"⬇️ Downloading {BASE_MODEL} from Hugging Face...")
        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
        model = AutoModelForCausalLM.from_pretrained(BASE_MODEL)
        os.makedirs(LOCAL_MODEL_PATH, exist_ok=True)
        tokenizer.save_pretrained(LOCAL_MODEL_PATH)
        model.save_pretrained(LOCAL_MODEL_PATH)
        print(f"✅ Model saved to {LOCAL_MODEL_PATH}")

def train_model():
    prepare_model()
    model_name_local = LOCAL_MODEL_PATH

    # Load dataset
    if USE_S3:
        s3 = boto3.client("s3", endpoint_url=LOCALSTACK_URL, region_name=REGION)
        response = s3.get_object(Bucket=BUCKET, Key=DATASET_FILE)
        dataset = json.loads(response["Body"].read())
        tmp_dataset = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        with open(tmp_dataset.name, "w", encoding="utf-8") as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)
        dataset_path_local = tmp_dataset.name
    else:
        dataset_path_local = DATASET_PATH_LOCAL

    dataset = load_dataset("json", data_files=dataset_path_local)

    # Check for incremental training
    incremental = os.path.isdir(OUTPUT_DIR) and os.path.exists(os.path.join(OUTPUT_DIR, "pytorch_model.bin"))
    if incremental:
        model_name_local = OUTPUT_DIR

    tokenizer = AutoTokenizer.from_pretrained(model_name_local)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(model_name_local)
    if incremental:
        target_modules = ["attn.attention.q_proj", "attn.attention.k_proj", "attn.attention.v_proj",
                          "attn.attention.out_proj", "mlp.c_proj"]
        lora_config = LoraConfig(r=8, lora_alpha=32, target_modules=target_modules,
                                 lora_dropout=0.1, bias="none", task_type="CAUSAL_LM")
        model = get_peft_model(model, lora_config)

    # Tokenization
    def tokenize(example):
        text = example["prompt"] + example["completion"]
        encoding = tokenizer(text, padding="max_length", truncation=True, max_length=128)
        encoding["labels"] = encoding["input_ids"].copy()
        return encoding

    dataset = dataset.map(tokenize, remove_columns=dataset["train"].column_names)

    # Training
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=8,
        num_train_epochs=5,
        weight_decay=0.01,
        learning_rate=5e-5,
        warmup_steps=100,
        save_steps=500,
        save_total_limit=2,
        logging_dir=f"{OUTPUT_DIR}/logs",
        logging_steps=50,
        seed=42,
        dataloader_drop_last=True
    )

    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    trainer = Trainer(model=model, args=training_args, train_dataset=dataset["train"], data_collator=data_collator)
    trainer.train()

    # Save model
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    if USE_S3:
        os.remove(tmp_dataset.name)

if __name__ == "__main__":
    train_model()
