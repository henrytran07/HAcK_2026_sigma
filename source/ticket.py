from pathlib import Path

from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates


class BattleOfTheBuilds:
    def __init__(self, rows="ABCDE", seats_per_row=10):
        self.seat_labels = [
            [letter + str(i) for i in range(1, seats_per_row + 1)]
            for letter in rows
        ]
        self.seat_available = {
            seat: True
            for row in self.seat_labels
            for seat in row
        }

    @property
    def num_seats(self):
        return len(self.seat_available)

    @property
    def seats_left(self):
        return sum(self.seat_available.values())

    def is_available(self, seat_label):
        if seat_label not in self.seat_available:
            return {"transaction": False, "code": "notfound", "message": "Seat not found."}
        if self.seat_available[seat_label]:
            return {"transaction": True, "code": "ok", "message": "Seat is available."}
        return {"transaction": False, "code": "taken", "message": "Seat is already taken."}

    def reserve_seat(self, seat_label):
        result = self.is_available(seat_label)
        if not result["transaction"]:
            return result
        self.seat_available[seat_label] = False
        return {"transaction": True, "code": "ok", "message": "Seat purchased successfully."}


BANNERS = {
    "ok": "Ticket confirmed for seat {seat}. See you at Mong Auditorium on Aug 9.",
    "taken": "Seat {seat} was claimed a moment ago. Pick another one.",
    "notfound": "That seat isn't in this auditorium. Pick one from the map.",
}

hack_2026 = BattleOfTheBuilds()
router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@router.get("/ticket")
def ticket_page(request: Request, seat: str = Query(None), status: str = Query(None)):
    banner = None
    if status in BANNERS:
        banner = BANNERS[status].format(seat=seat)

    context = {
        "seat_labels": hack_2026.seat_labels,
        "available": hack_2026.seat_available,
        "seats_left": hack_2026.seats_left,
        "mine": seat if status == "ok" else None,
        "banner": banner,
        "banner_ok": status == "ok",
    }
    return templates.TemplateResponse(request=request, name="ticket.html", context=context)


@router.post("/ticket")
def purchase_ticket(seat_label: str = Form(...)):
    result = hack_2026.reserve_seat(seat_label)
    return RedirectResponse(
        url=f"/ticket?seat={seat_label}&status={result['code']}",
        status_code=303,
    )