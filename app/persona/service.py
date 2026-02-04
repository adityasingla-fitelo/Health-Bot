import json
from app.core.openai_client import chat_completion


# ─────────────────────────────────────────────
# 1️⃣ LLM-BASED PERSONA EXTRACTION (SILENT)
# ─────────────────────────────────────────────

EXTRACTION_PROMPT = """
Extract persona details ONLY if they are explicitly stated.

Rules:
- Do NOT guess
- Do NOT infer
- If unsure, return null
- Output STRICT JSON only

Fields:
- age
- goal
- diet_type
- activity_level
- gender
- height_cm
- weight_kg
- skin_type
- hair_type
- training_days_per_week
- scalp_condition
- dandruff
- stress_level
- hairfall_duration

User message:
"{message}"
"""


def extract_persona_from_message(message: str) -> dict:
    """
    Uses LLM to silently extract persona signals.
    This function NEVER controls the conversation.
    """
    if not message:
        return {}

    result = chat_completion([
        {"role": "system", "content": "Return ONLY valid JSON. No explanations."},
        {"role": "user", "content": EXTRACTION_PROMPT.format(message=message)},
    ])

    try:
        data = json.loads(result)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


# ─────────────────────────────────────────────
# 2️⃣ SAFE PERSONA UPDATE (NO OVERRIDES)
# ─────────────────────────────────────────────

def update_persona(db, persona, extracted: dict):
    """
    Stores persona details ONLY if:
    - They are explicitly extracted
    - They are not already present

    Never overwrites existing data.
    """
    if not persona or not extracted:
        return

    # Core structured fields
    for field in [
        "age",
        "goal",
        "diet_type",
        "activity_level",
        "gender",
        "height_cm",
        "weight_kg",
        "training_days_per_week",
    ]:
        if extracted.get(field) is not None and getattr(persona, field, None) is None:
            setattr(persona, field, extracted[field])

    # Flexible / descriptive fields go to misc_persona
    misc = persona.misc_persona or {}

    for field in [
        "skin_type",
        "hair_type",
        "scalp_condition",
        "dandruff",
        "stress_level",
        "hairfall_duration",
    ]:
        if extracted.get(field) and field not in misc:
            misc[field] = extracted[field]

    persona.misc_persona = misc
    db.commit()


# ─────────────────────────────────────────────
# 3️⃣ PERSONA SNAPSHOT (FOR LLM CONTEXT ONLY)
# ─────────────────────────────────────────────

def get_persona_snapshot(persona) -> dict:
    """
    Returns a clean snapshot of known persona data.
    Used ONLY as context for the LLM.
    """
    if not persona:
        return {}

    snapshot = {
        "age": getattr(persona, "age", None),
        "goal": persona.goal,
        "diet_type": persona.diet_type,
        "activity_level": persona.activity_level,
        "gender": getattr(persona, "gender", None),
        "height_cm": getattr(persona, "height_cm", None),
        "weight_kg": getattr(persona, "weight_kg", None),
        "training_days_per_week": getattr(persona, "training_days_per_week", None),
    }

    if persona.misc_persona:
        snapshot.update(persona.misc_persona)

    # Remove empty values
    return {k: v for k, v in snapshot.items() if v not in (None, "", [])}
