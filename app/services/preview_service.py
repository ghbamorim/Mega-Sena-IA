from transformers import AutoTokenizer, AutoModelForCausalLM

model_name = "./finetuned_mega"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name, device_map="auto")

def gerar_previsao(date_str: str) -> list[int]:
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
