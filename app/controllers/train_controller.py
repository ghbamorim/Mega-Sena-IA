import os
from fastapi import APIRouter, HTTPException
from app.models.preview_model import TrainResponse
from app.services.train_service import treinar_modelo
import threading

router = APIRouter()

def treino_background():
    dataset_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dataset.json"))
    try:
        treinar_modelo(
            dataset_path=dataset_path,
            model_name="EleutherAI/gpt-neo-125M",
            output_dir="./finetuned_mega"
        )
    except Exception as e:
        print(f"Erro no treino: {e}")

@router.post("/train", response_model=TrainResponse)
def iniciar_treino():
    thread = threading.Thread(target=treino_background)
    thread.start()
    return TrainResponse(status="iniciado", message="Treinamento LoRA disparado em background")
