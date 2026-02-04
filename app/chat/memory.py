from app.core.openai_client import chat_completion

def summarize_messages(messages):
    text = "\n".join([f"{m.role}: {m.content}" for m in messages])

    prompt = f"""
Summarize this conversation into short memory notes
that help continue the conversation naturally.

Keep it factual, neutral, and compact.
Do not include advice.

Conversation:
{text}
"""

    summary = chat_completion([
        {"role": "system", "content": "You create compact conversation memory."},
        {"role": "user", "content": prompt}
    ])

    return summary.strip() if summary else ""
