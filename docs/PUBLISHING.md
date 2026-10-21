# Launch checklist — Streamlit + Postman

Both products use ONE GitHub repository: https://github.com/ahamdjin/webhook-reliability-lab .

Current public app: https://webhook-reliability-lab.streamlit.app/ . API documentation: https://webhook-reliability-api.vercel.app/docs . Postman documentation: https://www.postman.com/cryosat-geoscientist-71511496-s-team/webhook-reliability-lab/documentation/41279717-bf96147e-42da-4eaf-bd4c-dd294fb5d585 .

## First verify and merge the PR

Wait for GitHub Actions to pass Python 3.11 / 3.12 unit tests, Streamlit AppTest, and the complete Postman collection running over real local HTTP. Merge to main only after checks pass.

## Streamlit Community Cloud

1. Visit https://share.streamlit.io/ and sign in with GitHub.
2. Choose New app and select existing repository.
3. Repository: ahamdjin/webhook-reliability-lab.
4. Branch: main.
5. Main file: streamlit_app.py.
6. Deploy and test each tab with example data. Download one report. There are no secrets or environment variables to configure.
7. The maintainer's public app is https://webhook-reliability-lab.streamlit.app/ . Check all tabs and JSON report downloads after changes.

## HTTP playground endpoint for Postman

1. Import the same repository as a separate **FastAPI/Python project** at https://vercel.com/new .
2. Use repository root as the project root. Root app.py exports a real FastAPI app; root requirements.txt supplies dependencies.
3. Deploy; check the returned HTTPS address at /api/v1/health and /docs.
4. Set the Postman base_url variable to the validated HTTPS origin, without trailing slash. Run all 15 Postman requests.
5. Before sharing broadly, review Vercel Firewall/traffic protection, logs and hosting usage quotas. The educational API has no authentication and should not receive private data.

This FastAPI endpoint is independent from the hosted Streamlit application and must never receive real secrets or private events.

## Postman API Network

1. Sign in to Postman and create a new workspace eligible for **Public** visibility.
2. Import postman/Webhook-Reliability-Lab.postman_collection.json.
3. Optionally import postman/Local.postman_environment.json for development.
4. Confirm all 15 test requests run with the public HTTPS base_url; never publish credential-bearing environments or values.
5. Add your portfolio https://www.ahmadyar.co/ and repository link to the collection description.
6. Make workspace Public, publish collection documentation if desired, and copy the true public workspace or collection URL.
7. Test the resulting public link in a logged-out browser; then add it to your portfolio.

Docs: https://learning.postman.com/docs/postman-api-network/showcase/publish/overview/

## Portfolio copy (after links are live)

Webhook Reliability Lab — an interactive lab for webhook replay, TTL deduplication, changed-payload collisions, validation, retry planning and signing. Includes a real bounded FastAPI test endpoint, Streamlit interface, 15-request tested Postman collection and CI suite. MIT open source by Ahmad Yar.

This is a deterministic education/demo project, not production-grade distributed delivery infrastructure.