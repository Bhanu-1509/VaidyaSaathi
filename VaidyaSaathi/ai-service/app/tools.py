"""Tools the assistant can call.

Everything here is read-only. Booking happens in the browser after the
patient presses Confirm on a proposal card, using the patient's own login.
"""
from datetime import date as Date, datetime

from app import backend
from app.backend import TZ, BackendError

DECLARATIONS = [
    {
        "name": "list_specialities",
        "description": "List the medical specialities that have doctors on VaidyaSaathi.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "find_doctors",
        "description": "Find active doctors, optionally filtered by speciality name, doctor name or maximum fee.",
        "parameters": {
            "type": "object",
            "properties": {
                "speciality": {"type": "string", "description": "Speciality name, e.g. 'Cardiologist'"},
                "name": {"type": "string", "description": "Part of the doctor's name"},
                "max_fee": {"type": "number", "description": "Maximum consultation fee in rupees"},
            },
        },
    },
    {
        "name": "get_doctor_slots",
        "description": (
            "Get free appointment times for one doctor. If date is omitted, returns the first day "
            "in the next 10 days that has free slots."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_id": {"type": "integer"},
                "date": {"type": "string", "description": "YYYY-MM-DD in India time"},
            },
            "required": ["doctor_id"],
        },
    },
    {
        "name": "show_doctors",
        "description": "Show doctor cards in the chat so the patient can open their profile. Use after find_doctors.",
        "parameters": {
            "type": "object",
            "properties": {"doctor_ids": {"type": "array", "items": {"type": "integer"}}},
            "required": ["doctor_ids"],
        },
    },
    {
        "name": "propose_appointment",
        "description": (
            "Show a booking card for one specific free slot. The patient must press Confirm on the card; "
            "this does not book by itself. Only use a start_time returned by get_doctor_slots."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_id": {"type": "integer"},
                "start_time": {"type": "string", "description": "ISO start time exactly as returned by get_doctor_slots"},
                "reason": {"type": "string", "description": "Short reason for visit in the patient's words"},
            },
            "required": ["doctor_id", "start_time"],
        },
    },
    {
        "name": "search_lab_tests",
        "description": (
            "Search the lab test catalogue (single tests and health packages) by keyword or category. "
            "Categories include Full Body Checkup, Diabetes, Thyroid, Heart, Liver, Kidney, Vitamins, "
            "Fever & Infection, Women's Health, Hormones, Allergy."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "category": {"type": "string"},
            },
        },
    },
    {
        "name": "show_lab_tests",
        "description": "Show lab test cards with an Add to cart button. Use after search_lab_tests.",
        "parameters": {
            "type": "object",
            "properties": {"test_ids": {"type": "array", "items": {"type": "integer"}}},
            "required": ["test_ids"],
        },
    },
]


def _doc_brief(d: dict) -> dict:
    return {
        "id": d["id"],
        "name": d["full_name"],
        "speciality": d["specialization"]["name"],
        "fee": float(d["consultation_fee"]),
        "experience_years": d["experience_years"],
    }


def _doc_card(d: dict) -> dict:
    return {**_doc_brief(d), "photo": d.get("profile_photo_url"),
            "qualifications": ", ".join(q["degree"] for q in d.get("qualifications", []))}


def _test_brief(t: dict) -> dict:
    return {
        "id": t["id"],
        "name": t["name"],
        "category": t["category"],
        "price": float(t["price"]),
        "mrp": float(t["mrp"]),
        "is_package": t["is_package"],
        "fasting_hours": t["fasting_hours"],
        "report_hours": t["report_hours"],
        "includes": t["parameters"][:12],
    }


def _parse_time(value: str) -> datetime:
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=TZ)


def _label(t: datetime) -> str:
    return t.astimezone(TZ).strftime("%a %d %b, %I:%M %p").replace(" 0", " ")


class Toolbox:
    """Runs tool calls for one chat turn and collects the cards to show."""

    def __init__(self):
        self.cards: list[dict] = []
        self.memo: list[str] = []

    def run(self, name: str, args: dict) -> dict:
        fn = getattr(self, f"t_{name}", None)
        if fn is None:
            return {"error": f"Unknown tool {name}"}
        try:
            return fn(**(args or {}))
        except BackendError as exc:
            return {"error": str(exc)}
        except (TypeError, ValueError, KeyError) as exc:
            return {"error": f"Bad arguments: {exc}"}

    def t_list_specialities(self):
        return {"specialities": [s["name"] for s in backend.specialities()]}

    def t_find_doctors(self, speciality: str | None = None, name: str | None = None, max_fee: float | None = None):
        docs = backend.doctors()
        if speciality:
            s = speciality.lower().strip()
            docs = [d for d in docs if s in d["specialization"]["name"].lower() or d["specialization"]["name"].lower() in s]
        if name:
            n = name.lower().replace("dr.", "").replace("dr ", "").strip()
            docs = [d for d in docs if n in d["full_name"].lower()]
        if max_fee:
            docs = [d for d in docs if float(d["consultation_fee"]) <= float(max_fee)]
        docs.sort(key=lambda d: -d["experience_years"])
        return {"count": len(docs), "doctors": [_doc_brief(d) for d in docs[:8]]}

    def t_get_doctor_slots(self, doctor_id: int, date: str | None = None):
        doctor_id = int(doctor_id)
        days = [Date.fromisoformat(date)] if date else backend.next_days(10)
        for day in days:
            found = backend.slots(doctor_id, day)
            if found:
                return {
                    "doctor_id": doctor_id,
                    "date": day.isoformat(),
                    "slots": [{"start_time": t.isoformat(), "label": _label(t)} for t in found[:16]],
                    "more_available": len(found) > 16,
                }
        return {"doctor_id": doctor_id, "slots": [], "note": "No free slots on the requested day(s)."}

    def t_show_doctors(self, doctor_ids: list):
        docs = {d["id"]: d for d in backend.doctors()}
        cards = [_doc_card(docs[int(i)]) for i in doctor_ids if int(i) in docs][:6]
        if cards:
            self.cards.append({"type": "doctors", "doctors": cards})
            self.memo.append("Showed doctors: " + ", ".join(f"{c['name']} (id {c['id']})" for c in cards))
        return {"shown": len(cards)}

    def t_propose_appointment(self, doctor_id: int, start_time: str, reason: str | None = None):
        d = backend.doctor(int(doctor_id))
        if not d:
            return {"error": "Doctor not found"}
        wanted = _parse_time(start_time)
        free = backend.slots(int(doctor_id), wanted.astimezone(TZ).date())
        if not any(abs((t - wanted).total_seconds()) < 60 for t in free):
            return {"error": "That time is not free any more. Call get_doctor_slots again and pick another."}
        card = {
            "type": "appointment",
            "doctor": _doc_card(d),
            "start_time": wanted.astimezone(TZ).isoformat(),
            "label": _label(wanted),
            "reason": (reason or "")[:300] or None,
        }
        self.cards.append(card)
        self.memo.append(f"Proposed {d['full_name']} (id {d['id']}) at {card['label']}, waiting for patient to confirm")
        return {"status": "Booking card shown. The patient must press Confirm to book."}

    def t_search_lab_tests(self, query: str | None = None, category: str | None = None):
        tests = backend.lab_tests(query, category)
        if not tests and query:
            # Try each word on its own, e.g. "sugar test" -> "sugar"
            for word in query.split():
                if len(word) > 2:
                    tests += [t for t in backend.lab_tests(word) if t["id"] not in {x["id"] for x in tests}]
        return {"count": len(tests), "tests": [_test_brief(t) for t in tests[:10]]}

    def t_show_lab_tests(self, test_ids: list):
        by_id = {t["id"]: t for t in backend.lab_tests()}
        cards = [_test_brief(by_id[int(i)]) for i in test_ids if int(i) in by_id][:6]
        if cards:
            self.cards.append({"type": "lab_tests", "tests": cards})
            self.memo.append("Showed lab tests: " + ", ".join(f"{c['name']} (id {c['id']})" for c in cards))
        return {"shown": len(cards)}


def system_prompt() -> str:
    now = datetime.now(TZ)
    return f"""You are Saathi, the booking assistant inside VaidyaSaathi, an Indian app for doctor appointments and lab tests.
Today is {now.strftime('%A %d %B %Y')}, time {now.strftime('%I:%M %p')} India Standard Time. Prices are in rupees (₹).

What you do:
- Help patients find the right kind of doctor for their symptoms, see free times, and get a booking card to confirm.
- Help patients find lab tests or health packages and add them to their cart.

How to work:
- Ask at most one or two short questions when you need them (e.g. how long the symptom has lasted, preferred day).
- Use the tools for every fact about doctors, fees, slots and tests. Never invent a doctor, time, test or price.
- To book: find_doctors -> get_doctor_slots -> propose_appointment with an exact start_time from get_doctor_slots.
  Say clearly that the patient must press Confirm on the card. You cannot book on your own.
- When you list doctors or tests, also call show_doctors / show_lab_tests so the patient sees cards.
- If no doctor matches, say so and suggest a General Physician if one exists.
- Mention fasting needs for lab tests when relevant.

Safety:
- You are not a doctor. Do not diagnose or prescribe medicine or doses. You may say which kind of specialist usually handles a symptom.
- If the patient describes an emergency (chest pain, difficulty breathing, stroke signs such as face drooping or slurred speech,
  severe bleeding, unconsciousness, seizures, suicidal thoughts, severe injury), tell them to call 112 or 108 or go to the nearest
  emergency department now. Do not offer an appointment instead.
- Stay on health bookings. Politely decline unrelated requests.

Style: friendly, plain English (reply in Hindi or another Indian language if the patient writes in it), short sentences, no markdown tables.
Keep replies under 90 words unless the patient asks for detail."""
