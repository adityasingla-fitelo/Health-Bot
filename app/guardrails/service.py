from app.core.openai_client import chat_completion


INTENT_PROMPT = """
You are an intent classification engine for a health & lifestyle chatbot.

Classify the user's message into ONE of the following categories ONLY:

- diet            (food, calories, weight loss/gain, meal planning)
- fitness         (workouts, gym, exercise, activity)
- skin            (acne, skincare routine, cosmetic concerns)
- lifestyle       (sleep, habits, fatigue, routine, hydration, hairfall)
- medical         (clear symptoms, diseases, diagnosis, medicines, dosages)
- sexual          (sexual or explicit content)
- off_topic       (coding, homework, academics, unrelated topics)
- harmful         (self-harm, dangerous advice, illegal actions)

IMPORTANT RULES:
- Hairfall, tiredness, low energy, pimples, digestion issues WITHOUT medicines
  or diagnosis → lifestyle (NOT medical)
- Gym pain, soreness, recovery → fitness (NOT medical)
- Diet for BP, sugar, cholesterol WITHOUT medicines → diet (NOT medical)
- ONLY classify as medical if diagnosis, medicines, supplements,
  dosages, or serious symptoms are clearly mentioned
- If unsure between lifestyle/diet/fitness vs medical → choose lifestyle

Reply with ONLY the category name in lowercase.
Do NOT explain.

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
    Classifies user intent with a bias towards helping,
    not blocking.

    Medical is a LAST resort.
    """

    if not message or not message.strip():
        return "off_topic"

    result = chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "You are a strict but helpful intent classifier. "
                    "When in doubt, choose a NON-medical category."
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
