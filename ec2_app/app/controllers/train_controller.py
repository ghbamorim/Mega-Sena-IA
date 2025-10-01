import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.models.preview_model import TrainResponse
from app.services.train_service import train_model

logger = logging.getLogger(__name__)
router = APIRouter()

training_status = {"status": "idle", "message": "No training started yet"}

def training_task():
    global training_status
    try:
        training_status = {"status": "running", "message": "Training in progress"}
        train_model()
        training_status = {"status": "completed", "message": "Training finished successfully"}
    except Exception as e:
        logger.error(f"❌ Training error: {e}")
        training_status = {"status": "failed", "message": str(e)}

@router.post("/train", response_model=TrainResponse)
def start_training(background_tasks: BackgroundTasks):
    """Start training in background"""
    if training_status["status"] == "running":
        raise HTTPException(status_code=409, detail="Training already in progress")
    background_tasks.add_task(training_task)
    return TrainResponse(status="started", message="Training launched in background")

@router.get("/train/status", response_model=TrainResponse)
def get_training_status():
    """Check last training job status"""
    return TrainResponse(**training_status)
