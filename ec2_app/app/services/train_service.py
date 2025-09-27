import os
import tempfile
import boto3
import json
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, Trainer, TrainingArguments
from peft import LoraConfig, get_peft_model

LOCALSTACK_URL = os.getenv("LOCALSTACK_URL_CONTAINER", "http://localstack:4566")
REGION = os.getenv("REGION", "us-east-1")
USE_S3 = os.getenv("USE_S3", "False").lower() == "true"
S3_BUCKET = os.getenv("S3_BUCKET", "")
DATASET_PATH_S3: str = os.getenv("DATASET_PATH_S3", "")
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
    print("🔹 Starting training process...")

    # -------------------------
    # 0️⃣ Prepare local model
    # -------------------------
    prepare_model()
    model_name_local = LOCAL_MODEL_PATH

    # -------------------------
    # 1️⃣ Dataset
    # -------------------------
    print("📦 Preparing dataset...")
    if USE_S3:
        try:
            s3 = boto3.client(
                "s3",
                endpoint_url=LOCALSTACK_URL,
                region_name=REGION
            )

            response = s3.get_object(Bucket=BUCKET, Key=DATASET_FILE)
            dataset = json.loads(response["Body"].read())

            tmp_dataset = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
            with open(tmp_dataset.name, "w", encoding="utf-8") as f:
                json.dump(dataset, f, ensure_ascii=False, indent=2)

            dataset_path_local = tmp_dataset.name
            print(f"✅ Dataset downloaded to {dataset_path_local}")
        except Exception as e:
            print(f"❌ Error downloading dataset from S3: {e}")
            raise
    else:
        dataset_path_local = DATASET_PATH_LOCAL
        print(f"Using local dataset: {dataset_path_local}")

    try:
        dataset = load_dataset("json", data_files=dataset_path_local)
        print(f"✅ Dataset loaded successfully. Keys: {list(dataset.keys())}")
    except Exception as e:
        print(f"❌ Error loading dataset: {e}")
        raise

    # -------------------------
    # 2️⃣ Detect pretrained local model for incremental training
    # -------------------------
    incremental = False
    if os.path.isdir(OUTPUT_DIR) and os.path.exists(os.path.join(OUTPUT_DIR, "pytorch_model.bin")):
        print("✅ Pretrained local model found — incremental training with LoRA.")
        model_name_local = OUTPUT_DIR
        incremental = True

    # -------------------------
    # 3️⃣ Tokenizer and model
    # -------------------------
    print(f"🔧 Loading tokenizer from {model_name_local}")
    tokenizer = AutoTokenizer.from_pretrained(model_name_local)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        print("🔹 pad_token set to eos_token")

    print(f"🔧 Loading model from {model_name_local}")
    model = AutoModelForCausalLM.from_pretrained(model_name_local)

    if incremental:
        print("🔧 Applying LoRA for incremental training...")
        target_modules = [
            "attn.attention.q_proj",
            "attn.attention.k_proj",
            "attn.attention.v_proj",
            "attn.attention.out_proj",
            "mlp.c_proj"
        ]
        lora_config = LoraConfig(
            r=8,
            lora_alpha=32,
            target_modules=target_modules,
            lora_dropout=0.1,
            bias="none",
            task_type="CAUSAL_LM"
        )
        model = get_peft_model(model, lora_config)
        print("✅ LoRA enabled for incremental training.")
    else:
        print("🔹 LoRA disabled — full fine-tuning.")

    # -------------------------
    # 4️⃣ Tokenization
    # -------------------------
    print("📝 Tokenizing dataset...")
    def tokenize(example):
        text = example["prompt"] + example["completion"]
        encoding = tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=64
        )
        encoding["labels"] = encoding["input_ids"].copy()
        return encoding

    try:
        dataset = dataset.map(tokenize)
        print("✅ Dataset tokenized successfully.")
    except Exception as e:
        print(f"❌ Error during tokenization: {e}")
        raise

    # -------------------------
    # 5️⃣ Training
    # -------------------------
    print("🏋️ Starting training...")
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=2,
        num_train_epochs=10 if incremental else 20,
        save_steps=200,
        save_total_limit=2,
        logging_dir=f"{OUTPUT_DIR}/logs",
        logging_steps=50
    )

    try:
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=dataset["train"]
        )
        trainer.train()
        print("✅ Training completed.")
    except Exception as e:
        print(f"❌ Error during training: {e}")
        raise

    # -------------------------
    # 6️⃣ Save model locally
    # -------------------------
    print(f"💾 Saving model to {OUTPUT_DIR}...")
    try:
        model.save_pretrained(OUTPUT_DIR)
        tokenizer.save_pretrained(OUTPUT_DIR)
        print("✅ Model and tokenizer saved successfully.")
    except Exception as e:
        print(f"❌ Error saving model/tokenizer: {e}")
        raise

    # -------------------------
    # 7️⃣ Clean up temporary file
    # -------------------------
    if USE_S3:
        try:
            os.remove(tmp_dataset.name)
            print(f"🗑 Temporary file {tmp_dataset.name} removed.")
        except Exception as e:
            print(f"⚠️ Error removing temporary file: {e}")

    print("🎉 Training process finished!")

if __name__ == "__main__":
    train_model()
