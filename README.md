# HAcK 2026 — Σ4 Electronic Instrument

An electronic instrument built for UCLA HAcK 2026 (Battle of the Builds), plus a live web dashboard. A Raspberry Pi **Pico 2** running CircuitPython reads a 4×3 matrix keypad and two potentiometers, synthesizes audio over I2S, and streams telemetry (frequency, amplitude, playing state, pressed keys) to a FastAPI site over USB serial.

## Repository layout

```
circuit/            CircuitPython firmware for the Pico 2
  boot.py           enables the second USB CDC (data) serial port
  code.py           synth + keypad + pots + JSON telemetry loop
source/             FastAPI web server
  main.py           app entrypoint, static mounts, routers
  pico_connection.py  serial reader thread + /live + /api/instrument
  ticket.py         seat reservation pages
templates/          Jinja2 / HTML pages (live.html is the dashboard)
css/                stylesheets
images/             static assets
```

## Hardware

- Raspberry Pi **Pico 2** (RP2350)
- 4×3 matrix keypad — rows GP16–GP19, columns GP20–GP22
- Slide potentiometer (pitch) on A1, rotary potentiometer (volume) on A2
- I2S audio out — BCLK GP12, LRCLK/WS GP# HAcK 2026 — Σ4 Electronic Instrument

An electronic instrument built for UCLA HAcK 2026 (Battle of the Builds), plus a live web dashboard. A Raspberry Pi **Pico 2** running CircuitPython reads a 4×3 matrix keypad and two potentiometers, synthesizes audio over I2S, and streams telemetry (frequency, amplitude, playing state, pressed keys) to a FastAPI site over USB serial.

## Repository layout

```
circuit/            CircuitPython firmware for the Pico 2
  boot.py           enables the second USB CDC (data) serial port
  code.py           synth + keypad + pots + JSON telemetry loop
source/             FastAPI web server
  main.py           app entrypoint, static mounts, routers
  pico_connection.py  serial reader thread + /live + /api/instrument
  ticket.py         seat reservation pages
templates/          Jinja2 / HTML pages (live.html is the dashboard)
css/                stylesheets
images/             static assets
```

## Hardware

- Raspberry Pi **Pico 2** (RP2350)
- 4×3 matrix keypad — rows GP16–GP19, columns GP20–GP22
- Slide potentiometer (pitch) on A1, rotary potentiometer (volume) on A2
- I2S audio out — BCLK GP12, LRCLK/WS GP13, DATA GP11
- Key **5** gates the note; pitch sweeps C4 (261.6 Hz) to C5 (523.3 Hz)

The firmware runs fine on a bare board with nothing wired — the pots just read floating-pin noise and no key can be pressed. Useful for testing the software stack alone.

## 1. Flash CircuitPython on the Pico 2

The board must run **CircuitPython** (not MicroPython — `synthio` and `usb_cdc` don't exist there). If plugging the board in gives you one serial port and no `CIRCUITPY` drive, it's running MicroPython and needs reflashing.

1. Download the CircuitPython UF2 for **Raspberry Pi Pico 2** from
   https://circuitpython.org/board/raspberry_pi_pico2/ (latest stable, e.g. 10.2.x).
2. Unplug the board. Hold the **BOOTSEL** button, plug the USB cable in while
   holding, release after ~2 seconds.
3. A drive named **`RP2350`** mounts (that's the Pico 2 bootloader name — the
   original Pico mounts as `RPI-RP2`).
4. Drag the `.uf2` onto the `RP2350` drive (Finder is easiest — see the macOS
   permissions note below). The drive ejects itself; the "disk not ejected
   properly" warning is normal.
5. After ~10 seconds a drive named **`CIRCUITPY`** appears. Flashing is done.

Reflashing wipes the drive, so redo steps 2 and 3 below after any reflash.

## 2. Install the keypad library

`code.py` imports `adafruit_matrixkeypad`, which is not built into the firmware.

1. Download the Adafruit CircuitPython **Bundle** from
   https://circuitpython.org/libraries — the bundle major version must match
   the firmware (10.x bundle for CircuitPython 10.x; a mismatched `.mpy`
   throws a version error).
2. Unzip it and copy one file onto the board:

   ```
   cp ~/Downloads/adafruit-circuitpython-bundle-10.x-mpy-*/lib/adafruit_matrixkeypad.mpy /Volumes/CIRCUITPY/lib/
   ```

Everything else the firmware imports (`synthio`, `audiobusio`, `analogio`,
`usb_cdc`, `board`, `digitalio`) is built in.

## 3. Copy the firmware

```
cp circuit/boot.py circuit/code.py /Volumes/CIRCUITPY/
```

Both files go in the drive root, next to `lib/`. There is no compile step —
CircuitPython runs `code.py` directly and auto-reloads whenever the file is
saved.

Then do a **hard reset**: eject `CIRCUITPY`, unplug, wait 2 seconds, replug
(or tap the RESET button). `boot.py` only runs on a hard reset — a soft
reload (Ctrl+D in the REPL) will not enable the second serial port.

## 4. Verify the board

```
ls /dev/cu.usbmodem*
```

You should see **two** ports (macOS; on Linux they appear as `/dev/ttyACM*`):

- the lower-numbered one is the **console** (REPL, tracebacks)
- the higher-numbered one is the **data** port streaming JSON frames ~20×/sec:

  ```
  {"frequency":331.4,"amplitude":0.481,"playing":0,"keys":""}
  ```

To watch either port: `screen /dev/cu.usbmodemNNN 115200`. Exit with
**Ctrl+A, K, y**. Only one serial port means `boot.py` didn't run — check it's
on the drive and hard-reset again. A traceback on the console usually means
the library from step 2 is missing or the wrong bundle version.

## 5. Run the web server

Python dependencies:

```
pip install fastapi uvicorn jinja2 pyserial python-multipart
```

(`python-multipart` is required — the ticket page uses form posts and the app
won't boot without it.)

Start the server **from the `source/` directory** (the imports are flat):

```
cd source
uvicorn main:app --reload
```

Or from the repo root: `uvicorn main:app --reload --app-dir source`.

Open http://127.0.0.1:8000/live — the connection pill goes green, and with
the full hardware attached the oscilloscope, frequency/note readout, volume
meter, and keypad grid all track the instrument in real time.
`/api/instrument` returns the latest JSON frame; the page polls it every
100 ms. The server-side reader (`InstrumentLink`) scans for VID `0x2E8A`,
probes both CDC ports, locks onto the one producing valid JSON, and
reconnects automatically if the board is unplugged.

## Gotchas (learned the hard way)

**Only one program can hold the data port.** If `screen` is attached to the
data port, the server reads nothing and the dashboard shows zeros — and vice
versa. Before starting uvicorn:

```
screen -ls                      # should say "No Sockets found"
lsof /dev/cu.usbmodem103        # should print nothing
```

Closing a terminal tab while `screen` is running leaves a *detached* session
that still owns the port. Kill leftovers with `screen -X -S <id> quit` (IDs
from `screen -ls`) or `pkill -9 screen`. Always exit screen with Ctrl+A, K, y
instead of closing the window.

**macOS "Operation not permitted" when copying to the board.** Terminal needs
permission to write removable volumes: System Settings → Privacy & Security →
Full Disk Access → enable Terminal, then fully quit (Cmd+Q) and reopen
Terminal — the setting only applies on relaunch. Dragging files in Finder
always works as a fallback.

**Board keeps mounting as `RP2350`.** That's bootloader mode — BOOTSEL is
being pressed during power-up. It sits next to the USB connector, so keep
fingers clear when plugging in, and use the RESET button instead of
replugging when possible.

**`Address already in use` from uvicorn.** A previous server is still alive —
often one suspended with Ctrl+Z (which pauses but doesn't kill). Bring it back
with `fg` and Ctrl+C it, or `lsof -ti :8000 | xargs kill -9`. Use Ctrl+C, not
Ctrl+Z, to stop the server.

**`Error loading ASGI app. Could not import module "main"`.** You ran uvicorn
from the repo root without `--app-dir source`. Run it from `source/`.

## Quick test checklist

1. `ls /dev/cu.usbmodem*` → two ports
2. Hold key 5 → tone plays; slide pot bends pitch; volume pot works
3. `screen` the data port → JSON values track the knobs (exit before step 4!)
4. `uvicorn main:app --reload` from `source/`, open `/live` → green pill,
   moving scope
5. Unplug the board mid-page → pill flips to disconnected within ~1 s and the
   scope flatlines; replug → recovers on its own13, DATA GP11
- Key **5** gates the note; pitch sweeps C4 (261.6 Hz) to C5 (523.3 Hz)

The firmware runs fine on a bare board with nothing wired — the pots just read floating-pin noise and no key can be pressed. Useful for testing the software stack alone.

## 1. Flash CircuitPython on the Pico 2

The board must run **CircuitPython** (not MicroPython — `synthio` and `usb_cdc` don't exist there). If plugging the board in gives you one serial port and no `CIRCUITPY` drive, it's running MicroPython and needs reflashing.

1. Download the CircuitPython UF2 for **Raspberry Pi Pico 2** from
   https://circuitpython.org/board/raspberry_pi_pico2/ (latest stable, e.g. 10.2.x).
2. Unplug the board. Hold the **BOOTSEL** button, plug the USB cable in while
   holding, release after ~2 seconds.
3. A drive named **`RP2350`** mounts (that's the Pico 2 bootloader name — the
   original Pico mounts as `RPI-RP2`).
4. Drag the `.uf2` onto the `RP2350` drive (Finder is easiest — see the macOS
   permissions note below). The drive ejects itself; the "disk not ejected
   properly" warning is normal.
5. After ~10 seconds a drive named **`CIRCUITPY`** appears. Flashing is done.

Reflashing wipes the drive, so redo steps 2 and 3 below after any reflash.

## 2. Install the keypad library

`code.py` imports `adafruit_matrixkeypad`, which is not built into the firmware.

1. Download the Adafruit CircuitPython **Bundle** from
   https://circuitpython.org/libraries — the bundle major version must match
   the firmware (10.x bundle for CircuitPython 10.x; a mismatched `.mpy`
   throws a version error).
2. Unzip it and copy one file onto the board:

   ```
   cp ~/Downloads/adafruit-circuitpython-bundle-10.x-mpy-*/lib/adafruit_matrixkeypad.mpy /Volumes/CIRCUITPY/lib/
   ```

Everything else the firmware imports (`synthio`, `audiobusio`, `analogio`,
`usb_cdc`, `board`, `digitalio`) is built in.

## 3. Copy the firmware

```
cp circuit/boot.py circuit/code.py /Volumes/CIRCUITPY/
```

Both files go in the drive root, next to `lib/`. There is no compile step —
CircuitPython runs `code.py` directly and auto-reloads whenever the file is
saved.

Then do a **hard reset**: eject `CIRCUITPY`, unplug, wait 2 seconds, replug
(or tap the RESET button). `boot.py` only runs on a hard reset — a soft
reload (Ctrl+D in the REPL) will not enable the second serial port.

## 4. Verify the board

```
ls /dev/cu.usbmodem*
```

You should see **two** ports (macOS; on Linux they appear as `/dev/ttyACM*`):

- the lower-numbered one is the **console** (REPL, tracebacks)
- the higher-numbered one is the **data** port streaming JSON frames ~20×/sec:

  ```
  {"frequency":331.4,"amplitude":0.481,"playing":0,"keys":""}
  ```

To watch either port: `screen /dev/cu.usbmodemNNN 115200`. Exit with
**Ctrl+A, K, y**. Only one serial port means `boot.py` didn't run — check it's
on the drive and hard-reset again. A traceback on the console usually means
the library from step 2 is missing or the wrong bundle version.

## 5. Run the web server

Python dependencies:

```
pip install fastapi uvicorn jinja2 pyserial python-multipart
```

(`python-multipart` is required — the ticket page uses form posts and the app
won't boot without it.)

Start the server **from the `source/` directory** (the imports are flat):

```
cd source
lsof -i :8000 | awk 'NR>1 {print $2}' | xargs kill -9\
uvicorn main:app --reload
```

Or from the repo root: `uvicorn main:app --reload --app-dir source`.

Open http://127.0.0.1:8000/live — the connection pill goes green, and with
the full hardware attached the oscilloscope, frequency/note readout, volume
meter, and keypad grid all track the instrument in real time.
`/api/instrument` returns the latest JSON frame; the page polls it every
100 ms. The server-side reader (`InstrumentLink`) scans for VID `0x2E8A`,
probes both CDC ports, locks onto the one producing valid JSON, and
reconnects automatically if the board is unplugged.

## Gotchas (learned the hard way)

**Only one program can hold the data port.** If `screen` is attached to the
data port, the server reads nothing and the dashboard shows zeros — and vice
versa. Before starting uvicorn:

```
screen -ls                      # should say "No Sockets found"
lsof /dev/cu.usbmodem103        # should print nothing
```

Closing a terminal tab while `screen` is running leaves a *detached* session
that still owns the port. Kill leftovers with `screen -X -S <id> quit` (IDs
from `screen -ls`) or `pkill -9 screen`. Always exit screen with Ctrl+A, K, y
instead of closing the window.

**macOS "Operation not permitted" when copying to the board.** Terminal needs
permission to write removable volumes: System Settings → Privacy & Security →
Full Disk Access → enable Terminal, then fully quit (Cmd+Q) and reopen
Terminal — the setting only applies on relaunch. Dragging files in Finder
always works as a fallback.

**Board keeps mounting as `RP2350`.** That's bootloader mode — BOOTSEL is
being pressed during power-up. It sits next to the USB connector, so keep
fingers clear when plugging in, and use the RESET button instead of
replugging when possible.

**`Address already in use` from uvicorn.** A previous server is still alive —
often one suspended with Ctrl+Z (which pauses but doesn't kill). Bring it back
with `fg` and Ctrl+C it, or `lsof -ti :8000 | xargs kill -9`. Use Ctrl+C, not
Ctrl+Z, to stop the server.

**`Error loading ASGI app. Could not import module "main"`.** You ran uvicorn
from the repo root without `--app-dir source`. Run it from `source/`.

## Quick test checklist

1. `ls /dev/cu.usbmodem*` → two ports
2. Hold key 5 → tone plays; slide pot bends pitch; volume pot works
3. `screen` the data port → JSON values track the knobs (exit before step 4!)
4. `uvicorn main:app --reload` from `source/`, open `/live` → green pill,
   moving scope
5. Unplug the board mid-page → pill flips to disconnected within ~1 s and the
   scope flatlines; replug → recovers on its own
=======
# HAcK_2026_sigma
>>>>>>> 4dc5bf98465486dbacf0ee2a5706e6996e7e47ba
