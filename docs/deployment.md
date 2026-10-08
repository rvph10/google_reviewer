# Deployment

Production runs on the `upintown` VPS through Coolify at `https://reviews.lab.upintown.dev`.

## Coolify

1. Push this repository to a Git provider connected to Coolify.
2. Create a new resource of type **Docker Compose** and select `docker-compose.yml`.
3. Set the domain of the `app` service to `https://reviews.lab.upintown.dev` (port 8000).
4. Fill the environment variables listed in [configuration.md](configuration.md), plus `POSTGRES_PASSWORD`.
5. Point the DNS record `reviews.lab.upintown.dev` to the VPS and deploy.

Coolify's Traefik proxy handles TLS.

## Notes

- Run a single app instance. The scheduler runs inside the process and would run twice with more replicas.
- The schema is created on startup. Back up the `pgdata` volume before upgrades that change models.
- `ENCRYPTION_KEY` must stay the same across deploys, otherwise the stored Google token cannot be read and Google must be reconnected.
