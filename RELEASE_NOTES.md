# Hikma Order Automation v1.0.0-rc1

Release candidate date: 2026-07-25

This is a release candidate for staging validation. It is not a record of a
production deployment or a security certification.

## Completed capabilities

- WhatsApp order parsing with safe parser-failure handling
- Configurable OpenAI or Groq parser provider using the same structured Pydantic contract
- Deterministic business-rule review and required-confirmation gating
- Product matching, strength-conflict blocking, and explicit manual approval
- Excel order generation from a protected company template
- SQLite persistence, idempotent generation, order history, detail, and downloads
- Explicit SMTP email delivery with recipient validation, attempt history, and
  `email_request_id` idempotency
- Read-only order, customer, product-volume, geographic, price-type, and email analytics
- Liveness, readiness, safe request logging, deployment guidance, and manual generated-file cleanup
- Responsive New Order, History, Email, and Analytics interfaces

## Deployment prerequisites

- Python 3.12 or later and Node.js compatible with the locked frontend dependencies
- A protected backend environment file created from `backend/.env.example`
- An explicit HTTPS frontend API origin in `VITE_API_BASE_URL`
- Explicit production CORS origins and allowed hosts
- Durable absolute paths for the SQLite database, generated files, and source workbook
- HTTPS termination and restricted direct access to the backend
- One application worker while SQLite remains in use
- Successful `/api/health/live` and `/api/health/ready` checks
- Completion of every applicable item in `RELEASE_CHECKLIST.md`

## Data protection and backups

Before staging with real operational data or performing any release:

1. Quiesce writes and back up the SQLite database.
2. Back up generated order files and the source workbook as the same versioned set.
3. Record and verify the source workbook SHA-256:
   `730edb4229048a7b7ff6b593749e7b507cfd547936fe7b306637869636f119c8`.
4. Protect the environment file and backups with least-privilege permissions.
5. Complete a restore drill and verify historical downloads before opening access.

## SMTP status

Email delivery is disabled by default. Configure and test SMTP in a controlled
environment before setting `EMAIL_ENABLED=true`. A failed send preserves the order and
generated workbook. A process interruption during an SMTP send can leave an attempt in
`sending`; confirm the outcome in the mailbox or SMTP provider before retrying.

## AI provider configuration

`AI_PROVIDER` selects `openai` or `groq`. OpenAI remains the default. Groq uses the
existing OpenAI Python SDK with its OpenAI-compatible base URL. Provider keys remain
backend-only and missing selected-provider configuration fails safely at parse time.

The release example uses the configurable Groq production model
`openai/gpt-oss-120b`, which supported structured output when this release candidate
was prepared. Groq model availability and deprecations must be reviewed before
deployment; change the model through `GROQ_MODEL`, not source edits.

## Known limitations

- SQLite uses a single-writer concurrency model. Run one backend worker; move to a
  server database before high-concurrency or multi-user operation.
- Product analytics reports ordered and free quantities, order counts, and customer
  reach. Product revenue is unavailable because historical product lines do not store
  unit prices or line values.
- No authentication or role-based authorization is included. Network access must be
  restricted according to the intended deployment environment.
- Email delivery has no scheduled reconciliation for attempts interrupted in the
  `sending` state.
- Generated-file retention cleanup is manual and dry-run by default.
- Automated browser execution was unavailable during final RC audit. Complete the
  desktop, mobile, Arabic, long-order, modal-focus, and overflow checks in the release checklist.
- Groq is OpenAI-compatible but not identical. Its service currently maps
  `temperature=0` to approximately `1e-8`, and model support can change. There is no
  automatic fallback between providers.

## Verification summary

The RC audit ran the full backend test suite, frontend lint and production build,
controlled temporary-data workflow and file-safety checks, SQLite integrity checks,
and a production frontend dependency audit. See the release handoff report for exact
results. Production deployment has not been performed.
