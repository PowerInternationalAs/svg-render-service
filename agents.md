# Agent Notes

- **Service Purpose:** Convert remote SVG files to PNG, enforce minimum width (>=512px), upload to Cloud Storage, return signed URL, prune renders older than 24 hours.
- **Runtime Stack:** Python 3.11, Flask app served by Gunicorn. Conversion handled by CairoSVG; depends on Cairo libraries installed in Dockerfile.
- **Key Files:** `app/main.py` (Flask app & business logic), `app/config.py` (env settings), `Dockerfile`, `requirements.txt`.
- **Environment Requirements:** `API_KEY` (Secret Manager `svg-render-service-api-key`), `BUCKET_NAME` (defaults to `svg-render-service`), optional tunables for timeouts and sizes.
- **Infrastructure:** Cloud Run (managed) in region `europe-north1`, bucket `gs://svg-render-service`, project `powergcp-prod-omnichannel`.
- **Security:** Requests authorized via `X-API-Key` header. Signed URLs generated per render. Runtime service account needs `roles/storage.objectAdmin` + `roles/secretmanager.secretAccessor` + `roles/iam.serviceAccountTokenCreator`.
- **Ops:** Each request triggers pruning of renders older than `PRUNE_AFTER_SECONDS` (24h default). `/healthz` endpoint available for monitoring.
- **Pending Enhancements:** Add automated tests, structured logging, metrics, and consider async pruning or retention policies if bucket traffic grows.

