# GitHub Actions production deployment

Production deployments use this path:

`main push -> GitHub Actions -> restricted SSH key -> server deploy wrapper -> deploy/deploy.sh`

The production server currently uses `/opt/wenheng-production`. Secrets remain
outside the checkout in `/opt/wenheng-secrets/production.env`; the server-only
Compose override remains in `/opt/wenheng-secrets/compose.server.yaml`.

## Required GitHub production secrets

Add these under **Settings -> Environments -> production -> Environment secrets**:

- `ALIYUN_HOST`: production server host or IP.
- `ALIYUN_SSH_PORT`: SSH port, normally `22`.
- `ALIYUN_SSH_USER`: restricted deployment user.
- `ALIYUN_SSH_PRIVATE_KEY`: complete private half of the dedicated Actions key.
- `ALIYUN_SSH_KNOWN_HOSTS`: verified OpenSSH known-hosts line for the server.

Do not add application API keys, database passwords, or `production.env` to
GitHub. They are read only from the production server.

## Deployment safety

- The workflow deploys only the exact commit that triggered the `main` push.
- A server lock prevents overlapping deployments.
- A dirty server checkout stops deployment instead of overwriting local files.
- Git updates are fast-forward only.
- Existing containers keep running while new images build.
- Docker layer caching avoids reinstalling unchanged Python and npm dependencies.
- Before backend migrations, a PostgreSQL custom-format backup is created and
  verified under `/opt/backups/wenheng/<timestamp>/`.
- If replacement containers fail their health checks, the previous application
  images are restored. Database migrations are not automatically downgraded;
  production migrations must remain backward compatible.
- `.env` and the server-only Compose override are outside the Git checkout.

## Verifying a deployment

The GitHub Actions run must finish successfully and contain a final line like:

`DEPLOYMENT_OK commit=<40-character commit SHA>`

Then verify both the public home page and `/api/health`. The deployed commit is
also recorded in `/opt/wenheng-secrets/last-deployed-commit`.
