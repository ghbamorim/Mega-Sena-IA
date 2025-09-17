from pydantic import BaseModel

class PreviewResponse(BaseModel):
    date: str
    numbers: list[int]
