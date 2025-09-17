import os
import tempfile
import boto3
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, Trainer, TrainingArguments
from peft import LoraConfig, get_peft_model
from app.config import config

def train_model():
    # -------------------------
    # 1️⃣ Dataset
    # -------------------------
    if config.USE_S3:
        s3 = boto3.client("s3")
        tmp_dataset = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        s3.download_file(config.S3_BUCKET, config.DATASET_PATH_S3, tmp_dataset.name)
        dataset_path_local = tmp_dataset.name
        print(f"Dataset downloaded from S3 to {dataset_path_local}")
    else:
        dataset_path_local = config.DATASET_PATH_LOCAL
        print(f"Using local dataset: {dataset_path_local}")

    dataset = load_dataset("json", data_files=dataset_path_local)

    # -------------------------
    # 2️⃣ Detect pretrained local model
    # -------------------------
    incremental = False
    if os.path.isdir(config.OUTPUT_DIR) and os.path.exists(os.path.join(config.OUTPUT_DIR, "pytorch_model.bin")):
        print("✅ Pretrained local model found — incremental training with LoRA.")
        model_name_local = config.OUTPUT_DIR
        incremental = True
    else:
        print("⚠️ No pretrained model found — full fine-tuning.")
        model_name_local = config.BASE_MODEL

    # -------------------------
    # 3️⃣ Tokenizer and model
    # -------------------------
    tokenizer = AutoTokenizer.from_pretrained(model_name_local)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(model_name_local)

    # Apply LoRA only for incremental training
    if incremental:
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
        print("🔧 LoRA enabled for incremental training.")
    else:
        print("🔧 LoRA disabled — full fine-tuning.")

    # -------------------------
    # 4️⃣ Tokenization
    # -------------------------
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

    dataset = dataset.map(tokenize)

    # -------------------------
    # 5️⃣ Training
    # -------------------------
    training_args = TrainingArguments(
        output_dir=config.OUTPUT_DIR,
        per_device_train_batch_size=2,
        num_train_epochs=10 if incremental else 20,
        save_steps=200,
        save_total_limit=2,
        logging_dir=f"{config.OUTPUT_DIR}/logs",
        logging_steps=50
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"]
    )
    trainer.train()

    # -------------------------
    # 6️⃣ Save model locally
    # -------------------------
    model.save_pretrained(config.OUTPUT_DIR)
    tokenizer.save_pretrained(config.OUTPUT_DIR)

    # -------------------------
    # 7️⃣ Clean up temporary file
    # -------------------------
    if config.USE_S3:
        os.remove(tmp_dataset.name)
