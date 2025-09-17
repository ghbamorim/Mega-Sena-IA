from pydantic import BaseModel

class PreviewResponse(BaseModel):
    date: str
    numbers: list[int]

class TrainResponse(BaseModel):
    status: str
    message: str