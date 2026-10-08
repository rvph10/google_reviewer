import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Protocol

import httpx

from app.google.oauth import TokenProvider

ACCOUNTS_URL = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
INFO_URL = "https://mybusinessbusinessinformation.googleapis.com/v1"
V4_URL = "https://mybusiness.googleapis.com/v4"
STARS = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}
FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "fake_gbp.json"


@dataclass
class GbpLocation:
    name: str
    account: str
    title: str
    address: str
    website: str


@dataclass
class GbpReview:
    name: str
    review_id: str
    reviewer: str
    stars: int
    comment: str
    created_at: datetime | None
    reply: str


class GbpClient(Protocol):
    def list_locations(self) -> list[GbpLocation]: ...
    def list_reviews(self, account: str, location: str) -> Iterator[GbpReview]: ...
    def put_reply(self, review_name: str, comment: str) -> None: ...


def parse_location(account: str, raw: dict) -> GbpLocation:
    addr = raw.get("storefrontAddress") or {}
    parts = [*addr.get("addressLines", []), addr.get("postalCode", ""), addr.get("locality", "")]
    return GbpLocation(
        name=raw["name"],
        account=account,
        title=raw.get("title", ""),
        address=", ".join(p for p in parts if p),
        website=raw.get("websiteUri", ""),
    )


def parse_review(raw: dict) -> GbpReview:
    created = raw.get("createTime")
    return GbpReview(
        name=raw["name"],
        review_id=raw["reviewId"],
        reviewer=(raw.get("reviewer") or {}).get("displayName", ""),
        stars=STARS.get(raw.get("starRating", ""), 0),
        comment=raw.get("comment", ""),
        created_at=datetime.fromisoformat(created.replace("Z", "+00:00")) if created else None,
        reply=(raw.get("reviewReply") or {}).get("comment", ""),
    )


class LiveGbpClient:
    def __init__(self, tokens: TokenProvider):
        self._tokens = tokens
        self._http = httpx.Client(timeout=30)

    def _get(self, url: str, params: dict | None = None) -> dict:
        resp = self._http.get(url, params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._tokens.access_token()}"}

    def _paginate(self, url: str, key: str, params: dict) -> Iterator[dict]:
        params = dict(params)
        while True:
            data = self._get(url, params)
            yield from data.get(key, [])
            if not data.get("nextPageToken"):
                return
            params["pageToken"] = data["nextPageToken"]

    def list_locations(self) -> list[GbpLocation]:
        result = []
        for account in self._paginate(ACCOUNTS_URL, "accounts", {"pageSize": 20}):
            params = {"pageSize": 100, "readMask": "name,title,storefrontAddress,websiteUri"}
            for raw in self._paginate(f"{INFO_URL}/{account['name']}/locations", "locations", params):
                result.append(parse_location(account["name"], raw))
        return result

    def list_reviews(self, account: str, location: str) -> Iterator[GbpReview]:
        url = f"{V4_URL}/{account}/{location}/reviews"
        for raw in self._paginate(url, "reviews", {"pageSize": 50}):
            yield parse_review(raw)

    def put_reply(self, review_name: str, comment: str) -> None:
        resp = self._http.put(f"{V4_URL}/{review_name}/reply", json={"comment": comment}, headers=self._headers())
        resp.raise_for_status()


class FakeGbpClient:
    """In-memory stand-in used until Google approves API access."""

    def __init__(self, path: Path = FIXTURES):
        self._data = json.loads(path.read_text())

    def list_locations(self) -> list[GbpLocation]:
        return [parse_location(loc["account"], loc) for loc in self._data["locations"]]

    def list_reviews(self, account: str, location: str) -> Iterator[GbpReview]:
        for loc in self._data["locations"]:
            if loc["name"] == location:
                for raw in loc["reviews"]:
                    yield parse_review(raw)

    def put_reply(self, review_name: str, comment: str) -> None:
        for loc in self._data["locations"]:
            for raw in loc["reviews"]:
                if raw["name"] == review_name:
                    raw["reviewReply"] = {"comment": comment}
                    return
        raise KeyError(review_name)
