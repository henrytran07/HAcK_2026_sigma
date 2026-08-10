# Σ4 — Battle of the Builds

Site and firmware for the Σ4 instrument, built for UCLA HAcK 2026 (Battle of the Builds). The show runs at Mong Auditorium.

Two halves talk to each other over USB serial:

- **`circuit/`** — CircuitPython firmware on a Raspberry Pi Pico 2 W. Generates audio with `synthio`, outputs over I2S, and streams its state as newline-delimited JSON. The KiCad schematic for the instrument lives in `circuit/HAcK2026_instrument_kicad/`.
- **`source/`** — FastAPI server. Serves the band site, handles seat booking, reads the instrument's serial feed to drive a live visualizer, and computes per-member contribution credit from git history for the build page.

## Layout

```
.
├── source/
│   ├── main.py              app, static mounts, page routes
│   ├── ticket.py            seat booking router
│   ├── pico_connection.py   serial reader + /live + /api/instrument
│   └── contributions.py     git-blame credit breakdown + /api/contributions
├── templates/
│   ├── main.html
│   ├── build.html
│   ├── contributions-snippet.html
│   ├── ticket.html
│   ├── ticketmaster.html
│   └── live.html
├── css/
├── images/
├── audio/                   recordings served at /audio
├── model/                   CAD — FinalCAD.stl, BaoFinal.dxf, drawing PDF
└── circuit/
    ├── boot.py
    ├── code.py
    └── HAcK2026_instrument_kicad/
```

`css/`, `images/`, `model/`, `circuit/`, and `audio/` are all mounted as static so the build page can link straight to the schematic, CAD files, and recordings.

## Hardware

| Part | Pin |
| --- | --- |
| I2S bit clock | GP12 |
| I2S word select | GP13 |
| I2S data | GP11 |
| Keypad rows | GP16–GP19 |
| Keypad columns | GP20–GP22 |
| Slide pot (pitch) | A1 |
| Volume pot (amplitude) | A2 |

## Controls

| Control | Action |
| --- | --- |
| Key 4 | Gate the note on/off |
| Key 1 | Next waveform |
| Key 7 | Previous waveform |
| Slide pot | Pitch, lerped continuously C4 (261.63 Hz) → C5 (523.25 Hz) |
| Volume pot | Amplitude 0.0–1.0 |

Four waveforms, in order: **saw** (default), **square**, **sine**, **noise**. The cycle clamps at both ends rather than wrapping.

## Firmware setup

The board is a Pico 2 W running **CircuitPython 10.2.1**. If it arrives with MicroPython on it, reflash first: hold BOOTSEL while plugging in, then drop the CircuitPython UF2 onto the RP2350 drive.

Copy onto the root of the CIRCUITPY drive:

- `boot.py` — enables the second USB serial endpoint
- `code.py` — the instrument firmware
- `lib/adafruit_matrixkeypad.mpy` — from the **10.x** Adafruit bundle, not 9.x

`boot.py` only runs at power-up. After copying it, unplug and replug the board — saving a file triggers a soft reload that re-runs `code.py` but not `boot.py`. When it has taken effect the board enumerates **two** serial ports instead of one.

## Server setup

```
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn jinja2 pyserial python-multipart
```

`git` must also be on the PATH — the contributions endpoint shells out to it.

## Running

```
cd source
lsof -ti :8000 | xargs kill -9
uvicorn main:app --reload
```

The kill line clears a stale server still holding port 8000. It is safe to skip when the port is free — `xargs` with no input does nothing.

## Routes

| Route | Purpose |
| --- | --- |
| `GET /` | Band page |
| `GET /build` | The build |
| `GET /live` | Live visualizer |
| `GET /api/instrument` | Instrument state as JSON |
| `GET /api/contributions` | Per-author credit breakdown as JSON |
| `GET /ticket` | Seat map |
| `POST /ticket` | Reserve a seat |
| `GET /ticket-master` | Ticketmaster page |

`/docs` lists every registered route, which is the fastest way to confirm a router actually loaded.

## Serial protocol

The firmware writes one JSON object per line to `usb_cdc.data` at roughly 20 Hz:

```
{"frequency":392.4,"amplitude":0.680,"playing":1,"keys":"4","waveform":"saw"}
```

`InstrumentLink` in `pico_connection.py` runs a background thread that finds the board by USB vendor ID (`0x2E8A` or `0x239A`), probes each candidate port until one produces valid frames, opens it at 115200 baud, and reconnects on its own if the board is unplugged mid-set.

`/api/instrument` returns:

| Field | Meaning |
| --- | --- |
| `connection` | A Pico-shaped device is present on a port |
| `port` | Which port it was found on |
| `frequency` | Current pitch in Hz |
| `amplitude` | 0.0–1.0 from the volume pot |
| `playing` | Whether the note is gated on |
| `keys` | Comma-separated held keys |
| `waveform` | Active waveform name |

Frame fields zero out when no frame has arrived within the last second. That split is deliberate: a board sitting in bootloader mode, or one that has hung, still shows `connection: true` — but its frequency, amplitude, and waveform all read empty, so the live page never animates on stale data.

## Troubleshooting

**404 on a route that exists.** The router did not load. A syntax error anywhere in the module removes every route in it, and `--reload` can swallow the traceback for a file it has not loaded before. Run `python -c "import pico_connection"` from `source/` to see the error.

**A page renders but its Jinja tags show as literal text.** That route is returning `FileResponse` instead of `TemplateResponse`. Check `main.py` for a leftover route shadowing the router's version.

**Live page shows zeros with the board plugged in.** No frames are arriving. Stop the server so nothing holds the port, then:

```
python -m serial.tools.miniterm <port> 115200
```

JSON lines should scroll past. If not, `boot.py` is missing or the board needs a hard reset.

**Listing what is actually connected:**

```python
from serial.tools import list_ports

for p in list_ports.comports():
    print(p.device, hex(p.vid) if p.vid else None, hex(p.pid) if p.pid else None, p.interface)
```

## Known gaps

- Only keys 1, 4, and 7 are mapped. The other nine keys are wired and reported but do nothing.
- Seat bookings live in memory — restarting the server frees every seat.
- The contributions cache means credit for a fresh commit can lag by up to five minutes.