# Operations Runbook

## Service Overview

- **Name:** `svg-render-service`
- **Platform:** Google Cloud Run (Managed)
- **Purpose:** Convert SVGs referenced by URL into PNG files, store them in Cloud Storage, return signed URLs, and prune rendered images older than 24 hours.

## Key Dependencies

- Storage bucket `gs://svg-render-service`
- Secret Manager secret `svg-render-service-api-key`
- CairoSVG, Flask, Google Cloud Storage client libraries

## Runtime Configuration

- `API_KEY` (required): Provided via Secret Manager (`svg-render-service-api-key:latest`)
- `BUCKET_NAME`: Must remain `svg-render-service` unless the bucket is renamed; update env var accordingly.
- Optional overrides: `MIN_OUTPUT_WIDTH`, `MAX_SVG_BYTES`, `PRUNE_AFTER_SECONDS`, `SIGNED_URL_TTL_SECONDS`

## Health & Monitoring

- **Health endpoint:** `GET /healthz` (returns `{ "status": "ok" }`)
- **Common Logs:** Look for `Rendering failed` and `Pruning stale object` messages in Cloud Logging.
- **Metrics:** Cloud Run automatically tracks request latency, error rate, CPU, and memory usage.

## Failure Scenarios

| Symptom | Likely Cause | Action |
| --- | --- | --- |
| 401 responses | Missing/incorrect API key | Validate `X-API-Key` header and secret version. |
| 400 responses with size errors | SVG too large or empty | Confirm `MAX_SVG_BYTES` and SVG source. |
| 500 responses during conversion | CairoSVG or GCS failure | Check Cloud Logging; redeploy or investigate service account permissions. |
| Signed URL fails | Secret missing `signBlob` rights | Ensure Cloud Run service account has `roles/iam.serviceAccountTokenCreator`. |

## Maintenance Tasks

- **Pruning**: Automatic per request; manual cleanup via `gsutil -m rm gs://svg-render-service/renders/**` if needed.
- **Secret Rotation**: Add new secret versions and update any referencing documentation.
- **Dependency Updates**: Modify `requirements.txt`, rebuild container, redeploy.

## Incident Response

1. Check Cloud Run logs for detailed stack traces.
2. Validate Cloud Storage availability and permissions.
3. Re-run the deployment command if configuration drift is suspected.
4. Escalate to the GCP administrator if IAM or billing issues arise.

