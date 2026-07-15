# Apify API (v2) — Detailed Reference

The Apify API version 2 provides programmatic access to the Apify platform. It is organized around RESTful HTTP endpoints. All requests and responses (including errors) are encoded in JSON with UTF-8, with a few explicitly noted exceptions (such as dataset items and key-value store records, which can return other formats).

**Source:** https://docs.apify.com/api/v2
**API version:** v2
**OpenAPI schema:** https://docs.apify.com/api/openapi.yaml · https://docs.apify.com/api/openapi.json

**Official clients:** [apify-client for JavaScript](https://docs.apify.com/api/client/js) · [apify-client for Python](https://docs.apify.com/api/client/python). The client functions map one-to-one to these API endpoints with the same parameters, and they handle retries and exponential backoff for you.

---

## Table of Contents

1. [Base URL](#1-base-url)
2. [Authentication](#2-authentication)
3. [Basic usage and typical workflow](#3-basic-usage-and-typical-workflow)
4. [Request details](#4-request-details)
5. [Response structure](#5-response-structure)
6. [Pagination](#6-pagination)
7. [Errors](#7-errors)
8. [Rate limiting](#8-rate-limiting)
9. [Referring to resources](#9-referring-to-resources)
10. [Core endpoints — full detail](#10-core-endpoints--full-detail)
11. [Full endpoint catalog](#11-full-endpoint-catalog)
    - [Actors](#actors)
    - [Actor versions](#actor-versions)
    - [Actor builds (nested under Actor)](#actor-builds-nested-under-actor)
    - [Actor runs (nested under Actor)](#actor-runs-nested-under-actor)
    - [Actor webhooks (nested under Actor)](#actor-webhooks-nested-under-actor)
    - [Actor builds (top-level)](#actor-builds-top-level)
    - [Actor runs (top-level)](#actor-runs-top-level)
    - [Actor tasks](#actor-tasks)
    - [Storage — Datasets](#storage--datasets)
    - [Storage — Key-value stores](#storage--key-value-stores)
    - [Storage — Request queues](#storage--request-queues)
    - [Webhooks](#webhooks)
    - [Webhook dispatches](#webhook-dispatches)
    - [Schedules](#schedules)
    - [Store](#store)
    - [Logs](#logs)
    - [Users](#users)
    - [Tools](#tools)
    - [Convenience endpoints](#convenience-endpoints)

---

## 1. Base URL

```
https://api.apify.com/v2
```

All endpoint paths in this document are relative to this base URL.

---

## 2. Authentication

Find your API token on the [Integrations page](https://console.apify.com/account#/integrations) in Apify Console. Use it in one of two ways:

**Recommended — Authorization header (Bearer token):**

```
Authorization: Bearer YOUR_API_TOKEN
```

**Less secure — query parameter:**

```
?token=YOUR_API_TOKEN
```

The header method is safer because URLs are often stored in browser history and server logs, which can leak a token placed in the query string.

**When is authentication required?**

Required for private Actors, tasks, or resources (including builds of private Actors). Required when using named formats for IDs (for example `username~store-name` for stores or `username~queue-name` for queues). Optional for public Actors or resources (builds of public Actors can be queried without a token).

Do not share your API token or account password with untrusted parties.

---

## 3. Basic usage and typical workflow

To run an Actor, send a `POST` request to the Run Actor endpoint using either the Actor ID (for example `vKg4IjxZbEYTYeW8T`) or its name (for example `janedoe~my-actor`):

```
POST https://api.apify.com/v2/acts/{actorId}/runs
```

If the Actor is not runnable anonymously, you receive a `401` or `403` response, meaning you must add your API token.

A typical polling workflow looks like this:

1. **Run** an Actor or task using the Run Actor or Run task endpoints.
2. **Monitor** the run by periodically polling its progress with the Get run endpoint.
3. **Fetch results** from the Get dataset items endpoint using the `defaultDatasetId` returned in the run response. Additional data may live in a key-value store, retrievable from Get record using the `defaultKeyValueStoreId` and the record's `key`.

Instead of polling, you can run an Actor or task **synchronously**. A synchronous request waits up to 300 seconds (5 minutes) for the run to finish and returns its output. If the run takes longer, the request times out and throws an error.

---

## 4. Request details

**Content-Type header:** For requests with a JSON body, include `Content-Type: application/json`.

**Method override:** You can override the HTTP method using the `method` query parameter. This helps clients that can only send `GET` requests. For example, to call a `POST` endpoint from a `GET` request, append `?method=POST` to the URL.

---

## 5. Response structure

Most endpoints return a JSON object with a `data` property:

```json
{
  "data": {
    ...
  }
}
```

Exceptions such as Get dataset items and Get record return data in other formats (for example raw items, CSV, or the stored record itself).

On error, the HTTP status code is in the `4xx` or `5xx` range and the `data` property is replaced by `error`:

```json
{
  "error": {
    "type": "record-not-found",
    "message": "Store was not found."
  }
}
```

---

## 6. Pagination

All endpoints that return a list of records enforce pagination to limit response size. Most use `offset` and `limit`. The only exception is Get list of keys (key-value stores), which uses `exclusiveStartKey`.

Each paginated endpoint enforces its own maximum `limit`. This maximum can change, so never rely on a specific value; always check the response.

### Using offset

| Parameter | Description                                                                                                                                                                                                                 |
| --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `limit`   | Maximum number of items to return, e.g. `limit=20`.                                                                                                                                                                          |
| `offset`  | Number of items to skip from the start, e.g. `offset=100`.                                                                                                                                                                   |
| `desc`    | By default items are sorted oldest to newest (order created/added). Set `desc=1` to return newest to oldest. Useful when fetching all items, since it ensures items created after pagination started are not skipped.        |

Response shape:

```json
{
  "data": {
    "total": 2560,
    "offset": 250,
    "limit": 1000,
    "count": 1000,
    "desc": false,
    "items": [ /* ... */ ]
  }
}
```

| Property | Meaning                                                                                                     |
| -------- | ---------------------------------------------------------------------------------------------------------- |
| `total`  | Total number of items available in the list.                                                               |
| `offset` | Number of items skipped at the start (equals the `offset` query param, or `0`).                            |
| `limit`  | Maximum items returnable in the response (the smaller of your `limit` and the endpoint's enforced maximum).|
| `count`  | Actual number of items returned in this response.                                                          |
| `desc`   | `true` if data was requested in descending order, otherwise `false`.                                       |
| `items`  | Array of requested items.                                                                                  |

### Using key

Key-value store records are ordered by their keys in UTF-8 binary order, not by numeric index. The Get list of keys endpoint paginates with:

| Parameter           | Description                                                                                    |
| ------------------- | --------------------------------------------------------------------------------------------- |
| `limit`             | Maximum number of items to return, e.g. `limit=20`.                                            |
| `exclusiveStartKey` | Skips all records up to and including the given key, in UTF-8 binary order.                    |

Response shape:

```json
{
  "data": {
    "limit": 1000,
    "isTruncated": true,
    "exclusiveStartKey": "my-key",
    "nextExclusiveStartKey": "some-other-key",
    "items": [ /* ... */ ]
  }
}
```

| Property                | Meaning                                                                     |
| ----------------------- | --------------------------------------------------------------------------- |
| `limit`                 | Maximum items returnable (smaller of your `limit` and the enforced maximum).|
| `isTruncated`           | `true` if more items remain to be queried, otherwise `false`.               |
| `exclusiveStartKey`     | The last key skipped at the start. `null` for the first page.               |
| `nextExclusiveStartKey` | Value to pass as `exclusiveStartKey` to fetch the next page.                |

---

## 7. Errors

The API uses standard HTTP status codes: `2xx` for success, `4xx` for caller errors (invalid requests), and `5xx` for server errors (rare). Each error response contains an `error` object with `type` (error code) and `message` (human-readable description).

```json
{
  "error": {
    "type": "record-not-found",
    "message": "Store was not found."
  }
}
```

Common errors across many endpoints:

| Status | Type                  | Message (example)                                                                    |
| ------ | --------------------- | ------------------------------------------------------------------------------------ |
| `400`  | `invalid-request`     | POST data must be a JSON object                                                       |
| `400`  | `invalid-value`       | Invalid value provided: Comments required                                            |
| `400`  | `invalid-record-key`  | Record key contains invalid character                                                |
| `401`  | `token-not-provided`  | Authentication token was not provided                                                |
| `404`  | `record-not-found`    | Store was not found                                                                  |
| `405`  | `method-not-allowed`  | This API endpoint can only be accessed using the following HTTP methods: ...         |
| `429`  | `rate-limit-exceeded` | You have exceeded the rate limit of ... requests per second                          |

---

## 8. Rate limiting

There are two kinds of limits: a global rate limit and a per-resource rate limit.

### Global rate limit

**250,000 requests per minute.** For authenticated requests it is counted per user; for unauthenticated requests it is counted per IP address.

### Per-resource rate limit

The default is **60 requests per second per resource**, where a resource means a single Actor, a single run, a single dataset, a single key-value store, and so on. Each endpoint returns its own limit in the `X-RateLimit-Limit` header.

Higher limits apply to some endpoints:

**200 requests/second per resource:**

- CRUD operations (get, put, delete) on key-value store records.

**400 requests/second per resource:**

- Run Actor
- Run Actor task asynchronously
- Run Actor task synchronously
- Metamorph Actor run
- Push items to dataset
- CRUD operations (add, get, update, delete) on requests in request queues.

### Rate limit exceeded

When you send too many requests, the API responds with `429 Too Many Requests`:

```json
{
  "error": {
    "type": "rate-limit-exceeded",
    "message": "You have exceeded the rate limit of ... requests per second"
  }
}
```

### Exponential backoff

On a `429`, wait and retry, doubling the wait period each time:

1. Set `DELAY = 500`.
2. Send the request.
3. If the status is not `429`, you are done. Otherwise: wait a random period between `DELAY` and `2 * DELAY` milliseconds, set `DELAY = 2 * DELAY`, and go back to step 2.

The official JavaScript and Python clients implement this backoff transparently.

---

## 9. Referring to resources

There are three ways to reference a resource:

- **Resource ID** — for example `iKkPcIgVvwmztduf8`.
- **`username~resourcename`** — requires your API token; works only if you have the correct permissions.
- **`~resourcename`** — requires an API token; refers to a resource in the token owner's own account.

---

## 10. Core endpoints — full detail

These are the endpoints used in almost every integration. Full request/response detail is shown here; the complete catalog of every endpoint follows in section 11.

### Run Actor

```
POST /v2/acts/{actorId}/runs
```

Runs an Actor and returns the run object immediately (asynchronous). Rate limit 400/s per resource.

**Common query parameters:**

| Parameter        | Type    | Description                                                                                      |
| ---------------- | ------- | ----------------------------------------------------------------------------------------------- |
| `timeout`        | number  | Optional timeout for the run, in seconds. `0` means no limit.                                    |
| `memory`         | number  | Memory limit for the run, in megabytes (power of 2, e.g. 128, 256, 512, 1024, 2048, 4096, 8192).|
| `maxItems`       | number  | Maximum number of results to store in the dataset (for pay-per-result Actors).                  |
| `build`          | string  | Specifies the Actor build to run (tag or version number, e.g. `latest` or `0.1.2`).             |
| `webhooks`       | string  | Base64-encoded JSON array of webhooks to attach to the run (ad-hoc webhooks).                   |
| `waitForFinish`  | number  | Seconds (max 60) to wait synchronously before returning the run object.                         |

**Request body:** The Actor input JSON (structure depends on the Actor's input schema). Send `Content-Type: application/json`.

**Example:**

```bash
curl -X POST "https://api.apify.com/v2/acts/apify~web-scraper/runs" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "startUrls": [{ "url": "https://example.com" }],
    "maxRequestsPerCrawl": 10
  }'
```

**Response (201):** A run object.

```json
{
  "data": {
    "id": "HG7ML7M8z78YcAPEB",
    "actId": "HDSasDasz78YcAPEB",
    "status": "RUNNING",
    "startedAt": "2026-01-01T00:00:00.000Z",
    "finishedAt": null,
    "defaultDatasetId": "9RunQkfSM4x2LnT7q",
    "defaultKeyValueStoreId": "sfAjeR4QziwGiJf46",
    "defaultRequestQueueId": "FL35cSF7jrxr3BY39",
    "containerUrl": "https://...",
    "usageTotalUsd": 0
  }
}
```

Run `status` progresses through values such as `READY`, `RUNNING`, `SUCCEEDED`, `FAILED`, `ABORTING`, `ABORTED`, `TIMING-OUT`, and `TIMED-OUT`.

### Run Actor synchronously and get dataset items

```
POST /v2/acts/{actorId}/run-sync-get-dataset-items
GET  /v2/acts/{actorId}/run-sync-get-dataset-items
```

Runs the Actor, waits up to 300 seconds for it to finish, and returns the contents of the default dataset directly (not wrapped in `data`). Use `POST` to pass input in the body; use `GET` for input-less runs. Accepts the same run query parameters as Run Actor, plus dataset item formatting parameters (`format`, `fields`, `clean`, and so on).

```bash
curl -X POST "https://api.apify.com/v2/acts/apify~web-scraper/run-sync-get-dataset-items" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "startUrls": [{ "url": "https://example.com" }] }'
```

### Get run

```
GET /v2/actor-runs/{runId}
```

Returns the run object for polling. The same run is also reachable at `GET /v2/acts/{actorId}/runs/{runId}`. Poll this until `status` is a terminal value (`SUCCEEDED`, `FAILED`, `ABORTED`, `TIMED-OUT`).

### Get dataset items

```
GET /v2/datasets/{datasetId}/items
```

Returns the items stored in a dataset. This endpoint returns the items directly (not wrapped in `data`) and supports multiple output formats.

**Query parameters:**

| Parameter    | Type    | Description                                                                                              |
| ------------ | ------- | ------------------------------------------------------------------------------------------------------- |
| `format`     | string  | Output format: `json` (default), `jsonl`, `csv`, `html`, `xlsx`, `xml`, `rss`.                          |
| `offset`     | number  | Number of items to skip.                                                                                 |
| `limit`      | number  | Maximum number of items to return.                                                                       |
| `fields`     | string  | Comma-separated list of fields to include in each item.                                                 |
| `omit`       | string  | Comma-separated list of fields to omit.                                                                  |
| `clean`      | boolean | If `true`, returns only non-empty items and skips hidden fields (those starting with `#`).              |
| `desc`       | boolean | If `true`, returns items in reverse order (newest first).                                                |
| `flatten`    | string  | Comma-separated list of fields to flatten.                                                               |
| `skipHeaderRow` | boolean | For CSV, skips the header row.                                                                        |

```bash
curl "https://api.apify.com/v2/datasets/9RunQkfSM4x2LnT7q/items?format=json&clean=true" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

### Store items (push to dataset)

```
POST /v2/datasets/{datasetId}/items
```

Appends one item or an array of items to the dataset. Rate limit 400/s per resource.

```bash
curl -X POST "https://api.apify.com/v2/datasets/9RunQkfSM4x2LnT7q/items" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '[{ "name": "Item 1" }, { "name": "Item 2" }]'
```

### Get key-value store record

```
GET /v2/key-value-stores/{storeId}/records/{recordKey}
```

Returns the value stored under `recordKey`, with the `Content-Type` it was saved with. Commonly used to read an Actor run's `OUTPUT` from its default key-value store.

```bash
curl "https://api.apify.com/v2/key-value-stores/sfAjeR4QziwGiJf46/records/OUTPUT" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

### Store key-value store record

```
PUT /v2/key-value-stores/{storeId}/records/{recordKey}
```

Saves a value under `recordKey`. Set `Content-Type` to match the payload (for example `application/json`, `text/plain`, `image/png`). Rate limit 200/s per resource.

```bash
curl -X PUT "https://api.apify.com/v2/key-value-stores/sfAjeR4QziwGiJf46/records/my-key" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "hello": "world" }'
```

### Add requests to a request queue (batch)

```
POST /v2/request-queues/{queueId}/requests/batch
```

Adds a batch of requests (URLs to crawl) to a request queue. Rate limit 400/s per resource.

```bash
curl -X POST "https://api.apify.com/v2/request-queues/FL35cSF7jrxr3BY39/requests/batch" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '[{ "url": "https://example.com" }, { "url": "https://example.org" }]'
```

---

## 11. Full endpoint catalog

Every endpoint below is relative to `https://api.apify.com/v2`. Path parameters are shown in braces, for example `{actorId}`.

### Actors

| Method   | Path                              | Description                              |
| -------- | --------------------------------- | ---------------------------------------- |
| `GET`    | `/acts`                           | Get list of Actors                       |
| `POST`   | `/acts`                           | Create Actor                             |
| `GET`    | `/acts/{actorId}`                 | Get Actor                                |
| `PUT`    | `/acts/{actorId}`                 | Update Actor                             |
| `DELETE` | `/acts/{actorId}`                 | Delete Actor                             |
| `POST`   | `/acts/{actorId}/validate-input`  | Validate Actor input                     |

### Actor versions

| Method   | Path                                                                     | Description                          |
| -------- | ------------------------------------------------------------------------ | ------------------------------------ |
| `GET`    | `/acts/{actorId}/versions`                                               | Get list of versions                 |
| `POST`   | `/acts/{actorId}/versions`                                               | Create version                       |
| `GET`    | `/acts/{actorId}/versions/{versionNumber}`                               | Get version                          |
| `PUT`    | `/acts/{actorId}/versions/{versionNumber}`                               | Update version                       |
| `POST`   | `/acts/{actorId}/versions/{versionNumber}`                               | Update version (POST)                |
| `DELETE` | `/acts/{actorId}/versions/{versionNumber}`                               | Delete version                       |
| `GET`    | `/acts/{actorId}/versions/{versionNumber}/env-vars`                      | Get list of environment variables    |
| `POST`   | `/acts/{actorId}/versions/{versionNumber}/env-vars`                      | Create environment variable          |
| `GET`    | `/acts/{actorId}/versions/{versionNumber}/env-vars/{envVarName}`         | Get environment variable             |
| `PUT`    | `/acts/{actorId}/versions/{versionNumber}/env-vars/{envVarName}`         | Update environment variable          |
| `POST`   | `/acts/{actorId}/versions/{versionNumber}/env-vars/{envVarName}`         | Update environment variable (POST)   |
| `DELETE` | `/acts/{actorId}/versions/{versionNumber}/env-vars/{envVarName}`         | Delete environment variable          |

### Actor builds (nested under Actor)

| Method | Path                                              | Description               |
| ------ | ------------------------------------------------- | ------------------------- |
| `GET`  | `/acts/{actorId}/builds`                          | Get list of builds        |
| `POST` | `/acts/{actorId}/builds`                          | Build Actor               |
| `GET`  | `/acts/{actorId}/builds/default`                  | Get default build         |
| `GET`  | `/acts/{actorId}/builds/{buildId}/openapi.json`   | Get OpenAPI definition    |
| `GET`  | `/acts/{actorId}/builds/{buildId}`                | Get build                 |
| `POST` | `/acts/{actorId}/builds/{buildId}/abort`          | Abort build               |

### Actor runs (nested under Actor)

| Method | Path                                                     | Description                                                    |
| ------ | -------------------------------------------------------- | ------------------------------------------------------------- |
| `GET`  | `/acts/{actorId}/runs`                                   | Get list of runs                                              |
| `POST` | `/acts/{actorId}/runs`                                   | Run Actor                                                     |
| `POST` | `/acts/{actorId}/run-sync`                               | Run Actor synchronously with input and return output          |
| `GET`  | `/acts/{actorId}/run-sync`                               | Run Actor synchronously without input                         |
| `POST` | `/acts/{actorId}/run-sync-get-dataset-items`            | Run synchronously with input and get dataset items            |
| `GET`  | `/acts/{actorId}/run-sync-get-dataset-items`            | Run synchronously without input and get dataset items         |
| `POST` | `/acts/{actorId}/runs/{runId}/resurrect`                | Resurrect run                                                 |
| `GET`  | `/acts/{actorId}/runs/last`                             | Get last run                                                  |
| `GET`  | `/acts/{actorId}/runs/{runId}`                          | Get run                                                       |
| `POST` | `/acts/{actorId}/runs/{runId}/abort`                    | Abort run                                                     |
| `POST` | `/acts/{actorId}/runs/{runId}/metamorph`                | Metamorph run                                                 |

### Actor webhooks (nested under Actor)

| Method | Path                          | Description           |
| ------ | ----------------------------- | --------------------- |
| `GET`  | `/acts/{actorId}/webhooks`    | Get list of webhooks  |

### Actor builds (top-level)

| Method   | Path                                    | Description             |
| -------- | --------------------------------------- | ----------------------- |
| `GET`    | `/actor-builds`                         | Get user builds list    |
| `GET`    | `/actor-builds/{buildId}`               | Get build               |
| `DELETE` | `/actor-builds/{buildId}`               | Delete build            |
| `POST`   | `/actor-builds/{buildId}/abort`         | Abort build             |
| `GET`    | `/actor-builds/{buildId}/log`           | Get build's log         |
| `GET`    | `/actor-builds/{buildId}/openapi.json`  | Get OpenAPI definition  |

### Actor runs (top-level)

| Method   | Path                                 | Description               |
| -------- | ------------------------------------ | ------------------------- |
| `GET`    | `/actor-runs`                        | Get user runs list        |
| `GET`    | `/actor-runs/{runId}`                | Get run                   |
| `PUT`    | `/actor-runs/{runId}`                | Update run                |
| `DELETE` | `/actor-runs/{runId}`                | Delete run                |
| `POST`   | `/actor-runs/{runId}/abort`          | Abort run                 |
| `POST`   | `/actor-runs/{runId}/metamorph`      | Metamorph run             |
| `POST`   | `/actor-runs/{runId}/reboot`         | Reboot run                |
| `POST`   | `/actor-runs/{runId}/resurrect`      | Resurrect run             |
| `POST`   | `/actor-runs/{runId}/charge`         | Charge events in run      |
| `GET`    | `/actor-runs/{runId}/log`            | Get run's log             |

### Actor tasks

| Method   | Path                                                          | Description                                    |
| -------- | ------------------------------------------------------------- | ---------------------------------------------- |
| `GET`    | `/actor-tasks`                                                | Get list of tasks                              |
| `POST`   | `/actor-tasks`                                                | Create task                                    |
| `GET`    | `/actor-tasks/{actorTaskId}`                                  | Get task                                       |
| `PUT`    | `/actor-tasks/{actorTaskId}`                                  | Update task                                    |
| `DELETE` | `/actor-tasks/{actorTaskId}`                                  | Delete task                                    |
| `GET`    | `/actor-tasks/{actorTaskId}/input`                           | Get task input                                 |
| `PUT`    | `/actor-tasks/{actorTaskId}/input`                           | Update task input                              |
| `GET`    | `/actor-tasks/{actorTaskId}/webhooks`                        | Get list of webhooks                           |
| `GET`    | `/actor-tasks/{actorTaskId}/runs`                            | Get list of task runs                          |
| `POST`   | `/actor-tasks/{actorTaskId}/runs`                            | Run task                                       |
| `GET`    | `/actor-tasks/{actorTaskId}/run-sync`                        | Run task synchronously (GET)                   |
| `POST`   | `/actor-tasks/{actorTaskId}/run-sync`                        | Run task synchronously (POST)                  |
| `GET`    | `/actor-tasks/{actorTaskId}/run-sync-get-dataset-items`     | Run task synchronously and get dataset items   |
| `POST`   | `/actor-tasks/{actorTaskId}/run-sync-get-dataset-items`     | Run task synchronously and get dataset items   |
| `GET`    | `/actor-tasks/{actorTaskId}/runs/last`                      | Get last run                                   |

### Storage — Datasets

| Method   | Path                                  | Description               |
| -------- | ------------------------------------- | ------------------------- |
| `GET`    | `/datasets`                           | Get list of datasets      |
| `POST`   | `/datasets`                           | Create dataset            |
| `GET`    | `/datasets/{datasetId}`               | Get dataset               |
| `PUT`    | `/datasets/{datasetId}`               | Update dataset            |
| `DELETE` | `/datasets/{datasetId}`               | Delete dataset            |
| `GET`    | `/datasets/{datasetId}/items`         | Get dataset items         |
| `HEAD`   | `/datasets/{datasetId}/items`         | Get dataset items headers |
| `POST`   | `/datasets/{datasetId}/items`         | Store items               |
| `GET`    | `/datasets/{datasetId}/statistics`    | Get dataset statistics    |

### Storage — Key-value stores

| Method   | Path                                                   | Description                |
| -------- | ------------------------------------------------------ | -------------------------- |
| `GET`    | `/key-value-stores`                                    | Get list of key-value stores |
| `POST`   | `/key-value-stores`                                    | Create key-value store     |
| `GET`    | `/key-value-stores/{storeId}`                          | Get store                  |
| `PUT`    | `/key-value-stores/{storeId}`                          | Update store               |
| `DELETE` | `/key-value-stores/{storeId}`                          | Delete store               |
| `GET`    | `/key-value-stores/{storeId}/keys`                     | Get list of keys           |
| `GET`    | `/key-value-stores/{storeId}/records/{recordKey}`      | Get record                 |
| `HEAD`   | `/key-value-stores/{storeId}/records/{recordKey}`      | Check if a record exists   |
| `PUT`    | `/key-value-stores/{storeId}/records/{recordKey}`      | Store record               |
| `POST`   | `/key-value-stores/{storeId}/records/{recordKey}`      | Store record (POST)        |
| `DELETE` | `/key-value-stores/{storeId}/records/{recordKey}`      | Delete record              |

### Storage — Request queues

**Queues:**

| Method   | Path                                  | Description               |
| -------- | ------------------------------------- | ------------------------- |
| `GET`    | `/request-queues`                     | Get list of request queues|
| `POST`   | `/request-queues`                     | Create request queue      |
| `GET`    | `/request-queues/{queueId}`           | Get request queue         |
| `PUT`    | `/request-queues/{queueId}`           | Update request queue      |
| `DELETE` | `/request-queues/{queueId}`           | Delete request queue      |

**Requests (batch and single):**

| Method   | Path                                                     | Description        |
| -------- | -------------------------------------------------------- | ------------------ |
| `POST`   | `/request-queues/{queueId}/requests/batch`               | Add requests (batch)|
| `DELETE` | `/request-queues/{queueId}/requests/batch`               | Delete requests (batch)|
| `GET`    | `/request-queues/{queueId}/requests`                     | List requests      |
| `POST`   | `/request-queues/{queueId}/requests`                     | Add request        |
| `GET`    | `/request-queues/{queueId}/requests/{requestId}`         | Get request        |
| `PUT`    | `/request-queues/{queueId}/requests/{requestId}`         | Update request     |
| `DELETE` | `/request-queues/{queueId}/requests/{requestId}`         | Delete request     |

**Request locks and head:**

| Method   | Path                                                          | Description            |
| -------- | ------------------------------------------------------------ | --------------------- |
| `POST`   | `/request-queues/{queueId}/requests/unlock`                  | Unlock requests       |
| `GET`    | `/request-queues/{queueId}/head`                             | Get head              |
| `POST`   | `/request-queues/{queueId}/head/lock`                        | Get head and lock     |
| `PUT`    | `/request-queues/{queueId}/requests/{requestId}/lock`        | Prolong request lock  |
| `DELETE` | `/request-queues/{queueId}/requests/{requestId}/lock`        | Delete request lock   |

### Webhooks

| Method   | Path                                | Description             |
| -------- | ----------------------------------- | ----------------------- |
| `GET`    | `/webhooks`                         | Get list of webhooks    |
| `POST`   | `/webhooks`                         | Create webhook          |
| `GET`    | `/webhooks/{webhookId}`             | Get webhook             |
| `PUT`    | `/webhooks/{webhookId}`             | Update webhook          |
| `DELETE` | `/webhooks/{webhookId}`             | Delete webhook          |
| `POST`   | `/webhooks/{webhookId}/test`        | Test webhook            |
| `GET`    | `/webhooks/{webhookId}/dispatches`  | Get collection of dispatches |

### Webhook dispatches

| Method | Path                              | Description                     |
| ------ | --------------------------------- | ------------------------------- |
| `GET`  | `/webhook-dispatches`             | Get list of webhook dispatches  |
| `GET`  | `/webhook-dispatches/{dispatchId}`| Get webhook dispatch            |

### Schedules

| Method   | Path                              | Description             |
| -------- | --------------------------------- | ----------------------- |
| `GET`    | `/schedules`                      | Get list of schedules   |
| `POST`   | `/schedules`                      | Create schedule         |
| `GET`    | `/schedules/{scheduleId}`         | Get schedule            |
| `PUT`    | `/schedules/{scheduleId}`         | Update schedule         |
| `DELETE` | `/schedules/{scheduleId}`         | Delete schedule         |
| `GET`    | `/schedules/{scheduleId}/log`     | Get schedule log        |

### Store

| Method | Path      | Description                   |
| ------ | --------- | ----------------------------- |
| `GET`  | `/store`  | Get list of Actors in Store   |

### Logs

| Method | Path                    | Description   |
| ------ | ----------------------- | ------------- |
| `GET`  | `/logs/{buildOrRunId}`  | Get log       |

### Users

| Method | Path                          | Description             |
| ------ | ----------------------------- | ----------------------- |
| `GET`  | `/users/{userId}`             | Get public user data    |
| `GET`  | `/users/me`                   | Get private user data   |
| `GET`  | `/users/me/usage/monthly`     | Get monthly usage       |
| `GET`  | `/users/me/limits`            | Get limits              |
| `PUT`  | `/users/me/limits`            | Update limits           |

### Tools

| Method   | Path                        | Description               |
| -------- | --------------------------- | ------------------------- |
| `GET`    | `/tools/browser-info`       | Get browser info          |
| `POST`   | `/tools/browser-info`       | Get browser info          |
| `PUT`    | `/tools/browser-info`       | Get browser info          |
| `DELETE` | `/tools/browser-info`       | Get browser info          |
| `POST`   | `/tools/encode-and-sign`    | Encode and sign object    |
| `POST`   | `/tools/decode-and-verify`  | Decode and verify object  |

### Convenience endpoints

These endpoints let you reach a run's default storages (or the last run's storages) without first looking up the storage IDs. They mirror the corresponding storage endpoints exactly (same parameters, same responses); only the path prefix differs.

**A run's default storages** — prefix `/actor-runs/{runId}`:

| Storage            | Base path                              | Available operations                                                                                                   |
| ------------------ | -------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Default dataset    | `/actor-runs/{runId}/dataset`          | `GET` / `PUT` / `DELETE` the dataset; `GET`/`POST` `/dataset/items`; `GET` `/dataset/statistics`                       |
| Default KV store   | `/actor-runs/{runId}/key-value-store`  | `GET` / `PUT` / `DELETE` the store; `GET` `/keys`; `GET`/`PUT`/`POST`/`DELETE` `/records/{recordKey}`                  |
| Default req. queue | `/actor-runs/{runId}/request-queue`    | `GET`/`PUT`/`DELETE` the queue; list/add/get/update/delete requests; batch add/delete; unlock; head and head/lock; request locks |

**Last Actor run's default storages** — prefix `/acts/{actorId}/runs/last`:

| Storage            | Base path                                     | Available operations                                                                          |
| ------------------ | --------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Default dataset    | `/acts/{actorId}/runs/last/dataset`           | `GET`/`PUT`/`DELETE`; `/dataset/items` (`GET`/`POST`); `/dataset/statistics` (`GET`)          |
| Default KV store   | `/acts/{actorId}/runs/last/key-value-store`   | `GET`/`PUT`/`DELETE`; `/keys`; `/records/{recordKey}` (`GET`/`PUT`/`POST`/`DELETE`)           |
| Default req. queue | `/acts/{actorId}/runs/last/request-queue`     | Full request-queue operation set (list/add/get/update/delete, batch, unlock, head, locks)    |
| Last run's log     | `/acts/{actorId}/runs/last/log`               | `GET` last Actor run's log                                                                    |

You can narrow the "last run" using query parameters such as `status` (for example only the last `SUCCEEDED` run).

**Last Actor task run's default storages** — prefix `/actor-tasks/{actorTaskId}/runs/last`:

| Storage            | Base path                                                 | Available operations                                                              |
| ------------------ | --------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Default dataset    | `/actor-tasks/{actorTaskId}/runs/last/dataset`            | `GET`/`PUT`/`DELETE`; `/dataset/items`; `/dataset/statistics`                     |
| Default KV store   | `/actor-tasks/{actorTaskId}/runs/last/key-value-store`    | `GET`/`PUT`/`DELETE`; `/keys`; `/records/{recordKey}`                             |
| Default req. queue | `/actor-tasks/{actorTaskId}/runs/last/request-queue`      | Full request-queue operation set                                                 |
| Last task run's log| `/actor-tasks/{actorTaskId}/runs/last/log`               | `GET` last Actor task run's log                                                   |

---

## Appendix — Official clients

Rather than calling raw HTTP, most integrations use the official clients, whose methods mirror these endpoints and handle auth, retries, and exponential backoff automatically.

**JavaScript / Node.js** (`npm install apify-client`):

```js
import { ApifyClient } from 'apify-client';

const client = new ApifyClient({ token: 'YOUR_API_TOKEN' });

// Run an Actor and wait for it to finish
const run = await client.actor('apify/web-scraper').call({
  startUrls: [{ url: 'https://example.com' }],
});

// Fetch results from the run's default dataset
const { items } = await client.dataset(run.defaultDatasetId).listItems();
console.log(items);
```

**Python** (`pip install apify-client`):

```python
from apify_client import ApifyClient

client = ApifyClient('YOUR_API_TOKEN')

run = client.actor('apify/web-scraper').call(run_input={
    'startUrls': [{'url': 'https://example.com'}],
})

for item in client.dataset(run['defaultDatasetId']).iterate_items():
    print(item)
```

---

*Document compiled from the official Apify API v2 reference at https://docs.apify.com/api/v2. For exact per-endpoint parameters and schemas, consult the linked endpoint pages or download the OpenAPI schema (YAML/JSON).*
