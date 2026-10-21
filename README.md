# Webhook Reliability Lab

**Understand webhook delivery before it breaks your automations.** A hands-on [Streamlit](https://streamlit.io/) app plus a ready-to-run [Postman](https://www.postman.com/) API collection, powered by the **same original Python reliability engine**.

Made by **[Ahmad Yar](https://www.ahmadyar.co/)** · [Try interactive Streamlit lab](https://webhook-reliability-lab.streamlit.app/) · [Published Postman API documentation](https://www.postman.com/cryosat-geoscientist-71511496-s-team/webhook-reliability-lab/documentation/41279717-bf96147e-42da-4eaf-bd4c-dd294fb5d585) · [Live FastAPI docs](https://webhook-reliability-api.vercel.app/docs) · [GitHub source](https://github.com/ahamdjin/webhook-reliability-lab) · MIT licensed

[![Test the Streamlit + Postman lab](https://github.com/ahamdjin/webhook-reliability-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/ahamdjin/webhook-reliability-lab/actions/workflows/ci.yml)

> **This is a local/stateless educational simulator—not a production webhook receiver.** No messages are delivered; no API keys are needed. Never paste private events or real signing secrets into a public demo.

## What can you do?

| Lab | See for yourself | Outcome |
| --- | --- | --- |
| Delivery replay | Send the same event three times | Accepted once; remaining duplicates ignored within TTL |
| Collision | Reuse an event ID with a changed body | Rejected as an ID/body conflict |
| Expiry | Replay after an idempotency TTL | Accepted again—shows why retention matters |
| Payload validation | Remove an ID, timezone or data object | Specific, non-sensitive validation findings |
| Retry scheduling | Simulate 503, 503, 200 or 429, 200 | Show attempt timeline, jitter, cap and Retry-After |
| Signature workshop | Sign, modify, or age a fictional event | See exact-payload HMAC matching and timestamp-window rejection |
| Postman tests | Run 15 documented HTTP requests | Check success, failure, dedup, TTL, backoff, and signatures |

Realistic caveats are built into the explanations: duplicate delivery is normal; a valid signature alone does not prevent replays; deduplication across concurrent/regionally distributed workers requires a **shared atomic durable inbox**, not a Python dictionary.

## Public links

- **[Interactive Streamlit lab](https://webhook-reliability-lab.streamlit.app/)** — browser-based exercises for deduplication, validation, retries, and signatures; no account keys required.
- **[Postman API Network documentation](https://www.postman.com/cryosat-geoscientist-71511496-s-team/webhook-reliability-lab/documentation/41279717-bf96147e-42da-4eaf-bd4c-dd294fb5d585)** — 15 runnable examples and assertions; shared by the maintainer.
- **[FastAPI playground](https://webhook-reliability-api.vercel.app/docs)** — publicly deployed synthetic API.
- **[API health](https://webhook-reliability-api.vercel.app/api/v1/health)** — availability endpoint.

## 1. Run the interactive Streamlit app

**[Open the hosted Streamlit lab](https://webhook-reliability-lab.streamlit.app/)** to try the exercises in your browser, or run it locally from the project root:

~~~bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
~~~

On Windows PowerShell, activate with \`.venv\Scripts\Activate.ps1\`.

The interface opens in your browser. Select a preset, change delays and TTL, edit JSON, and download a structured analysis report. Streamlit invokes the local Python engine; **it does not call our FastAPI service or send any webhooks**.

### Deploy to Streamlit Community Cloud

1. Open [Streamlit Community Cloud](https://share.streamlit.io/) and sign in with GitHub.
2. Select **Create app / Deploy an app** → **I have an app** (labels can change).
3. Repository: \`ahamdjin/webhook-reliability-lab\`; branch: \`main\`.
4. Main file path: **\`streamlit_app.py\`**.
5. Choose an available public app URL, then deploy. The root \`requirements.txt\` provides dependencies.

You do **not** need to configure secrets, environment variables or an endpoint.

**Hosted community app:** [webhook-reliability-lab.streamlit.app](https://webhook-reliability-lab.streamlit.app/). The deployment is independent of the FastAPI/Postman service; it runs simulations with the local Python engine.

## 2. Run the real demo API locally

~~~bash
python -m pip install -r requirements.txt
python -m uvicorn app:app --reload
~~~

Visit [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for interactive FastAPI/OpenAPI documentation. The service is a **real HTTP API for deterministic experiments**, not a real queue consumer. It makes no outbound requests, stores no event history across calls, and is intentionally limited to small synthetic bodies.

| Method | Path | Input |
| --- | --- | --- |
| GET | \`/api/v1/health\` | State + version |
| GET | \`/api/v1/scenarios\` | Five synthetic exercise fixtures |
| POST | \`/api/v1/validate\` | \`{"event": { ... }}\` |
| POST | \`/api/v1/replay\` | \`{"deliveries": [{"at": 0, "event": { ... }}], "ttl_seconds": 300}\` |
| POST | \`/api/v1/retry\` | \`{"statuses": [503, 503, 200], "jitter": 0}\` |
| POST | \`/api/v1/demo-sign\` | \`{"payload": "fictional", "timestamp": 1767268800}\` |
| POST | \`/api/v1/verify-sign\` | Same payload, timestamp and \`signature\`, plus optional \`reference_time\` |

A quick request:

~~~bash
curl -s http://127.0.0.1:8000/api/v1/retry \
  -H 'Content-Type: application/json' \
  -d '{"statuses":[503,503,200],"base_seconds":1,"cap_seconds":60,"jitter":0}'
~~~

The result is a **schedule**, not actual HTTP attempts. The service reports \`no-store\` headers and restricts request bodies to 64 KiB (synthetic data only). Basic error responses do not reflect input values.

### Deploy FastAPI to Vercel (optional but recommended for public Postman examples)

Import the **same repository** again as a separate Vercel project:

1. In [Vercel](https://vercel.com/new), choose **Import Git Repository** → \`ahamdjin/webhook-reliability-lab\`.
2. Select **FastAPI / Python** (or Other if your dashboard does not list FastAPI); use **repository root** as the project root.
3. The root \`app.py\` exports \`app = FastAPI(...)\`; the root \`requirements.txt\` declares dependencies. Avoid specifying a custom build command unless Vercel explicitly requires one.
4. Deploy, then visit \`https://YOUR-DEPLOYMENT.vercel.app/api/v1/health\` and \`.../docs\`.
5. Put that **verified** HTTPS origin in the Postman collection's \`base_url\` variable.

**Production demo currently deployed:** [webhook-reliability-api.vercel.app](https://webhook-reliability-api.vercel.app/docs). A publicly accessible test API may be subject to traffic, misuse and hosting quotas. This project does not implement per-user rate limiting or authentication; configure appropriate Vercel Firewall / traffic controls if deployed publicly. Do not add real provider secrets or production workflows.

## 3. Import into Postman and run tests

Download or import these repository files into [Postman](https://www.postman.com/):

- [15-request Postman collection](postman/Webhook-Reliability-Lab.postman_collection.json)
- [Local Postman environment](postman/Local.postman_environment.json)

With FastAPI running, select the Local environment and open the collection's **Run** view. Run the whole collection in order. It checks expected successes and intentional failures, and sets the example \`demo_signature\` variable before verifying it.

All requests point to \`{{base_url}}\`. The **collection now defaults to \`https://webhook-reliability-api.vercel.app\`** so importing it works for visitors without local setup. The separate \`Local.postman_environment.json\` overrides this with \`http://127.0.0.1:8000\` for localhost development and CI. In Postman select **No environment** to use the public collection default.

For local continuous integration with Newman (Postman Collection v2.1):

~~~bash
npx --yes newman@6 run postman/Webhook-Reliability-Lab.postman_collection.json \
  --environment postman/Local.postman_environment.json
~~~

GitHub Actions runs the collection **against a freshly booted API process**, not a mocked response. See [the CI workflow](.github/workflows/ci.yml). Postman currently recommends Postman CLI for new native v3 Git workflows; this starter deliberately uses the widely importable v2.1 collection format, and Newman exercises that exported file.

### Publish on Postman API Network (requires your Postman account)

1. Sign in to Postman and create or open a workspace that you can make **Public**.
2. Import the collection, select it, and review **every request and variable** for sensitive values (none are intentionally included).
3. Replace \`base_url\` with the verified HTTPS demo API if you want the published examples usable by visitors without running locally.
4. Add a description pointing to [your portfolio](https://www.ahmadyar.co/) and the GitHub repository.
5. Open workspace settings and change the workspace type to **Public**. Publish collection documentation if you also want a shareable public docs URL.
6. Verify the published Postman collection by opening its URL in a logged-out browser and forking it.

**Published documentation:** [Webhook Reliability Lab — Postman](https://www.postman.com/cryosat-geoscientist-71511496-s-team/webhook-reliability-lab/documentation/41279717-bf96147e-42da-4eaf-bd4c-dd294fb5d585). The collection's public workspace/docs publication is a Postman account action, separate from committing the exported JSON here.

## Design and learning boundaries

This project deliberately avoids the misleading approach of pretending a tutorial is a webhook gateway:

- **Deduplication:** The TTL map exists only inside **one simulation call**. No cross-request persistence or race-condition guarantees. Different bodies with the same ID are considered conflicting *within* the TTL. A duplicate past the TTL can be accepted.
- **Retries:** Only a schedule is computed. Status \`0\` stands for a simulated timeout. This is not a transport- or message-queue client.
- **Signatures:** Public training key, exact UTF-8 byte string \`timestamp + "." + payload\`, HMAC-SHA256, and constant-time digest comparison. The signed timestamp may be controlled in demo tests. **It is not GitHub/Stripe signature compatibility or real authentication.**
- **Event contract:** Opinionated learning envelope: \`event_id\`, \`event_type\`, aware ISO timestamp \`occurred_at\`, object \`data\`. Providers have different native schemas.
- **Privacy:** Synthetic inputs only. The API never contacts your own webhook URL or accesses connected accounts. Hosts, proxies and providers may log requests despite our no-store application behavior.
- **Operational safety:** A real webhook receiver needs provider-specific signature verification, durable inbox/queue, atomic dedup across workers, per-provider retries, observability and rate limiting.

See [architecture / production boundaries](docs/ARCHITECTURE.md) for exact flow and a safe SQL inbox pattern, plus [publishing checklist](docs/PUBLISHING.md).

## Test it

~~~bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
~~~

CI runs Python 3.11 and 3.12, Streamlit AppTest, and the complete Postman collection over real local HTTP.

### References

Read the provider's own requirements before implementing real webhooks:

- [GitHub webhook best practices](https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks)
- [Streamlit Community Cloud deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization)
- [Vercel FastAPI deployment](https://vercel.com/docs/frameworks/backend/fastapi)
- [Publish to Postman API Network](https://learning.postman.com/docs/postman-api-network/showcase/publish/overview/)

**Authorship & licensing:** Original MIT-licensed implementation by [Ahmad Yar](https://www.ahmadyar.co/). No third-party repository was copied wholesale. Standard OSS dependencies (Streamlit, FastAPI, Pydantic, Uvicorn, httpx, pytest) retain their own licenses.
