# app/persona/service.py

import json
from app.core.openai_client import chat_completion


# ─────────────────────────────────────────────
# 1️⃣ LLM-BASED PERSONA EXTRACTION (SILENT)
# ─────────────────────────────────────────────

EXTRACTION_PROMPT = """
You extract persona details for a health & lifestyle assistant.

Rules:
- Extract ONLY what is clearly stated or strongly implied
- Do NOT guess
- If unsure, use null
- Output STRICT JSON only (no markdown, no text)

Fields:
- age (number or null)
- goal (fat_loss | muscle_gain | general_health | null)
- diet_type (vegetarian | non_veg | eggitarian | null)
- activity_level (sedentary | active | null)
- skin_type (oily | dry | combination | null)

User message:
"{message}"
"""


def extract_persona_from_message(message: str) -> dict:
    """
    Uses LLM ONLY to extract structured persona signals.
    Never controls conversation flow.
    """
    if not message:
        return {}

    result = chat_completion([
        {
            "role": "system",
            "content": "You extract structured JSON only. No explanations."
        },
        {
            "role": "user",
            "content": EXTRACTION_PROMPT.format(message=message)
        }
    ])

    try:
        data = json.loads(result)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


# ─────────────────────────────────────────────
# 2️⃣ SAFE PERSONA UPDATE (NO GUESSING)
# ─────────────────────────────────────────────

def update_persona(db, persona, extracted: dict):
    """
    Updates persona ONLY with confident signals.
    Never overwrites existing data with weak info.
    """
    if not persona or not extracted:
        return

    # Age → map to range safely
    age = extracted.get("age")
    if isinstance(age, int) and 13 <= age <= 100:
        if age <= 22:
            persona.age_range = "18–22"
        elif age <= 27:
            persona.age_range = "23–27"
        else:
            persona.age_range = "28+"

    if extracted.get("goal"):
        persona.goal = extracted["goal"]

    if extracted.get("diet_type"):
        persona.diet_type = extracted["diet_type"]

    if extracted.get("activity_level"):
        persona.activity_level = extracted["activity_level"]

    if extracted.get("skin_type"):
        persona.misc_persona = persona.misc_persona or {}
        persona.misc_persona["skin_type"] = extracted["skin_type"]

    db.commit()


# ─────────────────────────────────────────────
# 3️⃣ HUMAN PERSONA QUESTION ENGINE
# ─────────────────────────────────────────────

def should_ask_persona_question(persona, intent: str | None) -> str | None:
    """
    Returns ONE natural, human-like question
    ONLY if answering properly requires it.
    Otherwise returns None.
    """
    if not persona:
        return "Before we continue — how old are you?"

    intent = intent or ""

    # Age is foundational, asked casually
    if not persona.age_range:
        return "Before I go deeper — how old are you?"

    # Diet queries need goal + diet type
    if intent == "diet":
        if not persona.goal:
            return "What’s your main goal right now — fat loss, muscle gain, or just staying healthy?"
        if not persona.diet_type:
            return "Do you follow a veg, non-veg, or eggitarian diet?"

    # Fitness needs activity context
    if intent == "fitness" and not persona.activity_level:
        return "How active are you usually — mostly desk-based or fairly active?"

    # Skin needs skin type
    if intent == "skin":
        skin_type = (persona.misc_persona or {}).get("skin_type")
        if not skin_type:
            return "Do you know your skin type — oily, dry, or combination?"

    return None
