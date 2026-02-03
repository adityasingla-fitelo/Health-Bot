from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import Conversation, Message, Persona

from app.guardrails.service import classify_intent
from app.guardrails.logger import log_violation

from app.chat.prompts import (
    system_guardrails_prompt,
    tone_prompt,
    persona_prompt,
    conversation_context,
)

from app.persona.service import (
    extract_persona_from_message,
    update_persona,
    should_ask_persona_question,
)

from app.core.openai_client import chat_completion


class ChatRequest(BaseModel):
    user_id: str
    message: str


router = APIRouter(prefix="/chat", tags=["chat"])


# ─────────────────────────────────────────────
# 🔑 Helper: detect persona questions
# ─────────────────────────────────────────────
def is_persona_question(text: str | None) -> bool:
    if not text:
        return False

    triggers = [
        "how old are you",
        "main goal",
        "fat loss",
        "muscle gain",
        "veg, non-veg",
        "how active",
        "skin type",
    ]

    t = text.lower()
    return any(trigger in t for trigger in triggers)


@router.post("/")
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    user_id = payload.user_id
    user_message = payload.message.strip()

    # ─────────────────────────────────────────────
    # 1️⃣ Conversation
    # ─────────────────────────────────────────────
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

    # Store user message
    db.add(Message(
        conversation_id=convo.id,
        role="user",
        content=user_message,
    ))
    db.commit()

    # ─────────────────────────────────────────────
    # 2️⃣ Check if user is answering a persona question
    # ─────────────────────────────────────────────
    last_assistant = (
        db.query(Message)
        .filter_by(conversation_id=convo.id, role="assistant")
        .order_by(Message.created_at.desc())
        .first()
    )

    if last_assistant and is_persona_question(last_assistant.content):
        # Ensure persona exists
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

        # Update persona from this reply
        extracted = extract_persona_from_message(user_message)
        update_persona(db, persona, extracted)

        # Ask next persona question ONLY if still needed
        follow_up = should_ask_persona_question(persona, intent="diet")

        if follow_up:
            db.add(Message(
                conversation_id=convo.id,
                role="assistant",
                content=follow_up,
            ))
            db.commit()
            return {"reply": follow_up}

        # Persona complete → now allow normal answering
        # DO NOT classify intent on numeric answers like "22"
        intent = "diet"
    else:
        intent = classify_intent(user_message)

    # ─────────────────────────────────────────────
    # 3️⃣ Guardrails (ONLY for real queries)
    # ─────────────────────────────────────────────
    if intent in {"medical", "sexual", "off_topic", "harmful"}:
        log_violation(db, user_id, convo.id, intent)

        if intent == "medical":
            return {
                "reply": (
                    "Yeh medical concern lag raha hai. "
                    "Iske liye doctor se consult karna better rahega 🙂\n\n"
                    "Diet, fitness ya lifestyle ke through help chahiye ho "
                    "toh main yahin hoon."
                )
            }

        return {
            "reply": (
                "Is topic pe main help nahi kar paungi 😅\n\n"
                "Health, diet, fitness ya lifestyle se related kuch poochna ho toh batao."
            )
        }

    # ─────────────────────────────────────────────
    # 4️⃣ Persona gate BEFORE answering
    # ─────────────────────────────────────────────
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

    follow_up = should_ask_persona_question(persona, intent)

    if follow_up:
        db.add(Message(
            conversation_id=convo.id,
            role="assistant",
            content=follow_up,
        ))
        db.commit()
        return {"reply": follow_up}

    # ─────────────────────────────────────────────
    # 5️⃣ Context
    # ─────────────────────────────────────────────
    messages = (
        db.query(Message)
        .filter_by(conversation_id=convo.id)
        .order_by(Message.created_at)
        .all()
    )

    system_content = "\n".join(filter(None, [
        system_guardrails_prompt(),
        tone_prompt(),
        persona_prompt(persona),
    ]))

    prompt_messages = [
        {"role": "system", "content": system_content},
        {"role": "system", "content": conversation_context(messages)},
        {"role": "user", "content": user_message},
    ]

    # ─────────────────────────────────────────────
    # 6️⃣ LLM ANSWER (FINALLY)
    # ─────────────────────────────────────────────
    reply = chat_completion(prompt_messages)

    db.add(Message(
        conversation_id=convo.id,
        role="assistant",
        content=reply,
    ))
    db.commit()

    return {"reply": reply}
