# Architecture

A single FastAPI process with an in-process scheduler and a Postgres database.

```
app/
  main.py         app startup and scheduler
  jobs.py         polling cycle: discover, sync, draft, notify, post
  drafting.py     Claude prompt and structured output
  google/oauth.py OAuth code exchange and token refresh
  google/gbp.py   Business Profile API client and fake client
  mailer.py       Resend emails
  web.py          dashboard, location settings, approval pages
  text.py         translation stripping and similarity check
```

## Cycle

Every `POLL_MINUTES`:

1. **Discover:** list all locations the agency account manages. New ones are saved disabled and announced by email.
2. **Sync:** for enabled locations, fetch reviews. On the first sync every review is marked as backfill.
3. **Draft:** each new review without a reply gets a Claude draft and is routed.
4. **Notify:** reviews awaiting approval are emailed. Backfill reviews are grouped in one email per location.
5. **Post:** queued replies are posted. Backfill replies respect `BACKFILL_PER_HOUR`.

## Review states

| State | Meaning |
| --- | --- |
| `new` | Synced, not drafted yet |
| `queued` | Will be posted automatically |
| `awaiting_approval` | Emailed, waiting for a decision |
| `posted` | Reply published by the app |
| `external` | Already answered outside the app |
| `skipped` | Dismissed manually |
| `failed` | Drafting or posting failed, see the error on the review page |

## Routing

A draft needs approval when any of these is true:

- rating below `AUTO_POST_MIN_STARS`
- Claude flags the review as risky (legal, health, refunds, fake review, and similar)
- the draft is too similar to a recent reply, even after one retry
- auto-post is disabled for the location or globally

## Security

- The dashboard uses HTTP Basic auth.
- Approval links are signed and expire after 30 days. Anyone holding a link can act on that single review, so do not forward the emails.
- The Google refresh token is encrypted at rest.
