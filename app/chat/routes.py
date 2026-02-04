from fastapi import APIRouter, Depends
import re
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
    get_genz_greeting,
)
from app.persona.service import (
    extract_persona_from_message,
    update_persona,
    should_ask_persona_question,
)
from app.core.openai_client import chat_completion
from app.chat.memory import summarize_messages

class ChatRequest(BaseModel):
    user_id: str
    message: str

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/")
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    user_id = payload.user_id
    user_message = payload.message.strip()

    # Conversation
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

    # Persona (extract + update)
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

    # Heuristic: directly parse very short persona answers so we don't repeat questions.
    lower_msg = user_message.lower()

    # Age (e.g. "22")
    if (convo.phase in {"diet", "fitness"} or "age" in lower_msg) and getattr(persona, "age", None) is None:
        m_age = re.search(r"\b(\d{1,2})\b", user_message)
        if m_age:
            age_val = int(m_age.group(1))
            if 12 <= age_val <= 80:
                persona.age = age_val
                db.commit()

    # Height and weight in one line (supports cm or feet + inches, e.g. "172cm and 62kg" or "5ft 7 and 60kg")
    if getattr(persona, "height_cm", None) is None or getattr(persona, "weight_kg", None) is None:
        text = lower_msg
        height_cm = None
        weight_kg = None

        # feet format
        feet_match = re.search(r"(\\d+)\\s*(ft|feet|'?)\\s*(\\d+)?", text)
        if feet_match:
            feet = int(feet_match.group(1))
            inches = int(feet_match.group(3) or 0)
            height_cm = round(feet * 30.48 + inches * 2.54)

        # generic numbers
        nums = [float(n) for n in re.findall(r"\\d+(?:\\.\\d+)?", text)]
        if len(nums) == 1:
            n = nums[0]
            if n > 90 and height_cm is None:  # likely cm
                height_cm = n
            elif n >= 30 and n <= 200 and weight_kg is None:
                weight_kg = n
        elif len(nums) >= 2:
            # assume first ~height, second ~weight
            if height_cm is None:
                if nums[0] > 90:
                    height_cm = nums[0]
                elif nums[0] < 3 and "ft" in text:
                    height_cm = nums[0] * 30.48
            if weight_kg is None:
                weight_kg = nums[1]

        if height_cm and getattr(persona, "height_cm", None) is None:
            persona.height_cm = int(round(height_cm))
            db.commit()
        if weight_kg and getattr(persona, "weight_kg", None) is None:
            persona.weight_kg = int(round(weight_kg))
            db.commit()

    # Extra mappings for goal / diet / activity from very short replies
    direct_goals = {
        "muscle gain": "muscle_gain",
        "muscle building": "muscle_gain",
        "fat loss": "fat_loss",
        "weight loss": "fat_loss",
        "general health": "general_health",
        "overall health": "general_health",
    }
    if lower_msg in direct_goals and not persona.goal:
        persona.goal = direct_goals[lower_msg]
        db.commit()

    direct_diets = {
        "veg": "vegetarian",
        "vegetarian": "vegetarian",
        "non veg": "non_veg",
        "non-veg": "non_veg",
        "nonveg": "non_veg",
        "egg": "eggitarian",
        "eggitarian": "eggitarian",
    }
    if lower_msg in direct_diets and not persona.diet_type:
        persona.diet_type = direct_diets[lower_msg]
        db.commit()

    if any(kw in lower_msg for kw in {"desk", "sitting", "baithi", "office"}) and not persona.activity_level:
        persona.activity_level = "sedentary"
        db.commit()
    if lower_msg in {"active", "very active", "moderately active"} and not persona.activity_level:
        persona.activity_level = "active"
        db.commit()

    # Intent (safety only) + topic tracking
    intent = classify_intent(user_message)
    if intent in {"sexual", "harmful"}:
        log_violation(db, user_id, convo.id, intent)
        return {"reply": "Is topic pe main help nahi kar paungi."}
    if intent == "medical":
        log_violation(db, user_id, convo.id, intent)
        return {
            "reply": (
                f"{get_genz_greeting()}\nYeh medical concern lag raha hai! Doctor se consult zaroor karo."
            )
        }

    # Decide which topic we are in for persona questions.
    topic_intent = intent
    main_topics = {"diet", "fitness", "skin", "hair"}

    # Special handling: hairfall / hair loss → treat as "hair" topic
    if intent == "lifestyle" and any(
        kw in lower_msg for kw in ["hairfall", "hair fall", "hair loss", "baal gir", "baal gire"]
    ):
        topic_intent = "hair"
        convo.phase = "hair"
        db.commit()
    elif intent in main_topics:
        convo.phase = intent  # remember last main topic for this conversation
        db.commit()
    elif convo.phase in main_topics:
        topic_intent = convo.phase

    # Persona Gate (ask 3–5 key questions BEFORE answering)
    follow_up = should_ask_persona_question(persona, topic_intent)
    if follow_up:
        db.add(Message(
            conversation_id=convo.id,
            role="assistant",
            content=follow_up,
        ))
        db.commit()
        return {"reply": follow_up}

    # Memory handling 
    messages = (
        db.query(Message)
        .filter_by(conversation_id=convo.id)
        .order_by(Message.created_at)
        .all()
    )
    if len(messages) > 40:
        old = messages[:-30]
        summary = summarize_messages(old)
        if summary:
            convo.summary = summary
            db.commit()
        messages = messages[-30:]

    # LLM CALL: GenZ/Ira prompt
    system_content = "\n".join(filter(None, [
        system_guardrails_prompt(),
        tone_prompt(),
        persona_prompt(persona),
    ]))
    prompt_messages = [{"role": "system", "content": system_content}]
    if convo.summary:
        prompt_messages.append({
            "role": "system",
            "content": f"Conversation memory:\n{convo.summary}"
        })
    for m in messages:
        prompt_messages.append({
            "role": m.role,
            "content": m.content
        })
    # Force leading greeting
    greeting = get_genz_greeting()
    prompt_messages.append({
        "role": "system",
        "content": f"Your first reply MUST start with: '{greeting}' as a separate chat bubble. Then directly deliver the full answer as the next message block in a human chatty tone."})
    reply = chat_completion(prompt_messages)
    db.add(Message(
        conversation_id=convo.id,
        role="assistant",
        content=reply,
    ))
    db.commit()
    return {"reply": reply}
