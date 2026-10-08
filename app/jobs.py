import logging
import threading
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import mailer
from app.config import get_settings
from app.crypto import decrypt
from app.db import SessionLocal
from app.drafting import draft_reply
from app.google.gbp import FakeGbpClient, GbpClient, LiveGbpClient
from app.google.oauth import TokenProvider
from app.models import AuditLog, Credential, Location, Review, ReviewStatus
from app.text import too_similar

log = logging.getLogger(__name__)
_lock = threading.Lock()
_fake: FakeGbpClient | None = None
OPEN_STATUSES = (ReviewStatus.NEW, ReviewStatus.AWAITING_APPROVAL, ReviewStatus.QUEUED, ReviewStatus.FAILED)


def gbp_client(db: Session) -> GbpClient | None:
    global _fake
    if get_settings().gbp_mode == "fake":
        _fake = _fake or FakeGbpClient()
        return _fake
    cred = db.scalars(select(Credential).order_by(Credential.id.desc())).first()
    if cred is None:
        return None
    return LiveGbpClient(TokenProvider(decrypt(cred.refresh_token)))


def audit(db: Session, action: str, review: Review | None = None, detail: str = "") -> None:
    db.add(AuditLog(review_id=review.id if review else None, action=action, detail=detail))


def discover_locations(db: Session, gbp: GbpClient) -> list[Location]:
    new = []
    for item in gbp.list_locations():
        loc = db.scalar(select(Location).where(Location.name == item.name))
        if loc is None:
            loc = Location(name=item.name, account=item.account, title=item.title, city="")
            db.add(loc)
            new.append(loc)
        loc.account, loc.title, loc.address, loc.website = item.account, item.title, item.address, item.website
    db.commit()
    return new


def sync_reviews(db: Session, gbp: GbpClient, loc: Location) -> None:
    backfill = not loc.backfill_done
    for item in gbp.list_reviews(loc.account, loc.name):
        row = db.scalar(select(Review).where(Review.location_id == loc.id, Review.review_id == item.review_id))
        if row is None:
            row = Review(
                location=loc, review_id=item.review_id, name=item.name, reviewer=item.reviewer,
                stars=item.stars, comment=item.comment, created_at=item.created_at, backfill=backfill,
                status=ReviewStatus.EXTERNAL if item.reply else ReviewStatus.NEW, reply=item.reply,
            )
            db.add(row)
        elif item.reply and row.status in OPEN_STATUSES:
            row.status, row.reply = ReviewStatus.EXTERNAL, item.reply
            audit(db, "replied_elsewhere", row)
    loc.backfill_done = True
    db.commit()


def recent_replies(db: Session, loc: Location, limit: int = 10) -> list[str]:
    rows = db.scalars(
        select(Review)
        .where(Review.location_id == loc.id, (Review.reply != "") | (Review.draft != ""))
        .order_by(Review.id.desc())
        .limit(limit)
    )
    return [r.reply or r.draft for r in rows]


def route(stars: int, risky: bool, loc: Location) -> str:
    s = get_settings()
    if risky or not (s.auto_post_enabled and loc.auto_post):
        return ReviewStatus.AWAITING_APPROVAL
    return ReviewStatus.QUEUED if stars >= s.auto_post_min_stars else ReviewStatus.AWAITING_APPROVAL


def draft_new(db: Session, loc: Location) -> None:
    retry = (Review.status == ReviewStatus.FAILED) & (Review.draft == "")
    to_draft = select(Review).where(Review.location_id == loc.id, (Review.status == ReviewStatus.NEW) | retry)
    for review in db.scalars(to_draft).all():
        avoid = recent_replies(db, loc)
        try:
            draft = draft_reply(loc, review, avoid)
            if too_similar(draft.reply, avoid):
                draft = draft_reply(loc, review, avoid)
                if too_similar(draft.reply, avoid):
                    draft.risky, draft.risk_reason = True, "Draft is very similar to a recent reply"
        except Exception as exc:
            log.exception("Drafting failed for review %s", review.id)
            review.status, review.error = ReviewStatus.FAILED, str(exc)
            audit(db, "draft_failed", review, str(exc))
            db.commit()
            continue
        review.draft, review.language, review.risk_reason = draft.reply, draft.language, draft.risk_reason
        review.status, review.error = route(review.stars, draft.risky, loc), ""
        audit(db, "drafted", review, review.status)
        db.commit()


def publish(db: Session, gbp: GbpClient, review: Review, text: str) -> bool:
    try:
        gbp.put_reply(review.name, text)
    except Exception as exc:
        log.exception("Posting failed for review %s", review.id)
        review.status, review.error = ReviewStatus.FAILED, str(exc)
        audit(db, "post_failed", review, str(exc))
        db.commit()
        return False
    review.status, review.reply, review.error = ReviewStatus.POSTED, text, ""
    review.posted_at = datetime.now(UTC)
    audit(db, "posted", review, text)
    db.commit()
    return True


def post_queued(db: Session, gbp: GbpClient) -> None:
    limit = get_settings().backfill_per_hour
    since = datetime.now(UTC) - timedelta(hours=1)
    queued = db.scalars(select(Review).where(Review.status == ReviewStatus.QUEUED).order_by(Review.created_at)).all()
    for review in queued:
        if review.backfill:
            posted = db.scalar(select(func.count()).select_from(Review).where(
                Review.location_id == review.location_id, Review.backfill, Review.posted_at >= since,
            ))
            if posted >= limit:
                continue
        publish(db, gbp, review, review.draft)


def _send(fn, *args) -> bool:
    try:
        fn(*args)
        return True
    except Exception:
        log.exception("Email failed")
        return False


def notify_pending(db: Session) -> None:
    pending = db.scalars(select(Review).where(
        Review.status == ReviewStatus.AWAITING_APPROVAL, Review.notified.is_(False),
    )).all()
    backfill: dict[int, list[Review]] = defaultdict(list)
    for review in pending:
        if review.backfill:
            backfill[review.location_id].append(review)
            continue
        if _send(mailer.notify_review, review):
            review.notified = True
            db.commit()
    for reviews in backfill.values():
        if not _send(mailer.notify_backfill, reviews[0].location.title, reviews):
            continue
        for review in reviews:
            review.notified = True
        db.commit()


def run_cycle() -> None:
    if not _lock.acquire(blocking=False):
        log.info("Cycle already running")
        return
    try:
        with SessionLocal() as db:
            gbp = gbp_client(db)
            if gbp is None:
                log.info("No Google account connected, skipping cycle")
                return
            base = get_settings().base_url.rstrip("/")
            for loc in discover_locations(db, gbp):
                _send(mailer.notify_new_location, loc.title, f"{base}/locations/{loc.id}")
            for loc in db.scalars(select(Location).where(Location.enabled)).all():
                try:
                    sync_reviews(db, gbp, loc)
                    draft_new(db, loc)
                except Exception:
                    db.rollback()
                    log.exception("Cycle failed for %s", loc.title)
            notify_pending(db)
            post_queued(db, gbp)
    finally:
        _lock.release()
