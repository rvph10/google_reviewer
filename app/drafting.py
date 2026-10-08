import anthropic
from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.models import Location, Review
from app.text import original_text

SYSTEM_PROMPT = """You write public owner replies to Google reviews on behalf of a local business.

Rules:
- Reply in the language the review is written in. If the review has no text, use the business default language.
- Address the reviewer by first name when a real name is available. Never use a surname alone.
- Refer to at least one specific detail of the review. Never write a reply that could fit any review.
- Be warm, human and conversational. No marketing language, no offers, discounts or promotions.
- You may mention the business service or city once if it fits naturally. Never stuff keywords.
- Never invent facts, policies, names, compensations or events that are not given to you.
- Never disclose private information about the reviewer or argue publicly.
- End with the signature when one is provided.

Length by rating:
- 5 or 4 stars: 1 to 3 sentences. Thank, mention a detail, invite them back.
- 3 stars: 2 to 4 sentences. Thank, acknowledge the issue, say it will be looked into.
- 1 or 2 stars: 3 to 5 sentences. Acknowledge, apologize where it is warranted without admitting fault for things outside the business control, and invite them to continue the conversation offline using the contact provided.
- Rating only, no text: one short thank-you sentence.

Write for future customers who will read the reply, not only for the reviewer.

Set risky to true, with a short reason in English, when the review mentions legal action, health or safety, injury, discrimination, refunds or money disputes, staff misconduct, or looks fake or written by someone who was never a customer. Otherwise set risky to false and leave risk_reason empty."""


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str = Field(description="ISO 639-1 code of the reply language")
    reply: str
    risky: bool
    risk_reason: str


class RefusalError(RuntimeError):
    pass


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key or None)


def business_profile(location: Location) -> str:
    lines = [
        f"Business: {location.title}",
        f"City: {location.city or location.address}",
        f"Default language: {location.default_language}",
        f"Form of address: {'formal (vous, u)' if location.formal else 'informal (tu, je)'}",
        f"Signature: {location.signature or 'none'}",
        f"Contact for complaints: {location.contact or location.website or 'none'}",
    ]
    if location.business_context:
        lines.append(f"About the business: {location.business_context}")
    if location.banned_phrases:
        lines.append(f"Never use these words or phrases: {location.banned_phrases}")
    return "\n".join(lines)


def review_prompt(location: Location, review: Review, avoid: list[str]) -> str:
    text = original_text(review.comment) or "(no text, rating only)"
    parts = [
        "<business>", business_profile(location), "</business>",
        "<review>", f"Reviewer: {review.reviewer or 'anonymous'}", f"Rating: {review.stars}/5", f"Text: {text}", "</review>",
    ]
    if avoid:
        parts += ["<recent_replies>", "Do not reuse the wording or structure of these recent replies:", *avoid, "</recent_replies>"]
    return "\n".join(parts)


def draft_reply(location: Location, review: Review, avoid: list[str]) -> Draft:
    s = get_settings()
    response = _client().messages.parse(
        model=s.claude_model,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": review_prompt(location, review, avoid)}],
        output_format=Draft,
        output_config={"effort": s.claude_effort},
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RefusalError(f"No draft produced (stop_reason={response.stop_reason})")
    return response.parsed_output
