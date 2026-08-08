# Σ4 — Battle of the Builds

Site and firmware for the Σ4 instrument, built for UCLA HAcK 2026 (Battle of the Builds). The show runs at Mong Auditorium.

Two halves talk to each other over USB serial:

- **`circuit/`** — CircuitPython firmware on a Raspberry Pi Pico 2. Generates audio with `synthio`, outputs over I2S, and streams its state as newline-delimited JSON.
- **`source/`** — FastAPI server. Serves the band site, handles seat booking, and reads the instrument's serial feed to drive a live visualizer.

## Layout

```
.
├── source/
│   ├── main.py              app, static mounts, page routes
│   ├── ticket.py            seat booking router
│   └── pico_connection.py   serial reader + /live + /api/instrument
├── templates/
│   ├── main.html
│   ├── build.html
│   ├── ticket.html
│   ├── ticketmaster.html
│   └── live.html
├── css/
├── images/
└── circuit/
    ├── boot.py
    └── code.py
```

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

The slide pot lerps continuously between C4 (261.63 Hz) and C5 (523.25 Hz). Key 5 gates the note.

## Firmware setup

The board is a Pico 2W running **CircuitPython 10.2.1**. If it arrives with MicroPython on it, reflash first: hold BOOTSEL while plugging in, then drop the CircuitPython UF2 onto the RPI-RP2 drive.

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
| `GET /ticket` | Seat map |
| `POST /ticket` | Reserve a seat |
| `GET /ticket-master` | Ticketmaster page |

`/docs` lists every registered route, which is the fastest way to confirm a router actually loaded.

## Serial protocol

The firmware writes one JSON object per line to `usb_cdc.data` at roughly 20 Hz:

```
{"frequency":392.4,"amplitude":0.68,"playing":1,"keys":"5"}
```

`InstrumentLink` in `pico_connection.py` runs a background thread that finds the Pico by USB vendor ID `0x2E8A`, opens the port at 115200 baud, and reconnects on its own if the board is unplugged mid-set.

`/api/instrument` returns:

| Field | Meaning |
| --- | --- |
| `connection` | A Pico-shaped device is present on a port |
| `streaming` | Frames arrived within the last 0.5 s |
| `frequency` | Current pitch in Hz |
| `amplitude` | 0.0–1.0 from the volume pot |
| `playing` | Whether the note is gated on |
| `keys` | Comma-separated held keys |

`connection` and `streaming` are deliberately separate. A board sitting in bootloader mode, or one that has hung, still shows `connection: true` — the live page keys its status pill on `streaming` so a green light always means real data.

## Troubleshooting

**404 on a route that exists.** The router did not load. A syntax error anywhere in the module removes every route in it, and `--reload` can swallow the traceback for a file it has not loaded before. Run `python -c "import pico_connection"` from `source/` to see the error.

**A page renders but its Jinja tags show as literal text.** That route is returning `FileResponse` instead of `TemplateResponse`. Check `main.py` for a leftover route shadowing the router's version.

**Pill stays red with the board plugged in.** No frames are arriving. Stop the server so nothing holds the port, then:

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

- Only key 5 is mapped. The other eleven keys are wired and reported but do nothing.
- No sound effects implemented yet; the competition asks for three. `synthio.Note` supports `waveform` swaps and `synthio.LFO` on `bend` or `amplitude`.
- Mutating `note.frequency` on a held note glides rather than re-articulates, so intervals smear.