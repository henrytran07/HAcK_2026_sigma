from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from serial.tools import list_ports

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

PICO_VID = 0x2E8A


def find_pico():
    for port in list_ports.comports():
        if port.vid == PICO_VID:
            return {"connection": True, "port": port.device}
    return {"connection": False, "port": None}


@router.get("/live")
def live_page(request: Request):
    return templates.TemplateResponse(request=request, name="live.html", context=find_pico())


@router.get("/api/instrument")
def instrument_status():
    return find_pico()
