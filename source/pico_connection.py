import json
import threading
import time
from pathlib import Path

import serial
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from serial.tools import list_ports

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

PICO_VIDS = {0x2E8A, 0x239A}
BAUD = 115200
STALE_AFTER = 1.0
RESCAN_DELAY = 0.5

DEFAULT_FRAME = {"frequency": 0.0, "amplitude": 0.0, "playing": 0, "keys": "", "waveform": ""}

def find_pico():
    for port in list_ports.comports():
        if port.vid in PICO_VIDS:
            return {"connection": True, "port": port.device}
    return {"connection": False, "port": None}

class InstrumentLink:
    def __init__(self):
        self._lock = threading.Lock()
        self._frame = dict(DEFAULT_FRAME)
        self._last_frame_at = 0.0
        self._port_name = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _candidate_ports(self):
        ports = sorted(p.device for p in list_ports.comports() if p.vid in PICO_VIDS)
        return list(reversed(ports))

    def _try_port(self, device):
        link = serial.Serial(device, BAUD, timeout=0.2)
        try:
            link.reset_input_buffer()
            for _ in range(8):
                line = link.readline()
                if not line:
                    continue
                try:
                    frame = json.loads(line.decode("utf-8", "ignore"))
                except (ValueError, UnicodeDecodeError):
                    continue
                if isinstance(frame, dict) and "frequency" in frame:
                    self._store(frame, device)
                    return link
            link.close()
        except (OSError, serial.SerialException):
            try:
                link.close()
            except Exception:
                pass
        return None

    def _store(self, frame, device):
        with self._lock:
            for key in DEFAULT_FRAME:
                if key in frame:
                    self._frame[key] = frame[key]
            self._last_frame_at = time.monotonic()
            self._port_name = device

    def _read_loop(self, link, device):
        while True:
            line = link.readline()
            if not line:
                if time.monotonic() - self._last_frame_at > STALE_AFTER * 3:
                    raise serial.SerialException("no data")
                continue
            try:
                frame = json.loads(line.decode("utf-8", "ignore"))
            except (ValueError, UnicodeDecodeError):
                continue
            if isinstance(frame, dict):
                self._store(frame, device)

    def _run(self):
        while True:
            link = None
            for device in self._candidate_ports():
                link = self._try_port(device)
                if link:
                    break
            if link is None:
                with self._lock:
                    self._port_name = None
                time.sleep(RESCAN_DELAY)
                continue
            try:
                self._read_loop(link, link.port)
            except (OSError, serial.SerialException):
                pass
            finally:
                try:
                    link.close()
                except Exception:
                    pass
            with self._lock:
                self._port_name = None
            time.sleep(RESCAN_DELAY)

    def snapshot(self):
        with self._lock:
            fresh = time.monotonic() - self._last_frame_at < STALE_AFTER
            connected = self._port_name is not None and fresh
            out = {"connection": connected, "port": self._port_name}
            out.update(self._frame if connected else DEFAULT_FRAME)
        return out


instrument = InstrumentLink()


@router.get("/live")
def live_page(request: Request):
    return templates.TemplateResponse(request=request, name="live.html", context=instrument.snapshot())


@router.get("/api/instrument")
def instrument_status():
    status = find_pico()
    data = instrument.snapshot()
    data["connection"] = status["connection"]
    data["port"] = status["port"]
    return data
