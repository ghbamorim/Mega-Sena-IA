from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
from app.models.preview_model import PreviewResponse
from app.services.preview_service import generate_prediction

router = APIRouter()

@router.get("/preview", response_model=PreviewResponse)
def preview(date: str = Query(..., description="Date in format DD/MM/YYYY")):
    try:
        dt = datetime.strptime(date, "%d/%m/%Y")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use DD/MM/YYYY.")

    date_str = dt.strftime("%d %m %Y")
    numbers = generate_prediction(date_str)
    return PreviewResponse(date=date, numbers=numbers)
