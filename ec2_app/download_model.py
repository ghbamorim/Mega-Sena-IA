#!/usr/bin/env python3
import os
from transformers import AutoTokenizer, AutoModelForCausalLM

BASE_MODEL = os.getenv("BASE_MODEL", "EleutherAI/gpt-neo-125M")
LOCAL_MODEL_DIR = os.getenv("LOCAL_MODEL_DIR", "./models/EleutherAI/gpt-neo-125M")

def prepare_model():
    if os.path.isdir(LOCAL_MODEL_DIR) and os.path.exists(os.path.join(LOCAL_MODEL_DIR, "config.json")):
        print(f"✅ Local model found in {LOCAL_MODEL_DIR}, skipping download.")
    else:
        print(f"⬇️ Downloading {BASE_MODEL} from Hugging Face...")
        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
        model = AutoModelForCausalLM.from_pretrained(BASE_MODEL)
        os.makedirs(LOCAL_MODEL_DIR, exist_ok=True)
        tokenizer.save_pretrained(LOCAL_MODEL_DIR)
        model.save_pretrained(LOCAL_MODEL_DIR)
        print(f"✅ Model saved to {LOCAL_MODEL_DIR}")

if __name__ == "__main__":
    prepare_model()
