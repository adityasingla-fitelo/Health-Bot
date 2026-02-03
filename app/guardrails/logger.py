from sqlalchemy.orm import Session
from app.db.models import ViolationLog


def log_violation(db: Session, user_id, conversation_id, intent_type) -> int:
    """
    Logs a guardrail violation and returns the updated count
    for this (user, conversation, intent_type).
    """

    violation = (
        db.query(ViolationLog)
        .filter_by(
            user_id=user_id,
            conversation_id=conversation_id,
            intent_type=intent_type
        )
        .first()
    )

    if violation:
        violation.count += 1
    else:
        violation = ViolationLog(
            user_id=user_id,
            conversation_id=conversation_id,
            intent_type=intent_type,
            count=1
        )
        db.add(violation)

    db.commit()
    db.refresh(violation)

    return violation.count