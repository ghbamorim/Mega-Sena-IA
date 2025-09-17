from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, Trainer, TrainingArguments
from peft import LoraConfig, get_peft_model

def treinar_modelo(dataset_path: str, model_name: str, output_dir: str):    
    dataset = load_dataset("json", data_files=dataset_path)    
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    
    model = AutoModelForCausalLM.from_pretrained(model_name)
    
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
    
    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=2,
        num_train_epochs=50,
        save_steps=200,
        save_total_limit=2,
        logging_dir=f"{output_dir}/logs",
        logging_steps=50
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"]
    )
    trainer.train()

    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
