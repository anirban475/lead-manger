# PayPerWA API Documentation

Send WhatsApp messages, manage contacts and templates, run campaigns, and receive delivery webhooks through the PayPerWA REST API. Authenticate with your API key and start sending in minutes. No BSP markup, just ₹0.20 per message plus Meta's standard charges.

**Source:** https://payperwa.com/docs

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Authentication](#2-authentication)
3. [Rate Limits](#3-rate-limits)
4. [Channels (Multi-WABA)](#4-channels-multi-waba)
5. [Send Message](#5-send-message)
6. [Contacts](#6-contacts)
7. [Templates](#7-templates)
8. [Campaigns](#8-campaigns)
9. [Wallet / Balance](#9-wallet--balance)
10. [Webhooks](#10-webhooks)
11. [Error Codes](#11-error-codes)
12. [Permissions](#12-permissions)

---

## 1. Getting Started

The PayPerWA API lets you send WhatsApp messages, manage contacts, templates, and campaigns programmatically. All endpoints use the `/api/v1` prefix and require API key authentication.

### Base URL

```
https://payperwa.com/api/v1
```

### Response Format

All responses follow a consistent JSON format.

```json
// Success
{
  "success": true,
  "data": { ... }
}

// Error
{
  "success": false,
  "error": "Human-readable error message"
}
```

---

## 2. Authentication

Include your API key in the `Authorization` header as a Bearer token with every request.

```
Authorization: Bearer ppw_live_sk_your_key_here
```

Generate your API key in **Dashboard → Settings → API tab** (https://payperwa.com/dashboard/settings). You can create up to 5 keys per account. Keys are shown only once at creation time, so store them safely.

### Quick Example — Check Balance

```bash
curl https://payperwa.com/api/v1/balance \
  -H "Authorization: Bearer ppw_live_sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
```

---

## 3. Rate Limits

Each API key has a configurable rate limit (default: **100 requests per minute**). Exceeding this limit returns a `429` status code. Wait and retry after a few seconds.

| Plan                          | Rate Limit                  |
| ----------------------------- | --------------------------- |
| Default                       | 100 requests/minute per key |
| Custom (configurable per key) | 10 to 1,000 requests/minute |

---

## 4. Channels (Multi-WABA)

If your account has more than one connected WhatsApp Business Account (WABA), for example separate numbers for Sales and Support, every API call can be scoped to a specific channel. Pass the channel ID via the `X-Channel-Id` header. If omitted, the request runs against your **primary channel**.

### How to specify a channel

Three options, in resolution order:

1. `X-Channel-Id` HTTP header (recommended)
2. `channelId` in the request body (POST/PUT only)
3. `?channelId=` query parameter (GET only)

### Where it applies

| Endpoint              | Effect of `X-Channel-Id`                                                |
| --------------------- | ----------------------------------------------------------------------- |
| `POST /messages/send` | Sends from that channel's phone number; template must be approved on it |
| `GET /contacts`       | Filters list to contacts on that channel only                           |
| `POST /contacts`      | Creates / upserts the contact under that channel                        |
| `GET /templates`      | Filters templates to that channel                                       |
| `GET /campaigns`      | Filters campaigns to that channel                                       |
| `GET /balance`        | Not used. Wallet is shared across all channels                          |

### Example — Send from a specific channel

```bash
curl -X POST https://payperwa.com/api/v1/messages/send \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "X-Channel-Id: ch_550e8400e29b41d4a716446655440000" \
  -H "Content-Type: application/json" \
  -d '{
    "to": "919876543210",
    "template_name": "order_confirmation",
    "variables": ["Rahul", "ORD-4521"]
  }'
```

Find your channel IDs in **Dashboard → Settings → Channels**. Sending an invalid or unauthorized channel ID returns `400 Invalid channelId`.

---

## 5. Send Message

```
POST /api/v1/messages/send
```

Send a single WhatsApp message using an approved template. The cost (Meta fee + ₹0.20 platform fee) is deducted from your wallet balance.

**Permission required:** `messages:send`

### Request Body

```json
{
  "to": "919876543210",
  "template_name": "order_confirmation",
  "language": "en",
  "variables": ["Rahul", "ORD-4521", "₹1,299"]
}
```

| Field           | Type     | Required | Description                                        |
| --------------- | -------- | -------- | -------------------------------------------------- |
| `to`            | string   | Yes      | Phone number with country code (e.g. 919876543210) |
| `template_name` | string   | Yes      | Name of your approved template                     |
| `language`      | string   | No       | Template language code (default: "en")             |
| `variables`     | string[] | No       | Template variable values in order                  |

### Sending an OTP / Login Code

For an `AUTHENTICATION` template, pass the one-time code as the **first value** in `variables`. PayPerWA automatically fills both the message body and the copy/autofill button with that same code.

```json
{
  "to": "919876543210",
  "template_name": "login",
  "variables": ["483920"]
}
```

### Response

```json
{
  "success": true,
  "data": {
    "message_id": "wamid.HBgLMTIzNDU2Nzg5MA==",
    "status": "sent",
    "cost": {
      "meta_fee": 0.86,
      "platform_fee": 0.20,
      "total": 1.06
    }
  }
}
```

### Example

```bash
curl -X POST https://payperwa.com/api/v1/messages/send \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "to": "919876543210",
    "template_name": "order_confirmation",
    "language": "en",
    "variables": ["Rahul", "ORD-4521", "₹1,299"]
  }'
```

---

## 6. Contacts

### List Contacts

```
GET /api/v1/contacts
```

List all contacts with optional pagination and search.

**Permission:** `contacts:read`

#### Query Parameters

| Param      | Default | Description              |
| ---------- | ------- | ------------------------ |
| `page`     | 1       | Page number              |
| `pageSize` | 50      | Items per page (max 100) |
| `search`   | -       | Search by name or phone  |

#### Response

```json
{
  "success": true,
  "data": {
    "contacts": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Rahul Sharma",
        "phone": "+919876543210",
        "email": "rahul@example.com",
        "optedIn": true,
        "tags": ["customer", "delhi"],
        "createdAt": "2026-01-15T10:30:00.000Z"
      }
    ],
    "total": 1250,
    "page": 1,
    "pageSize": 50
  }
}
```

#### Example

```bash
curl "https://payperwa.com/api/v1/contacts?page=1&pageSize=50" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Create or Update Contact (Upsert)

```
POST /api/v1/contacts
```

Create a contact, or update it if the phone already exists on the same channel (upsert). Tags are auto-created if they don't exist. Returns `201` on create and `200` on update; the response includes a `created` boolean so you can branch.

**Permission:** `contacts:write`

#### Body Fields

| Field      | Type     | Required | Description                                                                                      |
| ---------- | -------- | -------- | ------------------------------------------------------------------------------------------------ |
| `name`     | string   | Yes      | Contact display name (1-100 chars)                                                               |
| `phone`    | string   | Yes      | Phone number; auto-normalized to E.164                                                           |
| `email`    | string   | No       | Optional email                                                                                   |
| `optedIn`  | boolean  | No       | Default `true`                                                                                   |
| `tags`     | string[] | No       | Tag names. New names are auto-created on your account                                            |
| `upsert`   | boolean  | No       | Default `true`. Set `false` to fail with `409` if the phone already exists                       |
| `tagsMode` | string   | No       | `"merge"` (default) keeps existing tags and adds new ones; `"replace"` wipes existing tags first |

Soft-deleted contacts are reactivated automatically when the same phone is upserted again, so there is no need to handle that case separately.

#### Request and Response

```json
// Request — create or update by phone, merge tags
{
  "name": "Priya Patel",
  "phone": "9123456789",
  "email": "priya@example.com",
  "tags": ["lead", "mumbai"]
}

// Response — 201 Created (new) or 200 OK (updated)
{
  "success": true,
  "created": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "name": "Priya Patel",
    "phone": "+919123456789",
    "email": "priya@example.com",
    "optedIn": true,
    "tags": ["lead", "mumbai"],
    "createdAt": "2026-03-20T14:00:00.000Z",
    "updatedAt": "2026-03-20T14:00:00.000Z"
  }
}
```

#### Examples

```bash
# Default: upsert + merge tags
curl -X POST https://payperwa.com/api/v1/contacts \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"Priya Patel","phone":"9123456789","tags":["lead","mumbai"]}'

# Replace tags entirely instead of merging
curl -X POST https://payperwa.com/api/v1/contacts \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"Priya Patel","phone":"9123456789","tags":["customer"],"tagsMode":"replace"}'

# Strict create-only — return 409 if the phone already exists
curl -X POST https://payperwa.com/api/v1/contacts \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"Priya Patel","phone":"9123456789","upsert":false}'
```

### Get a Single Contact

```
GET /api/v1/contacts/{id}
```

Get a single contact by ID with tags and groups.

### Update a Contact

```
PUT /api/v1/contacts/{id}
```

Update a contact. Send only the fields you want to change. Replacing `tags` replaces all existing tags.

```json
// Request
{
  "name": "Priya P.",
  "tags": ["customer", "vip"]
}
```

### Delete a Contact

```
DELETE /api/v1/contacts/{id}
```

Soft-delete a contact (can be restored by support).

---

## 7. Templates

```
GET /api/v1/templates
```

List your approved message templates. Filter by status or category.

**Permission:** `templates:read`

#### Query Parameters

| Param      | Default  | Description                        |
| ---------- | -------- | ---------------------------------- |
| `status`   | APPROVED | DRAFT, PENDING, APPROVED, REJECTED |
| `category` | -        | MARKETING, UTILITY, AUTHENTICATION |

#### Response

```json
{
  "success": true,
  "data": {
    "templates": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440002",
        "name": "order_confirmation",
        "category": "UTILITY",
        "language": "en",
        "status": "APPROVED",
        "body": "Hi {{1}}, your order {{2}} of {{3}} has been confirmed!",
        "header": null,
        "footer": "Thank you for shopping with us",
        "buttons": null,
        "createdAt": "2026-02-01T12:00:00.000Z"
      }
    ]
  }
}
```

#### Example

```bash
curl "https://payperwa.com/api/v1/templates?status=APPROVED" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

---

## 8. Campaigns

### List Campaigns

```
GET /api/v1/campaigns
```

List all campaigns with status and delivery stats.

**Permission:** `campaigns:read`

#### Response

```json
{
  "success": true,
  "data": {
    "campaigns": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440003",
        "name": "Diwali Offer 2026",
        "status": "COMPLETED",
        "template": "promo_offer",
        "templateCategory": "MARKETING",
        "totalMessages": 5000,
        "sentCount": 5000,
        "deliveredCount": 4850,
        "readCount": 3200,
        "failedCount": 150,
        "estimatedCost": "5300.00",
        "actualCost": "5300.00",
        "createdAt": "2026-03-10T09:00:00.000Z"
      }
    ],
    "total": 42,
    "page": 1,
    "pageSize": 20
  }
}
```

### Create a Campaign

```
POST /api/v1/campaigns
```

Create and optionally send a campaign. Set `send: true` to immediately queue messages, or omit it to create as DRAFT.

**Permission:** `campaigns:send`

#### Request and Response

```json
// Request
{
  "name": "March Sale",
  "templateId": "550e8400-e29b-41d4-a716-446655440002",
  "groupIds": ["group-uuid-1"],
  "variables": {
    "1": "name",
    "2": "20%",
    "3": "MARCH20"
  },
  "send": true
}

// Response (201)
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440004",
    "name": "March Sale",
    "status": "SENDING",
    "totalContacts": 5000,
    "estimatedCost": {
      "meta_fee": "4300.00",
      "platform_fee": "1000.00",
      "total": "5300.00"
    },
    "message": "Campaign queued. 5000 messages will be sent."
  }
}
```

#### Example

```bash
curl -X POST https://payperwa.com/api/v1/campaigns \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "March Sale",
    "templateId": "your-template-uuid",
    "groupIds": ["your-group-uuid"],
    "variables": { "1": "name", "2": "20%", "3": "MARCH20" },
    "send": true
  }'
```

---

## 9. Wallet / Balance

```
GET /api/v1/balance
```

Check your current wallet balance. All amounts in INR.

**Permission:** `balance:read`

#### Response

```json
{
  "success": true,
  "data": {
    "balance": 4520.60,
    "currency": "INR"
  }
}
```

#### Example

```bash
curl https://payperwa.com/api/v1/balance \
  -H "Authorization: Bearer YOUR_API_KEY"
```

---

## 10. Webhooks

PayPerWA can send delivery status callbacks to your server whenever a message status changes (sent, delivered, read, or failed). Configure your webhook URL in **Dashboard → Settings**.

### Webhook Payload

```json
{
  "event": "message.status",
  "message_id": "wamid.HBgLMTIzNDU2Nzg5MA==",
  "status": "delivered",
  "timestamp": "2026-03-20T14:35:00Z",
  "recipient": "919876543210",
  "campaign_id": "camp_abc123"
}
```

### Status Values

| Status      | Description                                      |
| ----------- | ------------------------------------------------ |
| `sent`      | Message sent to WhatsApp servers                 |
| `delivered` | Message delivered to recipient's device          |
| `read`      | Recipient read the message                       |
| `failed`    | Message could not be delivered (wallet refunded) |

### Verifying Webhooks

Each webhook request includes an `X-PayPerWA-Signature` header. Verify it using your webhook secret (available in Settings) with HMAC-SHA256.

```javascript
const crypto = require("crypto");

function verifyWebhook(body, signature, secret) {
  const expected = crypto
    .createHmac("sha256", secret)
    .update(JSON.stringify(body))
    .digest("hex");
  return signature === expected;
}
```

---

## 11. Error Codes

All errors follow a consistent format.

```json
{
  "success": false,
  "error": "Human-readable error message"
}
```

| Code  | Status            | Description                                                                        |
| ----- | ----------------- | --------------------------------------------------------------------------------- |
| `400` | Bad Request       | Invalid request body or missing required fields                                    |
| `401` | Unauthorized      | Invalid, missing, expired, or deactivated API key                                 |
| `402` | Payment Required  | Insufficient wallet balance. Recharge at Dashboard → Billing                      |
| `403` | Forbidden         | API key lacks the required permission for this endpoint                           |
| `404` | Not Found         | Resource not found (contact, template, or campaign)                               |
| `409` | Conflict          | Duplicate resource (e.g. contact with same phone number)                          |
| `429` | Too Many Requests | Rate limit exceeded. Wait and retry.                                              |
| `500` | Server Error      | Internal server error. Contact support if this persists.                          |

---

## 12. Permissions

Each API key can be scoped with specific permissions. New keys are created with all permissions by default. You can restrict them when creating or editing a key.

| Permission       | Grants Access To                                                             |
| ---------------- | ---------------------------------------------------------------------------- |
| `contacts:read`  | GET /api/v1/contacts, GET /api/v1/contacts/:id                               |
| `contacts:write` | POST /api/v1/contacts, PUT /api/v1/contacts/:id, DELETE /api/v1/contacts/:id |
| `templates:read` | GET /api/v1/templates                                                        |
| `messages:send`  | POST /api/v1/messages/send                                                   |
| `campaigns:read` | GET /api/v1/campaigns                                                        |
| `campaigns:send` | POST /api/v1/campaigns (create + send)                                       |
| `balance:read`   | GET /api/v1/balance                                                          |

---

## Quick Reference — Endpoint Summary

| Method   | Endpoint                    | Permission        | Description                          |
| -------- | --------------------------- | ----------------- | ------------------------------------ |
| `GET`    | `/api/v1/balance`           | `balance:read`    | Check wallet balance                 |
| `POST`   | `/api/v1/messages/send`     | `messages:send`   | Send a single templated message      |
| `GET`    | `/api/v1/contacts`          | `contacts:read`   | List contacts (paginated, search)    |
| `POST`   | `/api/v1/contacts`          | `contacts:write`  | Create or upsert a contact           |
| `GET`    | `/api/v1/contacts/{id}`     | `contacts:read`   | Get a single contact                 |
| `PUT`    | `/api/v1/contacts/{id}`     | `contacts:write`  | Update a contact                     |
| `DELETE` | `/api/v1/contacts/{id}`     | `contacts:write`  | Soft-delete a contact                |
| `GET`    | `/api/v1/templates`         | `templates:read`  | List message templates               |
| `GET`    | `/api/v1/campaigns`         | `campaigns:read`  | List campaigns with delivery stats   |
| `POST`   | `/api/v1/campaigns`         | `campaigns:send`  | Create and optionally send a campaign|

---

*Document generated from the official PayPerWA API documentation at https://payperwa.com/docs*
