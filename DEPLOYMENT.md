# Deployment guide

This guide prepares a production-like deployment; it does not claim the application
has been deployed. Run the full verification suite before every release.

The current frozen release candidate is `v1.0.0-rc1`. Review
`RELEASE_NOTES.md` and complete `RELEASE_CHECKLIST.md` before promotion.

## Local development

Backend (Python 3.12+; the current verified environment uses Python 3.14):

```sh
cd backend
python -m venv .venv
./.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
./.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```sh
cd frontend
npm ci
cp .env.example .env
npm run dev
```

## Production backend

Create a dedicated operating-system account and virtual environment, install pinned
release dependencies, and provide a protected environment file readable only by that
account. Start from `backend/.env.example`. Set `APP_ENV=production`, explicit HTTPS
`CORS_ALLOWED_ORIGINS`, explicit `APP_ALLOWED_HOSTS`, durable absolute storage paths,
and real secrets outside source control.

Install runtime dependencies with `./.venv/bin/pip install -r requirements.txt`.
The separate `requirements-dev.txt` adds test-only tooling and is not required on a
production host.

### AI parser provider

The parser supports OpenAI and Groq without changing its API response schema. Select
one provider in the protected backend environment:

```sh
# OpenAI
AI_PROVIDER=openai
OPENAI_API_KEY=REPLACE_FROM_SECRET_STORE
OPENAI_MODEL=gpt-4.1-mini

# Or Groq through its OpenAI-compatible API
AI_PROVIDER=groq
GROQ_API_KEY=REPLACE_FROM_SECRET_STORE
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=openai/gpt-oss-120b
```

Do not configure either key in the frontend or bake it into an image or build artifact.
Only the selected provider's key is required; a parse request fails safely with HTTP
503 when it is missing. The default Groq model above was listed by Groq as a production
model with structured-output support when this release candidate was prepared. Keep
`GROQ_MODEL` environment-configured and review Groq's supported-model and deprecation
documentation before each deployment.

The parser sends `temperature=0` for deterministic extraction. Groq currently converts
zero to approximately `1e-8`. Both providers still pass responses through the same
OpenAI SDK structured parser and `ParsedOrderResponse` Pydantic validation. No automatic
cross-provider fallback occurs: a failed selected provider returns a safe parser error
instead of sending order content to another provider.

From the backend working directory:

```sh
./.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
```

Use one worker with SQLite because it has a single-writer concurrency model. PostgreSQL
is recommended before multi-user or high-concurrency deployment. Terminate HTTPS at a
reverse proxy. Forward only trusted proxy headers and configure the application host
allowlist to the public hostname.

Example systemd unit (replace placeholders during installation):

```ini
[Unit]
Description=Pharmaceutical Order Automation API
After=network.target

[Service]
Type=simple
User=APP_USER
Group=APP_GROUP
WorkingDirectory=/srv/order-automation/backend
EnvironmentFile=/etc/order-automation/backend.env
ExecStart=/srv/order-automation/backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=on-failure
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

## Production frontend

Set `VITE_API_BASE_URL` to the public HTTPS API origin before building:

```sh
cd frontend
npm ci
VITE_API_BASE_URL=https://orders.example.invalid npm run build
```

Serve `frontend/dist` from a static host or reverse proxy. Vite variables are public;
never place passwords, tokens, or private configuration in them.
The default displayed release version is `1.0.0-rc1`; set
`VITE_APP_VERSION=1.0.0-rc1` explicitly in reproducible release builds.

## Reverse proxy

Illustrative Nginx configuration:

```nginx
server {
    listen 443 ssl http2;
    server_name orders.example.invalid;
    client_max_body_size 10m;

    root /srv/order-automation/frontend/dist;
    index index.html;
    location / { try_files $uri /index.html; }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
        proxy_send_timeout 30s;
    }
}
```

Use valid certificates, redirect HTTP to HTTPS, and restrict direct backend access.
Align proxy size/time limits with `MAX_UPLOAD_SIZE_MB` and
`REQUEST_TIMEOUT_SECONDS`. Those settings document deployment limits; the reverse proxy
must enforce them because the current API does not accept general uploads.

## Health checks

- `/api/health/live`: process liveness only
- `/api/health/ready`: database, template, and generated-directory readiness
- `/api/health`: versioned component summary

Health responses deliberately omit paths, connection URLs, and SMTP details.

## Data persistence

Persist and protect:

1. The SQLite file configured by `DATABASE_URL`
2. `GENERATED_ORDERS_DIR`
3. The source workbook configured by `EXCEL_TEMPLATE_PATH`
4. The backend environment file

Paths may be absolute in production. The generated-order cleanup command is manual and
dry-run by default:

```sh
cd backend
./.venv/bin/python -m scripts.cleanup_generated_orders
./.venv/bin/python -m scripts.cleanup_generated_orders --execute
```

Review dry-run output before execution. No cleanup runs at startup or on a schedule.

## Backup and restore

Stop or otherwise quiesce application writes before copying SQLite. Back up the
database, generated orders, source template, and protected configuration as one
versioned set. Prefer SQLite's online backup command when a full stop is unavailable,
then validate the copied database with `PRAGMA integrity_check`.

Record the source workbook SHA-256 with every backup:

```sh
shasum -a 256 "templates/Hikma orders.xlsx"
```

Restore in this order: stop the service, restore the template and verify its hash,
restore the SQLite database, restore generated files, restore protected configuration,
run readiness checks, then start the service. Confirm historical downloads before
reopening traffic.

Protect backups and environment files with least-privilege filesystem permissions.
Rotate SMTP and API credentials after suspected exposure and whenever privileged staff
change. Test explicit email delivery in a controlled environment before enabling
`EMAIL_ENABLED=true`.

## Docker decision

Docker was intentionally not added. The current project has no established container
structure, and an unverified multi-service setup would add volume, workbook, and
frontend build-configuration risk. It remains a future option once durable volume
mounts and release automation can be tested in the target environment.
