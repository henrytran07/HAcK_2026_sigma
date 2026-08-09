# Copilot Instructions for HAcK_2026_sigma

- This repository has two main runtime surfaces:
  - `source/main.py` is the FastAPI web server entrypoint.
  - `circuit/code.py` is the CircuitPython Pico firmware that streams instrument telemetry over USB CDC.

- The web app is structured as a small FastAPI project with routers in `source/ticket.py` and `source/pico_connection.py`.
  - `source/main.py` mounts `/css` and `/images` as static directories and includes the two routers.
  - `source/pico_connection.py` provides live device status and renders `templates/live.html`.
  - `source/ticket.py` provides `/ticket` GET/POST behavior and in-memory seat reservation state.

- Key route behaviors:
  - `/` serves `templates/main.html`
  - `/ticket-master` serves `templates/ticketmaster.html`
  - `/ticket` uses `ticket.py` to render the seating UI and process form POSTs
  - `/live` renders the live instrument dashboard
  - `/api/instrument` returns JSON status for the connected Pico device

- Important implementation notes:
  - Seat state is ephemeral: `hack_2026 = BattleOfTheBuilds()` is stored in memory and resets each server restart.
  - `source/pico_connection.py` scans USB serial ports for VID `0x2E8A` and expects newline-delimited JSON frames.
  - The Pico firmware in `circuit/code.py` produces those JSON frames via `usb_cdc.data`.
  - The server uses `pyserial` to connect and keep an active snapshot of the latest frame.

- Templates are rendered with Jinja2 and rely on explicit context keys like `seat_labels`, `available`, `connection`, and `banner`.
  - The `ticket.html` page uses client-side JS to select a seat and submit `seat_label`.
  - The `live.html` page polls `/api/instrument` and updates the dashboard using the JSON payload.

- When changing code:
  - Keep server-side page flow in FastAPI router methods rather than introducing a new frontend framework.
  - Preserve the static asset mounting at `/css` and `/images`.
  - Avoid modifying `source/ticket.py` to add persistence unless a new storage layer is explicitly introduced.

- Run / development hints:
  - Start the app from the repository root with `python3 -m uvicorn source.main:app --reload --reload-dir source`.
  - From the `source/` folder, `uvicorn main:app --reload` should also work.
  - There is no existing `requirements.txt`; dependencies are implied by imports in `source/*.py`.

- Avoid generic fixes. Focus on this project’s actual flow: FastAPI routing + Jinja2 templates + Pico serial telemetry.
