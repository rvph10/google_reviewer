import secrets
import threading
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, select

from app.config import get_settings
from app.crypto import encrypt, sign, unsign
from app.db import SessionLocal
from app.drafting import draft_reply
from app.google import oauth
from app.jobs import audit, gbp_client, publish, recent_replies, run_cycle
from app.mailer import review_link
from app.models import Credential, Location, Review, ReviewStatus

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.globals["review_link"] = review_link
security = HTTPBasic()
router = APIRouter()
EDITABLE = (ReviewStatus.AWAITING_APPROVAL, ReviewStatus.QUEUED, ReviewStatus.FAILED)


def require_admin(creds: HTTPBasicCredentials = Depends(security)) -> None:
    s = get_settings()
    ok_user = secrets.compare_digest(creds.username.encode(), s.admin_user.encode())
    ok_pass = secrets.compare_digest(creds.password.encode(), s.admin_password.encode())
    if not (ok_user and ok_pass):
        raise HTTPException(401, headers={"WWW-Authenticate": "Basic"})


def get_db():
    with SessionLocal() as db:
        yield db


def back_home() -> RedirectResponse:
    return RedirectResponse("/", status_code=303)


@router.get("/healthz")
def healthz():
    return {"ok": True}


@router.get("/", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def dashboard(request: Request, db=Depends(get_db)):
    locations = db.scalars(select(Location).order_by(Location.title)).all()
    counts = {loc.id: Counter(r.status for r in loc.reviews) for loc in locations}
    pending = db.scalars(
        select(Review).where(Review.status.in_([ReviewStatus.AWAITING_APPROVAL, ReviewStatus.FAILED])).order_by(Review.created_at.desc())
    ).all()
    return templates.TemplateResponse(request, "index.html", {
        "credential": db.scalars(select(Credential)).first(),
        "mode": get_settings().gbp_mode,
        "locations": locations,
        "counts": counts,
        "pending": pending,
    })


@router.post("/run", dependencies=[Depends(require_admin)])
def run_now():
    threading.Thread(target=run_cycle, daemon=True).start()
    return back_home()


@router.get("/oauth/start", dependencies=[Depends(require_admin)])
def oauth_start():
    return RedirectResponse(oauth.authorization_url(sign("oauth", "oauth")))


@router.get("/oauth/callback")
def oauth_callback(code: str, state: str, db=Depends(get_db)):
    if unsign(state, "oauth", max_age=600) != "oauth":
        raise HTTPException(400, "Invalid state")
    email, refresh_token = oauth.exchange_code(code)
    db.execute(delete(Credential))
    db.add(Credential(email=email, refresh_token=encrypt(refresh_token)))
    audit(db, "google_connected", detail=email)
    db.commit()
    return back_home()


@router.get("/locations/{location_id}", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def location_form(request: Request, location_id: int, db=Depends(get_db)):
    loc = db.get(Location, location_id) or _not_found()
    return templates.TemplateResponse(request, "location.html", {"loc": loc})


@router.post("/locations/{location_id}", dependencies=[Depends(require_admin)])
async def location_save(request: Request, location_id: int, db=Depends(get_db)):
    loc = db.get(Location, location_id) or _not_found()
    form = await request.form()
    for field in ("business_context", "city", "signature", "contact", "default_language", "banned_phrases"):
        setattr(loc, field, str(form.get(field, "")).strip())
    for field in ("enabled", "auto_post", "formal"):
        setattr(loc, field, form.get(field) == "on")
    audit(db, "location_saved", detail=loc.name)
    db.commit()
    return back_home()


@router.get("/r/{token}", response_class=HTMLResponse)
def review_page(request: Request, token: str, db=Depends(get_db)):
    review = _review_from_token(db, token)
    return templates.TemplateResponse(request, "review.html", {"review": review, "editable": review.status in EDITABLE})


@router.post("/r/{token}", response_class=HTMLResponse)
async def review_action(request: Request, token: str, db=Depends(get_db)):
    review = _review_from_token(db, token)
    if review.status not in EDITABLE:
        raise HTTPException(409, "This review is already handled")
    form = await request.form()
    action, text = form.get("action"), str(form.get("reply", "")).strip()
    message = ""
    if action == "post" and text:
        gbp = gbp_client(db)
        if gbp is None:
            raise HTTPException(503, "No Google account connected")
        message = "Reply posted." if publish(db, gbp, review, text) else f"Posting failed: {review.error}"
    elif action == "regenerate":
        try:
            draft = draft_reply(review.location, review, recent_replies(db, review.location))
        except Exception as exc:
            message = f"Drafting failed: {exc}"
        else:
            review.draft, review.risk_reason = draft.reply, draft.risk_reason
            audit(db, "regenerated", review)
            db.commit()
            message = "New draft generated."
    elif action == "skip":
        review.status = ReviewStatus.SKIPPED
        audit(db, "skipped", review)
        db.commit()
        message = "Review skipped."
    return templates.TemplateResponse(request, "review.html", {
        "review": review, "editable": review.status in EDITABLE, "message": message,
    })


def _review_from_token(db, token: str) -> Review:
    review_id = unsign(token, "review")
    review = db.get(Review, review_id) if isinstance(review_id, int) else None
    return review or _not_found()


def _not_found():
    raise HTTPException(404)
