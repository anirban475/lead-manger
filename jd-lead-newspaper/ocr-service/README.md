# Tesseract OCR Standing HTTP Service

Standing HTTP service providing Tesseract OCR extraction for n8n workflows and internal microservices.

## Specifications

- **Bind Address**: `172.21.0.1:5050` (Docker bridge gateway for `amatec-net`)
- **Process Manager**: PM2 (`ocr-service`)
- **Default Languages**: `hin+eng` (Hindi + English)

## Endpoints

### `GET /health`
Returns service status.

Response:
```json
{"service": "ocr-service", "status": "ok"}
```

### `POST /ocr`
Performs OCR extraction on an uploaded image.

#### Parameters:
- `lang` (optional query, form, or JSON param, default: `hin+eng`)

#### Request Formats:
1. **Multipart Form Upload**:
   - Form field `file` or `image` containing image binary.
   - Example:
     ```bash
     curl -X POST http://172.21.0.1:5050/ocr -F "file=@sample.jpg" -F "lang=hin+eng"
     ```
2. **JSON Base64**:
   - Body: `{"image": "<base64_string>", "lang": "hin+eng"}`
   - Example:
     ```bash
     curl -X POST http://172.21.0.1:5050/ocr -H "Content-Type: application/json" -d '{"image": "...", "lang": "hin+eng"}'
     ```

#### Responses:
- **Success (HTTP 200)**:
  ```json
  {
    "text": "Extracted text content...",
    "char_count": 1234
  }
  ```
- **Error (HTTP 400)**:
  ```json
  {
    "error": "Error description"
  }
  ```

## Service Management (PM2)

```bash
# Start service
pm2 start ecosystem.config.js

# View status & logs
pm2 status ocr-service
pm2 logs ocr-service

# Restart
pm2 restart ocr-service

# Save PM2 state for reboot persistence
pm2 save
```
