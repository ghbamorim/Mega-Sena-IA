import os
from dotenv import load_dotenv
from fastapi import FastAPI
from threading import Thread

# Load variables from .env
load_dotenv()

from app.controllers import preview_controller, train_controller
from app.workers.train_worker import start_worker  # Just import the function, without loops

app = FastAPI(title="Lottery Numbers Prediction")

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Include API routers
app.include_router(preview_controller.router)
app.include_router(train_controller.router)

# Start worker in a separate thread
worker_thread = Thread(target=start_worker, daemon=True)
worker_thread.start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
