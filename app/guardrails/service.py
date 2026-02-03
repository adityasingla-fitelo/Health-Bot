from app.core.openai_client import chat_completion

INTENT_PROMPT = """
You are an intent classification engine for a health & lifestyle chatbot.

Classify the user's message into ONE of the following categories ONLY:

- diet            (food, calories, weight loss/gain, meal planning)
- fitness         (workouts, gym, exercise, activity)
- skin            (acne, skincare routine, cosmetic concerns — non-medical)
- lifestyle       (sleep, habits, fatigue, routine, hydration)
- medical         (symptoms, diseases, diagnosis, medicines, supplements)
- sexual          (sexual or explicit content)
- off_topic       (coding, homework, academics, unrelated topics)
- harmful         (self-harm, dangerous advice, illegal actions)

Rules:
- If the message mentions symptoms, pain, disease, medicines, or supplements → medical
- If unsure between health and medical → choose medical
- Reply with ONLY the category name (lowercase)
- Do not explain
- If the user mentions common issues like hairfall, tiredness, skin problems
WITHOUT medicines or diagnosis → classify as lifestyle, NOT medical


User message:
"{message}"
"""


ALLOWED_INTENTS = {
    "diet",
    "fitness",
    "skin",
    "lifestyle",
    "medical",
    "sexual",
    "off_topic",
    "harmful",
}


def classify_intent(message: str) -> str:
    """
    Returns a normalized intent label.
    Falls back safely if LLM response is noisy.
    """

    result = chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "You are a strict intent classifier. "
                    "Reply with exactly ONE lowercase label."
                ),
            },
            {
                "role": "user",
                "content": INTENT_PROMPT.format(message=message),
            },
        ]
    )

    if not result:
        return "off_topic"

    # 🔹 Normalize aggressively
    intent = (
        result.strip()
        .lower()
        .replace("intent:", "")
        .replace(".", "")
        .replace("\n", "")
        .strip()
    )

    if intent not in ALLOWED_INTENTS:
        return "off_topic"

    return intent
