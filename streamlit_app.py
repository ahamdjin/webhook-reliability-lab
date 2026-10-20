"""Interactive Streamlit teaching experience powered by the shared Python engine."""
from __future__ import annotations

import json
import time

import streamlit as st

from reliability_lab.core import (
    VERSION, analyze_deliveries, demo_signature, example_event, plan_retries,
    sample_scenario, validate_event, verify_demo_signature,
)

st.set_page_config(
    page_title="Webhook Reliability Lab · Ahmad Yar",
    page_icon="🔁",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root { --lab-accent: #46d6ac; }
    .block-container { max-width: 1280px; padding-top: 2.0rem; }
    div[data-testid="stMetric"] {
        background: rgba(112, 133, 160, .08);
        border: 1px solid rgba(139, 154, 170, .20);
        border-radius: 12px;
        padding: 12px 16px;
    }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; }
    .lab-kicker { letter-spacing: .16em; font-size: .75rem; font-weight: 700;
        color: #24a682; text-transform: uppercase; }
    .lab-subtitle { max-width: 800px; opacity: .76; margin: 0 0 1rem; }
    .lab-banner { background: rgba(112,133,160,.08); padding: 14px 18px;
        border-radius: 12px; border: 1px solid rgba(139,154,170,.18); }
    .lab-banner b { color: #24a682; }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### 🔁 Webhook Reliability Lab")
    st.caption(f"Interactive engineering sandbox · v{VERSION}")
    st.markdown("**Your playground**")
    st.markdown(
        "Test idempotency, payload validation, backoff and signed deliveries "
        "with fictional examples—without hitting a real webhook."
    )
    st.divider()
    st.markdown("**How this works**")
    st.caption("Simulations run in this Streamlit process. Nothing is sent to a third-party endpoint.")
    st.markdown("[GitHub source](https://github.com/ahamdjin/webhook-reliability-lab)")
    st.markdown("[Created by Ahmad Yar](https://www.ahmadyar.co/)")
    st.divider()
    st.warning(
        "Do not paste customer data, credentials or actual signing secrets. "
        "A hosted Streamlit service may log application activity."
    )

st.markdown('<div class="lab-kicker">Engineering playground / automation</div>', unsafe_allow_html=True)
st.title("Webhook Reliability Lab")
st.markdown(
    '<p class="lab-subtitle">See why events get processed twice, when retries are safe, '
    'and where validation breaks. Explore deterministic examples and inspect every decision.</p>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="lab-banner"><b>Sandbox only.</b> No real events are delivered, '
    'no credentials are needed, and no persistent database is used. '
    'All sample payloads are fictional.</div>',
    unsafe_allow_html=True,
)
st.write("")

tabs = st.tabs([
    "01 · Replay & deduplication",
    "02 · Validate payload",
    "03 · Retry planner",
    "04 · Signature lab",
    "05 · Implementation notes",
])

with tabs[0]:
    st.subheader("Simulate deliveries")
    st.caption(
        "Within the selected TTL, the first well-formed event ID is accepted; "
        "exact duplicates are ignored; the same ID with changed data is rejected. "
        "After TTL expiry, that ID can be accepted again."
    )
    left, right = st.columns([1, 2], gap="large")
    with left:
        presets = {
            "Duplicate delivery": "duplicate_delivery",
            "Happy path": "happy_path",
            "Changed payload / same ID": "collision",
            "Expired deduplication key": "expired_replay",
            "Invalid then valid": "invalid_payload",
        }
        chosen = st.selectbox("Scenario", list(presets), index=0)
        ttl = st.slider("Idempotency window (seconds)", 1, 600, 300, 1)
        st.caption("Simulation assumes a single ordered worker and an in-memory TTL map.")
        if st.button("Reset to sample", use_container_width=True):
            st.session_state["delivery_text"] = json.dumps(sample_scenario(presets[chosen]), indent=2)
            st.session_state["delivery_choice"] = chosen
    if "delivery_text" not in st.session_state or st.session_state.get("delivery_choice") != chosen:
        st.session_state["delivery_text"] = json.dumps(sample_scenario(presets[chosen]), indent=2)
        st.session_state["delivery_choice"] = chosen
    with right:
        st.text_area("Delivery list · editable JSON", key="delivery_text", height=250,
                     help='Each item: {"at": 0, "event": { "event_id": "...", ... }}')
    try:
        deliveries = json.loads(st.session_state["delivery_text"])
        report = analyze_deliveries(deliveries, ttl_seconds=ttl)
        summary = report["summary"]
        a, b, c, d = st.columns(4)
        a.metric("Accepted", summary["accepted"])
        b.metric("Duplicates skipped", summary["ignored_duplicate"])
        c.metric("ID collisions", summary["rejected_collision"])
        d.metric("Invalid events", summary["rejected_invalid"])
        st.markdown("#### Decision timeline")
        st.dataframe(
            [{"Delivery": d["index"], "Second": d["at"],
              "Decision": d["action"].replace("_", " ").title(),
              "Reason": d["rule"], "Active keys": d["active_keys"]}
             for d in report["deliveries"]],
            use_container_width=True, hide_index=True,
        )
        st.download_button("Export simulation report (.json)", json.dumps(report, indent=2),
                           "webhook-replay-report.json", mime="application/json",
                           key="download_replay")
        with st.expander("What this simulation does NOT prove"):
            for limitation in report["limitations"]:
                st.markdown("- " + limitation)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        st.error(f"Please correct the delivery list: {exc if not isinstance(exc, json.JSONDecodeError) else 'invalid JSON'}")

with tabs[1]:
    st.subheader("Validate an event envelope")
    st.caption("A small documented webhook contract. Unlike arbitrary JSON Schema, this is a deliberately minimal learning schema.")
    if "validation_text" not in st.session_state:
        st.session_state["validation_text"] = json.dumps(example_event(), indent=2)
    st.text_area("Your JSON event", key="validation_text", height=230)
    try:
        incoming = json.loads(st.session_state["validation_text"])
        result = validate_event(incoming)
        if result["valid"]:
            st.success("Valid event envelope according to this lab's contract.")
        else:
            st.error(f"Validation found {len(result['errors'])} problem(s).")
            st.dataframe(result["errors"], use_container_width=True, hide_index=True)
        st.caption("Required: event_id, event_type, occurred_at (timezone-aware ISO 8601), and object data. Maximum event size: 16 KB.")
        st.download_button("Export validation result (.json)", json.dumps(result, indent=2),
                           "webhook-validation.json", mime="application/json", key="download_validate")
    except (json.JSONDecodeError, ValueError) as exc:
        st.error("Input must be valid JSON. No validation call was made.")

with tabs[2]:
    st.subheader("Plan retries—without sending requests")
    st.caption("Set the response sequence. 0 represents a timeout; 429/503 may supply Retry-After. Retryable: 0, 408, 425, 429, 500, 502, 503, 504.")
    p1, p2 = st.columns([2, 1], gap="large")
    with p1:
        statuses_text = st.text_input("Status code sequence · comma-separated", "503, 503, 200")
        base = st.number_input("Initial backoff (seconds)", min_value=0.1, max_value=120.0,
                               value=1.0, step=0.5)
        cap = st.number_input("Maximum backoff (seconds)", min_value=0.1, max_value=3600.0,
                              value=60.0, step=1.0)
    with p2:
        jitter = st.slider("Jitter proportion", 0.0, 0.5, 0.2, step=0.05)
        seed = st.number_input("Random seed (reproducible)", min_value=0,
                               max_value=1_000_000, value=7, step=1)
        use_retry_after = st.checkbox("Simulate Retry-After header", value=False)
        after = (st.number_input("Retry-After (seconds)", min_value=0.0,
                                 max_value=3600.0, value=10.0)
                 if use_retry_after else None)
    try:
        statuses = [int(item.strip()) for item in statuses_text.split(",") if item.strip()]
        strategy = plan_retries(statuses, base_seconds=base, cap_seconds=cap,
                                jitter=jitter, seed=int(seed), retry_after_seconds=after)
        p, q, r = st.columns(3)
        p.metric("Attempted", len(strategy["attempts"]))
        q.metric("Total planned wait", f"{strategy['total_wait_seconds']:g}s")
        r.metric("Final outcome", strategy["final_outcome"].replace("_", " "))
        st.dataframe(strategy["attempts"], use_container_width=True, hide_index=True)
        st.line_chart(
            {"Elapsed seconds": {str(x["attempt"]): x["at_seconds"] for x in strategy["attempts"]}},
            height=230,
        )
        st.download_button("Export retry plan (.json)", json.dumps(strategy, indent=2),
                           "webhook-retry-plan.json", mime="application/json", key="download_retry")
    except (ValueError, TypeError):
        st.error("Enter 1–12 valid HTTP status codes (100–599) or 0, with a backoff cap greater than or equal to the base.")

with tabs[3]:
    st.subheader("Understand signed deliveries")
    st.warning(
        "This section uses a PUBLIC training key. It is not a production signing service. "
        "Never paste your provider's secret or a private payload."
    )
    if "signature_time" not in st.session_state:
        st.session_state["signature_time"] = int(time.time())
    s1, s2 = st.columns(2, gap="large")
    with s1:
        payload = st.text_area("Synthetic body (bytes matter)", '{"event_id":"evt_demo_001"}',
                               height=120)
        timestamp = st.number_input("Signed Unix timestamp", min_value=0,
                                     max_value=4_000_000_000, key="signature_time")
        tolerance = st.slider("Allowed clock drift (seconds)", 1, 900, 300)
        signature = demo_signature(payload, int(timestamp))
        st.code(signature, language="text")
        st.caption("Message: UTF-8 bytes of timestamp + '.' + exact UTF-8 payload.")
    with s2:
        edited_sig = st.text_input("Signature to verify (change it to simulate tampering)",
                                    signature, key="signature_input")
        reference = st.number_input("Receiver clock (Unix seconds)",
                                    min_value=0, max_value=4_000_000_000,
                                    value=int(timestamp), key="signature_clock")
        outcome = verify_demo_signature(
            payload, int(timestamp), edited_sig,
            reference_time=int(reference), tolerance_seconds=tolerance,
        )
        if outcome["valid"]:
            st.success("Signature and timestamp checks passed in this simulated window.")
        else:
            st.error(f"Rejected: {outcome['reason'].replace('_', ' ')}")
        st.json(outcome)
        st.caption("Replay prevention still requires durable event-ID deduplication, even when a signature passes.")

with tabs[4]:
    st.subheader("How to build a reliable webhook receiver")
    st.markdown(
        """
        **1. Authenticate before processing.** Verify the provider's documented
        signature format against the exact raw request bytes, use a timestamp window,
        and rotate real secrets through a secret manager.

        **2. Validate the payload contract.** Reject malformed events explicitly.
        Apply byte limits before JSON parsing and never copy credentials into logs.

        **3. Enforce idempotency atomically.** In production, use a database unique
        constraint or a safe atomic key acquisition across workers—not a Python
        dictionary in each instance.

        **4. Acknowledge only durable work.** For asynchronous handling, write the
        event to a durable queue or inbox transactionally before returning success.
        Account for worker crashes and dead-letter handling.

        **5. Retry selectively.** Handle network timeouts, 429, 408 and transient 5xx
        with capped exponential backoff, bounded attempts, jitter, and Retry-After
        where appropriate. Do not blindly retry authentication or malformed requests.

        **6. Observe the delivery lifecycle.** Track attempt IDs, accepted IDs,
        duplicates, invalid events, processing outcomes, dead letters and latency.
        Avoid logging raw payloads.

        This lab isolates individual concepts. It is **not** a production webhook
        gateway, race-condition test or security certification.
        """
    )
    st.markdown("**One repository · two distribution surfaces:**")
    st.markdown(
        "The [Postman collection](https://github.com/ahamdjin/webhook-reliability-lab/tree/main/postman) "
        "calls a bounded FastAPI demo service. "
        "The Streamlit interface calls the same Python engine directly, with no public API required."
    )
    with st.expander("Run the FastAPI demo locally"):
        st.code(
            "python -m pip install -r requirements.txt\n"
            "python -m uvicorn app:app --reload\n"
            "# Visit http://127.0.0.1:8000/docs",
            language="bash",
        )

st.divider()
st.caption(
    "Built by Ahmad Yar · MIT licensed · Synthetic inputs only · "
    "[Source code](https://github.com/ahamdjin/webhook-reliability-lab) · "
    "[Portfolio](https://www.ahmadyar.co/)"
)
