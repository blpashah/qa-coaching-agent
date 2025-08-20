import os, json, re, textwrap
import streamlit as st
import google.generativeai as genai

# ---------- Config ----------
st.set_page_config(page_title="QA Coaching Agent", page_icon="✅", layout="centered")
MODEL_NAME = "gemini-1.5-flash"

# Read key from Streamlit Secrets (preferred) OR environment variable (fallback)
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY", "")

if not GEMINI_API_KEY:
    st.error(
        "Missing GEMINI_API_KEY.\n\n"
        "Locally: create `.streamlit/secrets.toml` with:\n"
        'GEMINI_API_KEY="YOUR_KEY_HERE"\n\n'
        "OR set an env var and restart: export GEMINI_API_KEY=YOUR_KEY_HERE\n\n"
        "On Streamlit Cloud: App ▸ Settings ▸ Secrets."
    )
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(MODEL_NAME)

QA_CRITERIA = [
    "accuracy",
    "empathy_and_tone",
    "clarity",
    "actionability",
    "escalation_awareness"
]

SYSTEM_GUIDE = textwrap.dedent("""
You are a meticulous QA coach for SaaS support agents.
Read the entire ticket transcript (customer, agent, follow-ups).
Score the agent responses on the following 5 criteria from 1–5:
- accuracy
- empathy_and_tone
- clarity
- actionability
- escalation_awareness

Rules:
- Return ONLY valid JSON. No code fences, no commentary.
- JSON schema:
  {
    "criteria_scores": {"accuracy": int, "empathy_and_tone": int, "clarity": int, "actionability": int, "escalation_awareness": int},
    "overall_score": int,
    "coaching_summary": "string with 2-4 crisp, actionable points",
    "suggested_1on1_questions": ["short question 1", "short question 2"]
  }
- overall_score = sum(criteria)
- coaching summary should be specific and actionable
""").strip()


def evaluate_ticket(ticket_text: str) -> dict:
    prompt = f"""{SYSTEM_GUIDE}

TICKET TRANSCRIPT:
{ticket_text}
"""
    resp = model.generate_content(prompt)
    raw = resp.text or ""

    # Extract JSON object from response
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"Model did not return JSON.\nRaw output:\n{raw}")
    data = json.loads(match.group(0))

    # Basic validation
    if "criteria_scores" not in data or "overall_score" not in data:
        raise ValueError(f"JSON missing expected keys.\nGot:\n{data}")
    if set(data["criteria_scores"].keys()) != set(QA_CRITERIA):
        raise ValueError("Criteria keys mismatch.")
    return data


# ---------- UI ----------
st.title("QA Coaching Agent (Free Tier)")
st.caption("Paste a Zendesk-style ticket transcript → get QA scores + coaching summary.")

DEFAULT_SAMPLE = """Customer: Jason Miller (IT Manager, Larkspur Biotech) | Priority: High | Plan: Enterprise Plus | SLA: 4 hrs
Subject: Inconsistent Access to SecureVault — Okta Group Sync Partially Failing

Customer Message
Hi, ...
(You can paste the full sample ticket here from your brief)
"""

ticket = st.text_area("Ticket transcript", value=DEFAULT_SAMPLE, height=320)
col_btn1, col_btn2 = st.columns([1,1])

with col_btn1:
    run_eval = st.button("Evaluate", type="primary")
with col_btn2:
    clear = st.button("Clear")

if clear:
    st.experimental_rerun()

if run_eval:
    with st.spinner("Scoring…"):
        try:
            result = evaluate_ticket(ticket)
        except Exception as e:
            st.error(str(e))
        else:
            st.subheader(f"Overall Score: {result['overall_score']} / 25")

            # Show per-criterion bars
            st.write("### Criteria Scores")
            for k in QA_CRITERIA:
                st.progress(result["criteria_scores"][k] / 5.0, text=f"{k.replace('_',' ').title()}: {result['criteria_scores'][k]} / 5")

            st.write("### Coaching Summary")
            st.write(result["coaching_summary"])

            if result.get("suggested_1on1_questions"):
                st.write("### Suggested 1:1 Questions")
                for q in result["suggested_1on1_questions"]:
                    st.write("• " + q)

            with st.expander("Raw JSON (for debugging)"):
                st.json(result)

st.divider()
st.write("#### ROI Estimator (toy example)")
managers = st.number_input("Managers doing QA", 1, 500, 10)
hrs_saved_per_mgr = st.number_input("Hours saved per manager / week", 1, 20, 4)
hourly_cost = st.number_input("Fully-loaded hourly cost ($)", 20, 300, 70)
weekly_hours = managers * hrs_saved_per_mgr
weekly_savings = weekly_hours * hourly_cost
st.metric("Estimated hours saved / week", f"{weekly_hours}")
st.metric("Estimated cost savings / week", f"${weekly_savings:,.0f}")
