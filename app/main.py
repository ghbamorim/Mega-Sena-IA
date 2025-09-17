from fastapi import FastAPI
from app.controllers import preview_controller, train_controller

app = FastAPI(title="Previsão de Números da Loteria")
app.include_router(preview_controller.router)
app.include_router(train_controller.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
