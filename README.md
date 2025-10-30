# SVG Render Service

Cloud Run service that downloads an SVG from a provided URL, renders it to PNG with a minimum width of 512 pixels, stores the result in Google Cloud Storage, and returns a signed URL for temporary access. Each invocation prunes PNGs older than 24 hours to keep the bucket tidy.

## Prerequisites

- Google Cloud project: `powergcp-prod-omnichannel`
- Storage bucket: `gs://svg-render-service` (created in `europe-north1`)
- Service account or user with permission to:
  - Read from the SVG source URL (public internet)
  - `storage.objects.create`, `storage.objects.get`, `storage.objects.delete` on the bucket
  - `iam.serviceAccounts.signBlob` or equivalent for signed URLs
- API key you supply via the `API_KEY` environment variable
- For local execution: Python 3.11, Cairo system libraries (installed via the Docker image or package manager), and Google Cloud credentials (`gcloud auth application-default login` or `GOOGLE_APPLICATION_CREDENTIALS`)

## Configuration

Environment variables consumed by the service:

| Variable | Description | Default |
| --- | --- | --- |
| `API_KEY` | Required API key expected in the `X-API-Key` header. | _None (required)_ |
| `BUCKET_NAME` | Target bucket for PNG uploads. | `svg-render-service` |
| `SIGNED_URL_TTL_SECONDS` | Lifetime of signed URLs. | `3600` (1 hour) |
| `PRUNE_AFTER_SECONDS` | Age threshold for pruning PNGs. | `86400` (24 hours) |
| `MIN_OUTPUT_WIDTH` | Minimum rendered width in pixels. | `512` |
| `MAX_OUTPUT_WIDTH` | Upper bound on rendered width in pixels. | `4096` |
| `MAX_OUTPUT_HEIGHT` | Upper bound on rendered height in pixels. | `4096` |
| `MAX_SVG_BYTES` | Maximum downloaded SVG size (bytes). | `5242880` (5 MiB) |
| `SVG_FETCH_TIMEOUT_SECONDS` | Timeout for fetching the remote SVG. | `10` |

## Running Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
export API_KEY="set-a-strong-key"
export BUCKET_NAME="svg-render-service"
python3 -m app.main
```

Send a request:

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d '{"svg_url": "https://example.com/sample.svg"}' \
  http://localhost:8080/render
```

## Building the Container

```bash
gcloud builds submit \
  --tag gcr.io/powergcp-prod-omnichannel/svg-render-service
```

## Deploying to Cloud Run

```bash
gcloud run deploy svg-render-service \
  --image gcr.io/powergcp-prod-omnichannel/svg-render-service \
  --project powergcp-prod-omnichannel \
  --region europe-north1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars API_KEY="set-a-strong-key",BUCKET_NAME="svg-render-service"
```

Update the Cloud Run service's `API_KEY` value whenever you rotate credentials. The endpoint expects the key in the `X-API-Key` header.

## API

`POST /render`

- Header: `X-API-Key`
- Body:

```json
{
  "svg_url": "https://example.com/sample.svg"
}
```

### Responses

- `200 OK`:

```json
{
  "png_url": "https://storage.googleapis.com/...",
  "object_name": "renders/<uuid>.png",
  "dimensions": {
    "width": 512,
    "height": 320
  },
  "pruned_files": 3
}
```

- `400 Bad Request`: validation or fetch error
- `401 Unauthorized`: missing or incorrect API key
- `500 Internal Server Error`: unexpected failures during render or upload

## Maintenance Notes

- PNG files older than 24 hours are deleted after each render request; you can tune `PRUNE_AFTER_SECONDS` if needed.
- Signed URLs default to a 1‑hour lifetime; adjust `SIGNED_URL_TTL_SECONDS` to change expiry.
- Monitor Cloud Run logs for entries from the `svg-render-service` logger to track pruning or conversion issues.

