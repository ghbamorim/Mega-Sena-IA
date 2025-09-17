import os
from transformers import AutoTokenizer, AutoModelForCausalLM

# Caminho absoluto do modelo
model_path = os.path.abspath("./finetuned_mega")

# Inicializar variáveis como None
tokenizer = None
model = None

# Função para carregar o modelo se existir
def carregar_modelo():
    global tokenizer, model
    if os.path.exists(model_path) and os.path.isdir(model_path):
        try:
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            model = AutoModelForCausalLM.from_pretrained(model_path, device_map="auto")
            print(f"✅ Modelo carregado de {model_path}")
        except Exception as e:
            print(f"❌ Erro ao carregar modelo: {e}")
            tokenizer = None
            model = None
    else:
        print(f"⚠️ Modelo não encontrado em {model_path}, execute o fine-tuning primeiro.")

# Carregar modelo ao iniciar o serviço
carregar_modelo()

# Função de previsão
def gerar_previsao(date_str: str) -> list[int]:
    if tokenizer is None or model is None:
        raise RuntimeError("Modelo ainda não carregado. Execute o fine-tuning primeiro.")

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
