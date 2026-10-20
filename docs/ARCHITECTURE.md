# Architecture and production boundaries

This lab contains two independent surfaces backed by the same original Python code: the Streamlit interface calls the engine locally, and the Postman collection sends HTTP requests to FastAPI, which calls the engine.

A Streamlit Community Cloud URL does NOT expose the FastAPI endpoint. A public Postman collection needs a separately deployed API if people are to run it without installing Python.

## Deduplication model

Each simulated delivery includes an arrival time in seconds and an event envelope. The engine first validates the envelope. Invalid events never reserve the ID. It removes entries older than the configured TTL and calculates a SHA-256 digest of canonical JSON (sorted keys, compact separators). First observation is accepted; a second delivery with the same live ID and digest is ignored; same ID with different digest is rejected. At exactly TTL expiry, a replay can be accepted again.

This is deliberately **not a production receiver**: a Python dictionary scoped to a single simulation call cannot protect across machines, processes, requests, restarts or races. SHA-256 here is a deterministic content fingerprint, not provider authentication.

## Example durable inbox design (illustrative SQL, NOT used by the simulator)

~~~sql
CREATE TABLE webhook_inbox (
  provider TEXT NOT NULL,
  event_id TEXT NOT NULL,
  body_digest TEXT NOT NULL,
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  processing_state TEXT NOT NULL DEFAULT 'received',
  PRIMARY KEY (provider, event_id)
);
~~~

After verifying a real provider signature, an actual receiver could atomically insert a receipt:

~~~sql
INSERT INTO webhook_inbox (provider, event_id, body_digest)
VALUES ($1, $2, $3)
ON CONFLICT (provider, event_id) DO NOTHING
RETURNING provider, event_id;
~~~

If no row is inserted, inspect the existing row for a digest collision and processing state under an appropriate isolation/transaction scheme. Persist the job atomically and acknowledge only after durable acceptance. A durable worker needs retries, leasing, state transitions, poison-message handling, recovery and tracing. Do not conflate recorded receipt with successfully processed business work.

## Retry and signature boundaries

Retry wait n is the minimum of (maximum cap) and (base delay multiplied by 2 to the power n-1). The demo can model numeric Retry-After for 429 and 503, seeded jitter, and success/failure boundaries. No actual HTTP requests are made.

Signature demo: HMAC-SHA256 over ASCII timestamp plus dot plus exact UTF-8 payload bytes, using a PUBLIC educational key embedded in source. The demo checks a constant-time digest comparison plus timestamp window. The key provides NO real authentication; different webhook platforms have different signature schemes. Even a real valid signature permits replay within the time window unless you enforce idempotency.

## API protections and limits

Max request body 64 KiB; max event 16,000 encoded bytes; up to 60 deliveries per replay; TTL up to 3,600 seconds; up to 12 simulated retry attempts. No filesystem writes, customer data, arbitrary URLs, HTTP forwarding, credentials or persisted dedup records. Responses request no-store caching, sanitise model-validation errors, and omit event bodies from reports.

A public deployment still needs network-level traffic controls, abuse monitoring, platform quota checks, a suitable logs/retention policy and explicit confirmation that visitors only send synthetic examples.

For real provider requirements start with [GitHub webhook best practices](https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks).