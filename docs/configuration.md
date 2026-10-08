# Configuration

All settings are environment variables. Locally they are read from `.env`.

| Variable | Default | Description |
| --- | --- | --- |
| `BASE_URL` | `http://localhost:8000` | Public URL, used for OAuth redirects and email links |
| `DATABASE_URL` | `sqlite:///./reviewer.db` | SQLAlchemy URL. `postgres://` URLs are accepted |
| `SECRET_KEY` | required | Signs approval links and OAuth state |
| `ENCRYPTION_KEY` | required | Fernet key that encrypts the Google refresh token |
| `ADMIN_USER` | `admin` | Dashboard login |
| `ADMIN_PASSWORD` | required | Dashboard password |
| `GOOGLE_CLIENT_ID` | | OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | | OAuth client secret |
| `GBP_MODE` | `fake` | `fake` uses fixtures, `live` calls Google |
| `ANTHROPIC_API_KEY` | | Claude API key |
| `ANTHROPIC_WORKSPACE_ID` | | Required when the API key is not scoped to a workspace |
| `CLAUDE_MODEL` | `claude-haiku-5-5` | Model used for drafts |
| `CLAUDE_EFFORT` | `medium` | `low`, `medium` or `high` |
| `RESEND_API_KEY` | | Resend API key. Without it emails are only logged |
| `MAIL_FROM` | | Sender, on a domain verified in Resend |
| `MAIL_TO` | | Recipients, comma separated |
| `SCHEDULER_ENABLED` | `true` | Disable to only run cycles manually |
| `POLL_MINUTES` | `15` | Interval between cycles |
| `AUTO_POST_ENABLED` | `true` | Global switch. When `false`, every reply needs approval |
| `AUTO_POST_MIN_STARS` | `4` | Minimum rating posted without approval |
| `BACKFILL_PER_HOUR` | `6` | Maximum backfill replies posted per location per hour |
