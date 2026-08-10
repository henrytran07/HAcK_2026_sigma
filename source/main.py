from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ticket import router as ticket_router
from pico_connection import router as pico_router
from contributions import router as contributions_router

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / "templates"

app = FastAPI()

app.mount("/css", StaticFiles(directory=BASE_DIR / "css"), name="css")
app.mount("/images", StaticFiles(directory=BASE_DIR / "images"), name="images")
app.mount("/model", StaticFiles(directory=BASE_DIR / "model"), name="model")
app.mount("/circuit", StaticFiles(directory=BASE_DIR / "circuit"), name="circuit")
app.mount("/audio", StaticFiles(directory=BASE_DIR / "audio"), name="audio")
app.include_router(ticket_router)
app.include_router(pico_router)
app.include_router(contributions_router)

@app.get("/")
def main():
    return FileResponse(TEMPLATE_DIR / "main.html")


@app.get("/ticket-master")
def ticketmaster():
    return FileResponse(TEMPLATE_DIR / "ticketmaster.html")

@app.get("/favicon.ico")
def favicon():
    return FileResponse(BASE_DIR / "images" / "ucla.png")

@app.get("/build")
def build(): 
    return FileResponse(TEMPLATE_DIR/"build.html")