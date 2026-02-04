from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
import json

from app.db.session import get_db
from app.db.models import Conversation, Message, Persona

from app.guardrails.service import classify_intent
from app.guardrails.logger import log_violation

from app.chat.prompts import (
    system_guardrails_prompt,
    tone_prompt,
    persona_prompt,
)

from app.persona.service import (
    extract_persona_from_message,
    update_persona,
)

from app.core.openai_client import chat_completion
from app.chat.memory import summarize_messages


router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    user_id: str
    message: str


# ─────────────────────────────────────────────
# PERSONA SNAPSHOT
# ─────────────────────────────────────────────

def get_persona_state(persona: Persona) -> dict:
    if not persona:
        return {}

    state = {
        "age": getattr(persona, "age", None),
        "goal": persona.goal,
        "diet_type": persona.diet_type,
        "activity_level": persona.activity_level,
        "gender": getattr(persona, "gender", None),
        "height_cm": getattr(persona, "height_cm", None),
        "weight_kg": getattr(persona, "weight_kg", None),
    }

    if persona.misc_persona:
        state.update(persona.misc_persona)

    return state


# ─────────────────────────────────────────────
# PERSONA READINESS GATE (CRITICAL)
# ─────────────────────────────────────────────

def is_persona_ready(intent: str, persona: dict) -> bool:
    """
    HARD gate: no proper advice until we understand the user.
    """
    intent = intent or ""

    if intent == "diet":
        return all([
            persona.get("age"),
            persona.get("goal"),
            persona.get("diet_type"),
        ])

    if intent == "fitness":
        return all([
            persona.get("age"),
            persona.get("goal"),
            persona.get("activity_level"),
        ])

    if intent in {"hair", "skin"}:
        return all([
            persona.get("age"),
            persona.get("stress_level") or persona.get("hairfall_duration"),
        ])

    return True


def get_next_missing_fields(intent: str, persona: dict) -> list[str]:
    """
    Ask MAX 2 fields per turn.
    """
    intent = intent or ""
    fields = []

    if intent == "diet":
        fields = ["age", "goal", "diet_type"]

    elif intent == "fitness":
        fields = ["age", "goal", "activity_level"]

    elif intent in {"hair", "skin"}:
        fields = ["age", "stress_level", "hairfall_duration"]

    missing = [f for f in fields if not persona.get(f)]
    return missing[:2]


# ─────────────────────────────────────────────
# MAIN CHAT ENDPOINT
# ─────────────────────────────────────────────

@router.post("/")
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    user_id = payload.user_id
    user_message = payload.message.strip()

    # 1️⃣ Conversation
    convo = (
        db.query(Conversation)
        .filter_by(user_id=user_id, is_active=True)
        .first()
    )

    if not convo:
        convo = Conversation(user_id=user_id)
        db.add(convo)
        db.commit()
        db.refresh(convo)

    db.add(Message(
        conversation_id=convo.id,
        role="user",
        content=user_message,
    ))
    db.commit()

    # 2️⃣ Persona
    persona = (
        db.query(Persona)
        .filter_by(user_id=user_id)
        .first()
    )

    if not persona:
        persona = Persona(user_id=user_id, misc_persona={})
        db.add(persona)
        db.commit()
        db.refresh(persona)

    extracted = extract_persona_from_message(user_message)
    if extracted:
        update_persona(db, persona, extracted)

    persona_state = get_persona_state(persona)

    # 3️⃣ Intent (SAFETY ONLY)
    intent = classify_intent(user_message)

    if intent in {"sexual", "harmful"}:
        log_violation(db, user_id, convo.id, intent)
        return {"reply": "Is topic pe main help nahi kar paungi."}

    if intent == "medical":
        log_violation(db, user_id, convo.id, intent)
        return {
            "reply": (
                "Hmm\n"
                "Samajh aa raha hai.\n"
                "Ye thoda medical concern lagta hai. Doctor se consult karna best rahega."
            )
        }

    # Special mapping: hairfall → hair
    lower = user_message.lower()
    if intent == "lifestyle" and any(w in lower for w in ["hairfall", "hair fall", "hair loss"]):
        intent = "hair"

    # 4️⃣ Memory
    messages = (
        db.query(Message)
        .filter_by(conversation_id=convo.id)
        .order_by(Message.created_at)
        .all()
    )

    if len(messages) > 40:
        summary = summarize_messages(messages[:-30])
        if summary:
            convo.summary = summary
            db.commit()
        messages = messages[-30:]

    # 5️⃣ Persona gating
    persona_ready = is_persona_ready(intent, persona_state)
    missing_fields = get_next_missing_fields(intent, persona_state) if not persona_ready else []

    # 6️⃣ PROMPT (LLM-FIRST, CONTROLLED)
    system_content = "\n".join(filter(None, [
        system_guardrails_prompt(),
        tone_prompt(),
        persona_prompt(persona),
    ]))

    prompt_messages = [
        {"role": "system", "content": system_content},
        {
            "role": "system",
            "content": (
                f"Conversation mode: {'ADVICE' if persona_ready else 'DISCOVERY'}\n"
                f"Known persona:\n{json.dumps(persona_state, indent=2)}\n\n"
                f"Missing fields to ask now (MAX 2): {missing_fields or 'None'}\n\n"
                "Rules:\n"
                "- If in DISCOVERY mode:\n"
                "  • Do NOT give final advice.\n"
                "  • Start with 1–2 short human reactions (each on new line).\n"
                "  • Ask ONLY the missing fields naturally.\n"
                "- If in ADVICE mode:\n"
                "  • Start with 1–2 WhatsApp-style reactions (new lines).\n"
                "  • Then give ONE confident, complete answer.\n"
                "- Language: simple, respectful Hinglish (badhia, achha, shi, hmmm, thoda).\n"
                "- Sound like a real human on WhatsApp.\n"
            )
        }
    ]

    if convo.summary:
        prompt_messages.append({
            "role": "system",
            "content": f"Conversation memory:\n{convo.summary}"
        })

    for m in messages:
        prompt_messages.append({"role": m.role, "content": m.content})

    # 7️⃣ LLM CALL
    reply = chat_completion(prompt_messages)

    db.add(Message(
        conversation_id=convo.id,
        role="assistant",
        content=reply,
    ))
    db.commit()

    return {"reply": reply}
