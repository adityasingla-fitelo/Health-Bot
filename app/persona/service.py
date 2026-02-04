import json
from app.core.openai_client import chat_completion
from app.persona.requirements import REQUIRED_PERSONA_FIELDS

def extract_persona_from_message(message: str) -> dict:
    if not message:
        return {}

    # Extraction logic (extend if new fields required)
    result = chat_completion([
        {"role": "system", "content": "Return ONLY valid JSON."},
        {
            "role": "user",
            "content": f'''
Extract all stated persona values, STRICT JSON only.

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
- scalp_condition        # dry / oily / normal / sensitive
- dandruff               # yes / no / sometimes
- stress_level           # low / medium / high
- hairfall_duration      # e.g. "2 months", "6 weeks"

User message: "{message}"
''',
        }
    ])

    try:
        data = json.loads(result)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

# New helper: get missing persona fields for intent/topic

def get_missing_fields(persona, topic: str):
    req = REQUIRED_PERSONA_FIELDS.get(topic, [])
    persona_dict = (persona.misc_persona if hasattr(persona, 'misc_persona') else {}) or {}
    # Flatten core fields from Persona into a simple dict
    for f in [
        'age',
        'goal',
        'diet_type',
        'activity_level',
        'gender',
        'height_cm',
        'weight_kg',
        'skin_type',
        'hair_type',
        'training_days_per_week',
    ]:
        v = getattr(persona, f, None)
        if v is not None and v != '':
            persona_dict[f] = v
    missing = [f for f in req if not persona_dict.get(f)]
    return missing

def update_persona(db, persona, extracted: dict):
    if not persona or not extracted:
        return
    # Core structured fields on Persona
    if extracted.get('age') and not getattr(persona, 'age', None):
        persona.age = extracted['age']
    if extracted.get('goal') and not persona.goal:
        persona.goal = extracted['goal']
    if extracted.get('diet_type') and not persona.diet_type:
        persona.diet_type = extracted['diet_type']
    if extracted.get('activity_level') and not persona.activity_level:
        persona.activity_level = extracted['activity_level']
    if extracted.get('gender') and not getattr(persona, 'gender', None):
        persona.gender = extracted['gender']
    if extracted.get('height_cm') and not getattr(persona, 'height_cm', None):
        persona.height_cm = extracted['height_cm']
    if extracted.get('weight_kg') and not getattr(persona, 'weight_kg', None):
        persona.weight_kg = extracted['weight_kg']
    # Flexible misc fields (skin/hair etc.)
    misc = persona.misc_persona or {}
    if extracted.get("skin_type") and "skin_type" not in misc:
        misc["skin_type"] = extracted["skin_type"]
    if extracted.get("scalp_condition") and "scalp_condition" not in misc:
        misc["scalp_condition"] = extracted["scalp_condition"]
    if extracted.get("dandruff") and "dandruff" not in misc:
        misc["dandruff"] = extracted["dandruff"]
    if extracted.get("stress_level") and "stress_level" not in misc:
        misc["stress_level"] = extracted["stress_level"]
    if extracted.get("hairfall_duration") and "hairfall_duration" not in misc:
        misc["hairfall_duration"] = extracted["hairfall_duration"]

    persona.misc_persona = misc
    db.commit()

def should_ask_persona_question(persona, intent: str | None):
    """
    Returns ONE soft persona question for this intent.
    We only block answering until a *small core* of fields is filled
    (3–4 max), so the user is not stuck in an endless Q&A loop.
    """
    if not persona or not intent:
        return None

    missing = get_missing_fields(persona, intent)
    if not missing:
        return None

    field = missing[0]
    return _persona_field_question_soft(field)

def _persona_field_question_soft(field: str) -> str:
    """
    Soft, feminine, GenZ-style prompts for missing persona fields.
    Tone: friendly, caring, not harsh or shouty.
    """
    friendly = {
        "age": (
            "Ek chhota sa basic detail batayenge?\n"
            "Aapki age kitni hai abhi?"
        ),
        "height_cm": (
            "Thoda body stats samajh loon, phir plan bohot better banega.\n"
            "Aapki height aur approx weight kitna hai (feet/cm aur kg)?"
        ),
        "goal": (
            "Ab bataiye, aapka main goal kya hai?\n"
            "Fat loss, muscle gain, ya overall healthy feel karna?"
        ),
        "diet_type": (
            "Food side se thoda bataiye.\n"
            "Aap mostly veg ho, non‑veg ho ya eggitarian?"
        ),
        "activity_level": (
            "Roz ka din kaisa rehta hai aapka?\n"
            "Zyada desk/baithi‑baithi life hai ya kaafi active rehte ho din bhar?"
        ),
        "skin_type": (
            "Skin ke liye ek basic cheez jaan lena zaroori hai.\n"
            "Aapki skin oily, dry, ya combination type lagti hai?"
        ),
        "hair_type": (
            "Baal ka pattern kaisa hai?\n"
            "Straight, wavy, curly… thoda bata dijiye."
        ),
        "scalp_condition": (
            "Scalp ka feel kaisa rehta hai zyada tar?\n"
            "Oily, dry, normal, ya thoda sensitive type?"
        ),
        "dandruff": (
            "Kya dandruff ka issue rehta hai?\n"
            "Bilkul nahi, thoda sa, ya kaafi zyada?"
        ),
        "stress_level": (
            "Last kuch mahino se stress level kaisa raha hai aapka?\n"
            "Low, medium, ya high bolenge?"
        ),
        "hairfall_duration": (
            "Hairfall ko roughly kitna time ho gaya hai?\n"
            "Kuch weeks, months, ya saalon se?"
        ),
    }

    return friendly.get(
        field,
        "Bas ek chhota sa detail aur bata dijiye, fir main properly guide karungi.",
    )
