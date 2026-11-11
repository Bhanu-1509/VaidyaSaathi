"""Simple keyword matcher used when no GEMINI_API_KEY is set.

It can't hold a conversation, but it still points patients to the right
specialist and shows doctor cards, so the app works without a key.
"""
from app import backend
from app.backend import BackendError
from app.tools import Toolbox

EMERGENCY = ["chest pain", "can't breathe", "cannot breathe", "breathless", "unconscious", "stroke",
             "seizure", "fits", "heavy bleeding", "suicide", "kill myself", "poison"]

# keyword -> speciality name (as seeded in docker/seed-specialities.sql)
RULES = [
    (["heart", "palpitation", "blood pressure", "bp", "cholesterol"], "Cardiologist"),
    (["skin", "rash", "acne", "itch", "hair fall", "pimple", "eczema"], "Dermatologist"),
    (["child", "baby", "kid", "son", "daughter", "infant"], "Pediatrician"),
    (["bone", "joint", "knee", "back pain", "fracture", "shoulder", "sprain", "neck pain"], "Orthopedic"),
    (["period", "pregnan", "pcod", "pcos", "uterus", "menstru", "gyn"], "Gynecologist"),
    (["ear", "nose", "throat", "sinus", "tonsil", "hearing"], "ENT"),
    (["headache", "migraine", "numb", "dizz", "nerve", "memory", "tremor"], "Neurologist"),
    (["fever", "cold", "cough", "flu", "weak", "tired", "stomach", "vomit", "diabetes", "sugar"], "General Physician"),
]

LAB_HINTS = [
    (["sugar", "diabetes"], "Diabetes"), (["thyroid"], "Thyroid"), (["fever", "dengue", "typhoid", "malaria"], "Fever"),
    (["vitamin", "tired", "weak"], "Vitamin"), (["full body", "checkup", "check-up"], "Full Body"),
    (["cholesterol", "heart"], "Lipid"), (["liver"], "Liver"), (["kidney"], "Kidney"),
]


def reply(history: list[dict]) -> dict:
    text = next((m["text"] for m in reversed(history) if m["role"] == "user"), "").lower()
    if any(k in text for k in EMERGENCY):
        return {"reply": "This could be an emergency. Please call 112 or 108, or go to the nearest emergency "
                         "department now. Don't wait for an appointment.", "cards": [], "memo": ""}
    tools = Toolbox()
    try:
        wants_test = any(w in text for w in ["test", "lab", "checkup", "check-up", "package"])
        if wants_test:
            q = next((q for keys, q in LAB_HINTS if any(k in text for k in keys)), None)
            found = tools.t_search_lab_tests(q)["tests"] if q else []
            if found:
                tools.t_show_lab_tests([t["id"] for t in found[:4]])
                return {"reply": "Here are some lab tests that match. Tap Add to cart, then book a slot.",
                        "cards": tools.cards, "memo": ""}
        spec = next((s for keys, s in RULES if any(k in text for k in keys)), None)
        if spec:
            docs = tools.t_find_doctors(speciality=spec)["doctors"]
            if docs:
                tools.t_show_doctors([d["id"] for d in docs[:4]])
                return {"reply": f"A {spec} usually handles this. Open a doctor below to see free slots and book.",
                        "cards": tools.cards, "memo": ""}
            return {"reply": f"A {spec} usually handles this, but none is listed yet. "
                             "Try a General Physician from the Doctors page.", "cards": [], "memo": ""}
    except BackendError:
        return {"reply": "I couldn't reach the doctor list just now. Please try again shortly.", "cards": [], "memo": ""}
    return {"reply": "Tell me your main symptom (for example 'fever for 3 days' or 'knee pain'), or the test you "
                     "need (for example 'thyroid test'). The full AI assistant is off because no Gemini key is set.",
            "cards": [], "memo": ""}
