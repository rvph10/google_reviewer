# Google Reviewer

Internal tool that replies to Google Business Profile reviews for every client profile managed by the agency account.

- **New client:** all existing unanswered reviews are answered, a few per hour.
- **New review:** a reply is drafted within one polling cycle.
- **Negative or sensitive review:** the draft is emailed for approval instead of being posted.

Replies are written by Claude in the language of the review (French, Dutch, English) using a per client profile: services, city, signature, contact and tone.

## How it works

1. The app polls the Business Profile API every 15 minutes with one agency Google account.
2. New locations are discovered automatically and stay disabled until configured.
3. Each unanswered review gets a draft from Claude.
4. Drafts for 4 and 5 star reviews are posted automatically. Everything else, and anything Claude flags as risky, is emailed with a link to approve, edit, regenerate or skip.

See [docs/architecture.md](docs/architecture.md) for details.

## Quick start

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

```sh
cp .env.example .env    # fill SECRET_KEY, ENCRYPTION_KEY, ADMIN_PASSWORD
uv sync
uv run uvicorn app.main:app --reload
```

Open http://localhost:8000 and log in with `ADMIN_USER` / `ADMIN_PASSWORD`. With `GBP_MODE=fake` the app uses fixture data from `fixtures/fake_gbp.json`, so it can be tested before Google grants API access.

Generate keys with:

```sh
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"                              # SECRET_KEY
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # ENCRYPTION_KEY
```

Run the tests with `uv run pytest`.

## Documentation

- [Google setup](docs/google-setup.md): Cloud project, OAuth and API access
- [Deployment](docs/deployment.md): Coolify on the VPS
- [Configuration](docs/configuration.md): environment variables
- [Architecture](docs/architecture.md): data flow and review states
- [Reply guidelines](docs/reply-guidelines.md): what the drafts follow and why
