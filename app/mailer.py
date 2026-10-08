import logging

import httpx

from app.config import get_settings
from app.crypto import sign
from app.models import Review

log = logging.getLogger(__name__)
RESEND_URL = "https://api.resend.com/emails"


def review_link(review: Review) -> str:
    return f"{get_settings().base_url.rstrip('/')}/r/{sign(review.id, 'review')}"


def send(subject: str, body: str) -> None:
    s = get_settings()
    if not s.resend_api_key:
        log.info("Email not sent (Resend not configured): %s\n%s", subject, body)
        return
    resp = httpx.post(
        RESEND_URL,
        headers={"Authorization": f"Bearer {s.resend_api_key}"},
        json={"from": s.mail_from, "to": [a.strip() for a in s.mail_to.split(",")], "subject": subject, "text": body},
        timeout=30,
    )
    resp.raise_for_status()


def _review_block(review: Review) -> str:
    lines = [f"{review.stars} star(s), {review.reviewer or 'anonymous'}:", review.comment or "(no text)", ""]
    if review.risk_reason:
        lines += [f"Flagged: {review.risk_reason}", ""]
    lines += ["Suggested reply:", review.draft, "", f"Review and post: {review_link(review)}"]
    return "\n".join(lines)


def notify_review(review: Review) -> None:
    subject = f"[{review.location.title}] {review.stars} star review needs approval"
    send(subject, _review_block(review))


def notify_backfill(location_title: str, reviews: list[Review]) -> None:
    subject = f"[{location_title}] {len(reviews)} older reviews need approval"
    blocks = [f"[{i}/{len(reviews)}] {_review_block(r)}" for i, r in enumerate(reviews, 1)]
    send(subject, "\n\n---\n\n".join(blocks))


def notify_new_location(title: str, url: str) -> None:
    send(f"New location available: {title}", f"{title} is now accessible. Configure and enable it here:\n{url}")
