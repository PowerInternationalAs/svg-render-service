# Deployment Guide

This document describes how the `svg-render-service` is built and deployed to Google Cloud Run using the repository’s Dockerfile and Cloud Build triggers.

## Prerequisites

- Project: `powergcp-prod-omnichannel`
- Artifact Registry or Container Registry location (example below uses `gcr.io`)
- Cloud Run API and Cloud Build API enabled
- Cloud Build service account granted:
  - `roles/run.admin`
  - `roles/iam.serviceAccountUser` on the Cloud Run runtime service account
  - `roles/storage.admin` on the target bucket if deploying infrastructure through build steps
- Runtime service account requires:
  - `roles/storage.objectAdmin` on `gs://svg-render-service`
  - `roles/secretmanager.secretAccessor` on secret `svg-render-service-api-key`

## Build & Deploy Pipeline

1. **Repository Trigger**  
   Create a Cloud Build trigger connected to GitHub (`PowerInternationalAs/svg-render-service`), watching the `main` branch. Configure it to use the repository’s `Dockerfile` with build context `/`.

2. **Build Step**  
   Cloud Build automatically runs:
   ```bash
   gcloud builds submit --tag gcr.io/powergcp-prod-omnichannel/svg-render-service
   ```

3. **Deploy Step**  
   Add a deploy step (Cloud Build or separate automation):
   ```bash
   gcloud run deploy svg-render-service \
     --image gcr.io/powergcp-prod-omnichannel/svg-render-service \
     --project powergcp-prod-omnichannel \
     --region europe-north1 \
     --allow-unauthenticated \
     --set-env-vars "BUCKET_NAME=svg-render-service" \
     --set-secrets "API_KEY=svg-render-service-api-key:latest"
   ```

4. **Post-Deploy Verification**
   - `gcloud run services describe svg-render-service --region europe-north1`
   - Hit `/healthz` endpoint to confirm startup.

## Local Testing Workflow

```bash
docker build -t svg-render-service:local .
docker run --rm -p 8080:8080 \
  -e API_KEY=local-key \
  -e BUCKET_NAME=svg-render-service \
  -v "$HOME/.config/gcloud:/root/.config/gcloud" \
  svg-render-service:local
```

## Rotating Secrets

1. Add a new secret version:
   ```bash
   printf '<new-key>' | gcloud secrets versions add svg-render-service-api-key --data-file=-
   ```
2. (Optional) Disable or destroy older versions:
   ```bash
   gcloud secrets versions disable 1 --secret=svg-render-service-api-key
   ```
3. No Cloud Run restart required; redeploy only if you change the secret reference.

## Disaster Recovery Notes

- Redeploy by rebuilding the container and running the deploy command above.
- Bucket pruning occurs per request; use `gsutil rm gs://svg-render-service/renders/*` for manual cleanup.
- If Cloud Run build fails, review Cloud Build logs from the trigger run.

