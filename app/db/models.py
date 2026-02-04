import uuid
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
    Integer,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.session import Base

# ─────────────────────────────────────────────
# USERS
# ─────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    persona = relationship(
        "Persona",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    conversations = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )

# ─────────────────────────────────────────────
# PERSONA
# ─────────────────────────────────────────────
class Persona(Base):
    __tablename__ = "personas"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    age = Column(Integer, nullable=True)  # NEW
    gender = Column(String, nullable=True)  # NEW
    goal = Column(String, nullable=True)
    diet_type = Column(String, nullable=True)
    activity_level = Column(String, nullable=True)
    height_cm = Column(Integer, nullable=True)  # NEW
    weight_kg = Column(Integer, nullable=True)  # NEW
    misc_persona = Column(JSONB, default=dict, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    user = relationship("User", back_populates="persona")

# ─────────────────────────────────────────────
# CONVERSATIONS
# ─────────────────────────────────────────────
class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phase = Column(String, nullable=False, default="persona", index=True)
    summary = Column(Text, nullable=True)  # Long-term memory summary
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    user = relationship("User", back_populates="conversations")
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

# ─────────────────────────────────────────────
# MESSAGES
# ─────────────────────────────────────────────
class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    conversation = relationship("Conversation", back_populates="messages")

# ─────────────────────────────────────────────
# GUARDRAIL VIOLATIONS
# ─────────────────────────────────────────────
class ViolationLog(Base):
    __tablename__ = "violation_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    intent_type = Column(String, nullable=False)
    count = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "conversation_id",
            "intent_type",
            name="uq_violation_user_convo_intent",
        ),
        Index("idx_violation_lookup", "user_id", "intent_type"),
    )
