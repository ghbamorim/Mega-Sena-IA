import os
from fastapi import APIRouter, HTTPException
from app.models.preview_model import TrainResponse
from app.services.train_service import train_model
import threading

router = APIRouter()

def training_background():
    try:
        train_model()
    except Exception as e:
        print(f"Training error: {e}")

@router.post("/train", response_model=TrainResponse)
def start_training():
    thread = threading.Thread(target=training_background)
    thread.start()
    return TrainResponse(status="started", message="Training launched in background")
