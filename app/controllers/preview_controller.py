from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
from app.models.preview_model import PreviewResponse
from app.services.preview_service import gerar_previsao

router = APIRouter()

@router.get("/previsao", response_model=PreviewResponse)
def previsao(data: str = Query(..., description="Data no formato DD/MM/AAAA")):
    try:
        dt = datetime.strptime(data, "%d/%m/%Y")
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de data inválido. Use DD/MM/AAAA.")

    date_str = dt.strftime("%d %m %Y")
    numeros = gerar_previsao(date_str)
    return PreviewResponse(date=data, numbers=numeros)
