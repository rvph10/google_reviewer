import uuid

import pytest
from sqlalchemy import select

from app import jobs
from app.db import SessionLocal, init_db
from app.drafting import Draft
from app.google.gbp import FakeGbpClient
from app.models import Location, Review, ReviewStatus


@pytest.fixture
def db(tmp_path, monkeypatch):
    init_db(f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setattr(jobs, "_fake", FakeGbpClient())
    sent = []
    monkeypatch.setattr(jobs.mailer, "send", lambda subject, body: sent.append(subject))

    def fake_draft(location, review, avoid):
        risky = "juridische" in review.comment
        return Draft(language="fr", reply=uuid.uuid4().hex, risky=risky, risk_reason="legal" if risky else "")

    monkeypatch.setattr(jobs, "draft_reply", fake_draft)
    with SessionLocal() as session:
        session.sent = sent
        yield session


def statuses(db, location_name):
    loc = db.scalar(select(Location).where(Location.name == location_name))
    return {r.review_id: r.status for r in loc.reviews}


def test_discovery_does_not_touch_disabled_locations(db):
    jobs.run_cycle()
    db.expire_all()
    assert len(db.scalars(select(Location)).all()) == 2
    assert db.scalars(select(Review)).all() == []
    assert sum("New location" in s for s in db.sent) == 2


def test_backfill_routes_by_rating(db):
    jobs.run_cycle()
    for loc in db.scalars(select(Location)).all():
        loc.enabled = True
    db.commit()
    jobs.run_cycle()
    db.expire_all()

    bakery = statuses(db, "locations/1001")
    assert bakery["r5"] == ReviewStatus.EXTERNAL
    assert bakery["r3"] == ReviewStatus.AWAITING_APPROVAL
    assert {bakery[k] for k in ("r1", "r2", "r4")} == {ReviewStatus.POSTED}

    garage = statuses(db, "locations/1002")
    assert garage["g1"] == ReviewStatus.POSTED
    assert garage["g2"] == ReviewStatus.AWAITING_APPROVAL
    assert garage["g3"] == ReviewStatus.AWAITING_APPROVAL
    assert sum("older reviews need approval" in s for s in db.sent) == 2


def test_backfill_is_rate_limited(db, monkeypatch):
    monkeypatch.setattr(jobs.get_settings(), "backfill_per_hour", 1)
    jobs.run_cycle()
    loc = db.scalar(select(Location).where(Location.name == "locations/1001"))
    loc.enabled = True
    db.commit()
    jobs.run_cycle()
    db.expire_all()
    posted = [s for s in statuses(db, "locations/1001").values() if s == ReviewStatus.POSTED]
    assert len(posted) == 1


def test_route_respects_location_and_risk():
    loc = Location(auto_post=True)
    assert jobs.route(5, False, loc) == ReviewStatus.QUEUED
    assert jobs.route(3, False, loc) == ReviewStatus.AWAITING_APPROVAL
    assert jobs.route(5, True, loc) == ReviewStatus.AWAITING_APPROVAL
    loc.auto_post = False
    assert jobs.route(5, False, loc) == ReviewStatus.AWAITING_APPROVAL


def test_failed_draft_is_retried(db, monkeypatch):
    jobs.run_cycle()
    loc = db.scalar(select(Location).where(Location.name == "locations/1002"))
    loc.enabled = True
    db.commit()
    working = jobs.draft_reply

    def broken(*args):
        raise RuntimeError("API down")

    monkeypatch.setattr(jobs, "draft_reply", broken)
    jobs.run_cycle()
    db.expire_all()
    assert set(statuses(db, "locations/1002").values()) == {ReviewStatus.FAILED}

    monkeypatch.setattr(jobs, "draft_reply", working)
    jobs.run_cycle()
    db.expire_all()
    assert ReviewStatus.FAILED not in statuses(db, "locations/1002").values()
