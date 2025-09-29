import os
from transformers import AutoTokenizer, AutoModelForCausalLM

# Local model path (same as OUTPUT_DIR used during training)
OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "./finetuned_mega")
model_path = os.path.abspath(OUTPUT_DIR)

# Initialize variables as None
tokenizer = None
model = None

def load_model():
    """
    Loads the model saved in OUTPUT_DIR if it exists.
    """
    global tokenizer, model
    
    if os.path.isdir(model_path) and (
        os.path.exists(os.path.join(model_path, "model.safetensors")) or
        os.path.exists(os.path.join(model_path, "config.json"))
    ):
        try:
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            model = AutoModelForCausalLM.from_pretrained(model_path, device_map="auto")
            print(f"✅ Model loaded from {model_path}")
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            tokenizer = None
            model = None
    else:
        print(f"⚠️ No model found in {model_path}. Run the first fine-tuning before generating predictions.")

# Load model at service startup
load_model()

def generate_prediction(date_str: str) -> list[int]:
    """
    Generates number predictions from a given date.
    """
    if tokenizer is None or model is None:
        raise RuntimeError("Model not loaded yet. Run fine-tuning first.")

    prompt = f"Digits: {date_str} -> Numbers:"
    input_ids = tokenizer(prompt, return_tensors="pt").input_ids

    output_ids = model.generate(
        input_ids,
        max_new_tokens=40,
        do_sample=False,
        temperature=0.0,
        top_p=0.9,
        eos_token_id=tokenizer.eos_token_id,
        pad_token_id=tokenizer.eos_token_id
    )[0]

    output_text = tokenizer.decode(output_ids, skip_special_tokens=True)
    numbers_str = output_text.split("Numbers")[-1]

    try:
        numbers = [int(x) for x in numbers_str.split() if x.isdigit()]
    except ValueError:
        numbers = []

    return numbers[:6]
