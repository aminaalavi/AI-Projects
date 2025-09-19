import os, json
import streamlit as st
from autogen import AssistantAgent

MODEL_NAME = "gpt-4o-mini"

def build_llm_config(api_key: str):
    return {"config_list":[{"model": MODEL_NAME, "api_key": api_key}], "temperature":0.3}

COACH_SYSTEM = (
    "You are a supportive self-advocacy coach. "
    "You will read the full transcript and give constructive feedback in STRICT JSON only:\n"
    "{\n"
    '  "scores": {"Clarity":0-10,"Assertiveness":0-10,"Evidence":0-10,"Boundaries":0-10},\n'
    '  "tips": ["3 short, actionable improvements"],\n'
    '  "examples": ["2 stronger example phrases"]\n'
    "}\n"
    "No commentary. JSON only."
)

CRITIC_SYSTEM = (
    "You are a direct critic of the USER's advocacy style. "
    "Focus ONLY on the USER's messages (not the challenger). "
    "Identify rhetorical weaknesses and strategy gaps. "
    "Return STRICT JSON only:\n"
    "{\n"
    '  "weaknesses": ["2-4 exact issues, quote user when possible"],\n'
    '  "risks": ["2-4 risks that follow from the user approach"],\n'
    '  "counts": {"apologies":int,"hedges":int,"explicit_asks":int}\n'
    "}\n"
    "No prose, JSON only."
)

def make_challenger_system(role: str) -> str:
    return (
        f"You are roleplaying as the USER's {role}. "
        "Your job is to push back against the USER’s requests. "
        "Be realistic, professional, and never abusive, but you may be curt, dismissive, "
        "condescending, or subtly demeaning. "
        "Always speak IN CHARACTER as that person (never as an observer). "
        "Do not break character. "
        "Keep replies under 80 words."
    )

def challenger_reply(challenger: AssistantAgent, transcript):
    ctx = "\n".join([f"{spk}: {msg}" for spk, msg in transcript[-6:]])
    latest_user = next((m for spk, m in reversed(transcript) if spk.lower()=="user"), "")
    prompt = (
        f"Context so far:\n{ctx}\n\n"
        f"User's latest message:\n{latest_user}\n\n"
        "Reply in character as that role. Keep under 80 words."
    )
    return challenger.generate_reply(messages=[
        {"role":"system","content":challenger.system_message},
        {"role":"user","content":prompt},
    ]).strip()

def evaluate_transcript(transcript, api_key):
    llm_config = build_llm_config(api_key)
    full_text = "\n".join([f"{spk}: {msg}" for spk, msg in transcript])
    user_text = "\n".join([f"User: {m}" for spk, m in transcript if spk.lower()=="user"])
    coach = AssistantAgent(name="Coach", system_message=COACH_SYSTEM, llm_config=llm_config)
    critic = AssistantAgent(name="Critic", system_message=CRITIC_SYSTEM, llm_config=llm_config)
    coach_reply = coach.generate_reply(messages=[{"role":"user","content":f"Transcript:\n{full_text}\n\nProvide JSON now."}])
    critic_reply = critic.generate_reply(messages=[{"role":"user","content":f"Critique ONLY USER lines:\n{user_text}\n\nProvide JSON now."}])
    def safe(txt):
        try: return json.loads(txt.strip())
        except:
            import re
            m = re.search(r"\{.*\}", txt, flags=re.S)
            return json.loads(m.group(0)) if m else {"raw": txt}
    return {"coach": safe(coach_reply), "critic": safe(critic_reply)}

st.set_page_config(page_title="AdvocateAI", page_icon="💬", layout="centered")
st.title("AdvocateAI — Self-Advocacy Practice")

api_key = st.text_input("OpenAI API Key", type="password", value=os.getenv("OPENAI_API_KEY",""))
if api_key: os.environ["OPENAI_API_KEY"] = api_key

role = st.selectbox(
    "Who should the Challenger roleplay as?",
    ["teenager","spouse","parent","sibling","peer","boss","customer service rep","roommate","friend","teacher","landlord","other"],
    index=0
)
if role == "other":
    role = st.text_input("Enter a custom role:", "").strip() or "peer"

if "transcript" not in st.session_state: st.session_state.transcript = []
if "challenger_role" not in st.session_state: st.session_state.challenger_role = None
if "challenger_agent" not in st.session_state: st.session_state.challenger_agent = None

def ensure_agent(role, api_key):
    changed_role = (st.session_state.challenger_role != role)
    missing = st.session_state.challenger_agent is None
    if not api_key: return
    if changed_role or missing:
        llm_config = build_llm_config(api_key)
        st.session_state.challenger_agent = AssistantAgent(
            name="Challenger",
            system_message=make_challenger_system(role),
            llm_config=llm_config,
        )
        st.session_state.challenger_role = role
        st.session_state.transcript = []

ensure_agent(role, api_key)

st.write("Type a message, press Send. Click Evaluate anytime for feedback.")

with st.form("chat"):
    user_msg = st.text_area("Your message", height=110, placeholder="State your ask / boundary...")
    submitted = st.form_submit_button("Send")
    if submitted and user_msg.strip():
        st.session_state.transcript.append(("User", user_msg.strip()))
        if not api_key:
            st.warning("Please add your API key first.")
        elif st.session_state.challenger_agent is None:
            st.warning("Set the role to create the Challenger.")
        else:
            reply = challenger_reply(st.session_state.challenger_agent, st.session_state.transcript)
            st.session_state.transcript.append(("Challenger", reply))

st.subheader("Transcript")
for spk, msg in st.session_state.transcript:
    st.markdown(f"**{spk}:** {msg}")

c1, c2 = st.columns(2)
with c1:
    if st.button("Evaluate"):
        if not api_key:
            st.warning("Please add your API key.")
        elif not st.session_state.transcript:
            st.info("Start a conversation first.")
        else:
            results = evaluate_transcript(st.session_state.transcript, api_key)
            st.subheader("Coach (scorecard)")
            st.json(results.get("coach", {}))
            st.subheader("Critic (diagnostics)")
            st.json(results.get("critic", {}))
with c2:
    if st.button("Reset conversation"):
        st.session_state.transcript = []
