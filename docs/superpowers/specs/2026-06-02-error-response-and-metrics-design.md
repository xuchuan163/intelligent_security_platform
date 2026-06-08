# Error Response and Metrics API Design

## Scope

This iteration adds two focused backend improvements:

- unified error response envelopes for API failures;
- read-only metrics catalog endpoints under `/api/v1/metrics`.

It does not implement metrics validation, lineage, aliases, NL2SQL, or Agent orchestration.

## Unified Error Response

Successful responses keep the existing envelope:

```json
{"code": "SUCCESS", "message": "ok", "data": {}}
```

Error responses use:

```json
{
  "code": "40401",
  "message": "资源不存在",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "data": null,
  "timestamp": "2026-06-02T10:00:00+08:00"
}
```

`X-Request-Id` is reused when supplied. Otherwise the API generates a UUID. The same request id is returned in the response body and response header.

Error code mapping:

- 400 -> `40001`
- 404 -> `40401`
- 409 -> `40901`
- 422 -> `42201`
- 500 -> `50001`
- 503 -> `50301`

Validation errors return a concise message and keep detailed validation data in `data.errors`.

## Metrics API

Add `backend/app/api/v1/endpoints/metrics.py` and mount it at `/metrics`.

Endpoints:

- `GET /api/v1/metrics/catalog`
- `GET /api/v1/metrics/{metric_code}`

`catalog` supports:

- `page_no`, default 1, minimum 1;
- `page_size`, default 20, minimum 1, maximum 100;
- `status`, optional;
- `keyword`, optional fuzzy match against code, name, and business definition.

The catalog response uses the documented pagination shape:

```json
{
  "page_no": 1,
  "page_size": 20,
  "total": 8,
  "items": []
}
```

`GET /metrics/{metric_code}` returns HTTP 404 with unified error envelope when the metric does not exist.

## Testing

Add tests for:

- validation errors use unified envelope;
- 404 errors use unified envelope and preserve `X-Request-Id`;
- metrics catalog route exists and returns pagination shape when DB is available;
- metric detail route exists and returns either data, 404, or 503 according to database state.

