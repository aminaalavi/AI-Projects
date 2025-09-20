import os
import json
import streamlit as st
from autogen import AssistantAgent

MODEL_NAME = "gpt-4o-mini"

SCORE_RULES_TEXT = (
    "Scoring: +10 points if the Judge is convinced (win). "
    "+2 points for a strong attempt when confidence ≥ 0.50. "
    "+1 bonus if your last message contained a clear ask, boundary, or concrete evidence."
)

# ------------------- PRETTY HELPERS -------------------
def _score_bar(label: str, value: int | float):
    v = max(0, min(10, float(value)))
    st.metric(label, f"{int(v)}/10")
    st.progress(v/10)

def render_coach(coach: dict):
    st.subheader("Coach (scorecard)")
    if not isinstance(coach, dict):
        st.info("No coach data.")
        return
    scores = coach.get("scores", {}) or {}
    tips   = coach.get("tips", []) or []
    exs    = coach.get("examples", []) or []
    cols = st.columns(4)
    order = ["Clarity", "Assertiveness", "Evidence", "Boundaries"]
    for i, k in enumerate(order):
        with cols[i]:
            _score_bar(k, scores.get(k, 0))
    if tips:
        st.markdown("**Tips (try these next time):**")
        for t in tips:
            st.markdown(f"- {t}")
    if exs:
        st.markdown("**Stronger example phrases:**")
        for e in exs:
            st.markdown(f"> {e}")

def render_critic(critic: dict):
    st.subheader("Critic (diagnostics)")
    if not isinstance(critic, dict):
        st.info("No critic data.")
        return
    weaknesses = critic.get("weaknesses", []) or []
    risks      = critic.get("risks", []) or []
    counts     = critic.get("counts", {}) or {}
    if weaknesses:
        st.markdown("**Weaknesses spotted:**")
        for w in weaknesses:
            st.markdown(f"- {w}")
    if risks:
        st.markdown("**Risks if you keep this pattern:**")
        for r in risks:
            st.markdown(f"- {r}")
    if counts:
        st.markdown("**Counts**")
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Apologies", counts.get("apologies", 0))
        with c2: st.metric("Hedges", counts.get("hedges", 0))
        with c3: st.metric("Explicit asks", counts.get("explicit_asks", 0))

# ------------------- LLM SYSTEMS -------------------
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

JUDGE_SYSTEM = (
    "You are a generous referee. Decide if the Challenger would now concede/agree "
    "based on the USER's **latest** message and immediate context. Be lenient: "
    "if the USER makes a clear, specific ask OR adds concrete evidence OR sets a firm boundary, "
    "lean toward convinced. Return STRICT JSON only:\n"
    "{"
    '  "convinced": true|false,'
    '  "confidence": 0.0-1.0,'
    '  "why": "1-2 sentence reason",'
    '  "tips": ["up to 2 short improvements for next turn"]'
    "}"
)

# ------------------- LOGIC -------------------
def judge_turn(transcript, api_key):
    llm_config = build_llm_config(api_key)
    judge = AssistantAgent(name="Judge", system_message=JUDGE_SYSTEM, llm_config=llm_config)
    ctx = "\n".join([f"{spk}: {msg}" for spk, msg in transcript[-4:]])
    prompt = "Decide if the Challenger would concede now based on this recent exchange.\n" + ctx + "\nReturn JSON only."
    raw = judge.generate_reply(messages=[{"role":"user","content":prompt}])
    try:
        data = json.loads(raw.strip())
    except Exception:
        import re
        m = re.search(r"\{.*\}", raw, flags=re.S)
        data = json.loads(m.group(0)) if m else {"convinced": False, "confidence": 0.0, "why": "Parse error", "tips": []}
    data.setdefault("convinced", False)
    data.setdefault("confidence", 0.0)
    data.setdefault("why", "")
    data.setdefault("tips", [])
    last_user = ""
    for spk, m in reversed(transcript):
        if spk.lower() == "user":
            last_user = m.lower()
            break
    keywords_ask = ["i want", "i need", "i would like", "i’m asking", "i am asking"]
    keywords_boundary = ["i won’t", "not acceptable", "that doesn’t work", "i can’t agree"]
    has_evidence = any(ch.isdigit() for ch in last_user) or "$" in last_user or "%" in last_user
    clear_ask = any(k in last_user for k in keywords_ask)
    clear_bound = any(k in last_user for k in keywords_boundary)
    conf = float(data.get("confidence", 0) or 0)
    if (clear_ask or clear_bound or has_evidence) and conf >= 0.30:
        data["convinced"] = True
        data["confidence"] = max(conf, 0.55)
    data["_has_signal"] = bool(clear_ask or clear_bound or has_evidence)
    return data

def make_challenger_system(role: str, level: int) -> str:
    tones = {1: "polite but firm", 3: "curt, slightly dismissive", 5: "sharply dismissive (still non-abusive)"}
    style = tones.get(level, "curt")
    return f"You are roleplaying as the USER's {role}. Your pushback intensity is {level}/5 and your tone is {style}. Be realistic, never abusive, but you may be curt, dismissive, or subtly demeaning. Stay in character. Keep replies under 80 words."

def challenger_reply(challenger: AssistantAgent, transcript):
    ctx = "\n".join([f"{spk}: {msg}" for spk, msg in transcript[-6:]])
    latest_user = next((m for spk, m in reversed(transcript) if spk.lower() == "user"), "")
    prompt = f"Context so far:\n{ctx}\n\nUser's latest message:\n{latest_user}\n\nReply IN CHARACTER as the assigned role with the specified pushback intensity. Keep your message under 80 words."
    return challenger.generate_reply(messages=[{"role": "system", "content": challenger.system_message},{"role": "user", "content": prompt},]).strip()

def evaluate_transcript(transcript, api_key):
    llm_config = build_llm_config(api_key)
    full_text = "\n".join([f"{spk}: {msg}" for spk, msg in transcript])
    user_text = "\n".join([f"User: {m}" for spk, m in transcript if spk.lower()=="user"])
    coach = AssistantAgent(name="Coach", system_message=COACH_SYSTEM, llm_config=llm_config)
    critic = AssistantAgent(name="Critic", system_message=CRITIC_SYSTEM, llm_config=llm_config)
    coach_reply = coach.generate_reply(messages=[{"role":"user","content":f"Transcript:\n{full_text}\n\nProvide JSON now."}])
    critic_reply = critic.generate_reply(messages=[{"role":"user","content":f"Critique ONLY USER lines:\n{user_text}\n\nProvide JSON now."}])
    def safe(txt):
        try:
            return json.loads(txt.strip())
        except Exception:
            import re
            m = re.search(r"\{.*\}", txt, flags=re.S)
            return json.loads(m.group(0)) if m else {"raw": txt}
    return {"coach": safe(coach_reply), "critic": safe(critic_reply)}

# ---------------- STREAMLIT APP ----------------
st.set_page_config(page_title="AdvocateAI", page_icon="💬", layout="centered")
st.title("AdvocateAI — Self-Advocacy Practice")

# Init states
if "transcript" not in st.session_state: st.session_state.transcript = []
if "challenger_role" not in st.session_state: st.session_state.challenger_role = None
if "challenger_agent" not in st.session_state: st.session_state.challenger_agent = None
if "chat_input" not in st.session_state: st.session_state.chat_input = ""
if "game_active" not in st.session_state: st.session_state.game_active = False
if "game_over" not in st.session_state: st.session_state.game_over = False
if "turns" not in st.session_state: st.session_state.turns = 0
if "max_turns" not in st.session_state: st.session_state.max_turns = 3
if "score" not in st.session_state: st.session_state.score = 0
if "streak" not in st.session_state: st.session_state.streak = 0
if "mode" not in st.session_state: st.session_state.mode = "regular"
if "last_verdict" not in st.session_state: st.session_state.last_verdict = None

api_key = st.text_input("OpenAI API Key", type="password", value=os.getenv("OPENAI_API_KEY",""))
if api_key: os.environ["OPENAI_API_KEY"] = api_key

role = st.selectbox("Who should the Challenger roleplay as?",["teenager","spouse","parent","sibling","peer","boss","customer service rep","roommate","friend","teacher","landlord","other"],index=5)
difficulty = st.slider("Difficulty (pushback level)", 1, 5, 3)
if role == "other":
    role = st.text_input("Enter a custom role:", "").strip() or "boss"

# Mode buttons
m1, m2 = st.columns(2)
with m1:
    if st.button("🎮 Game mode"):
        st.session_state.mode = "game"; st.session_state.game_active=True; st.session_state.game_over=False
        st.session_state.turns=0; st.session_state.score=0; st.session_state.streak=0; st.session_state.transcript=[]
        st.success("Game mode: started a new game (3 turns). Convince the Challenger!")
with m2:
    if st.button("🗨️ Regular mode"):
        st.session_state.mode="regular"; st.session_state.game_active=False; st.session_state.game_over=False
        st.info("Regular mode: free practice. No turns, no scoring.")

# Agent setup
def ensure_agent(role: str, difficulty: int, api_key: str):
    if not api_key: return
    changed_role = (st.session_state.get("challenger_role") != role)
    changed_diff = (st.session_state.get("challenger_difficulty") != difficulty)
    missing = st.session_state.get("challenger_agent") is None
    if changed_role or changed_diff or missing:
        llm_config = build_llm_config(api_key)
        st.session_state.challenger_agent = AssistantAgent(name="Challenger",system_message=make_challenger_system(role, difficulty),llm_config=llm_config)
        st.session_state.challenger_role = role
        st.session_state.challenger_difficulty = difficulty
        st.session_state.transcript=[]

ensure_agent(role, difficulty, api_key)

# Chat input form
with st.form("chat_form", clear_on_submit=True):
    user_msg = st.text_area("Your message", height=110, placeholder="State your ask / boundary...", disabled=(st.session_state.mode=="game" and st.session_state.get("game_over")), key="chat_input")
    submitted = st.form_submit_button("Send", disabled=(st.session_state.mode=="game" and st.session_state.get("game_over")))

if submitted and user_msg.strip():
    st.session_state.transcript.append(("User", user_msg.strip()))
    if api_key and st.session_state.challenger_agent:
        reply = challenger_reply(st.session_state.challenger_agent, st.session_state.transcript)
        st.session_state.transcript.append(("Challenger", reply))
        verdict = judge_turn(st.session_state.transcript, api_key)
        st.session_state.last_verdict = verdict
        if st.session_state.mode=="game" and st.session_state.get("game_active") and not st.session_state.get("game_over"):
            if verdict.get("_has_signal"): st.session_state.score+=1
            if verdict.get("confidence",0)>=0.5: st.session_state.score+=2
            if verdict.get("convinced",False):
                st.session_state.score+=10; st.session_state.streak+=1; st.session_state.game_over=True
            else:
                st.session_state.turns+=1
                if st.session_state.turns>=st.session_state.max_turns:
                    st.session_state.streak=0; st.session_state.game_over=True

# Judge section
_last = st.session_state.get("last_verdict")
st.subheader("Judge")
if _last:
    if _last.get("convinced",False):
        st.success(f"Convinced ✅ (confidence {_last.get('confidence',0):.2f}) — You win!")
    else:
        st.info(f"Not convinced yet (confidence {_last.get('confidence',0):.2f}). Keep going.")
    if _last.get("why"): st.caption(f"Why: {_last['why']}")
    tips = _last.get("tips", [])
    if tips:
        st.markdown("**Try next:**")
        for t in tips: st.markdown(f"- {t}")
else:
    st.caption("No verdict yet — send a message to get a ruling.")

# Transcript display
st.subheader("Transcript")
for spk,msg in st.session_state.transcript:
    st.markdown(f"**{spk}:** {msg}")

# Evaluation buttons
c1, c2 = st.columns(2)
with c1:
    if st.button("Evaluate"):
        if not api_key:
            st.warning("Please add your API key.")
        elif not st.session_state.transcript:
            st.info("Start a conversation first.")
        else:
            results = evaluate_transcript(st.session_state.transcript, api_key)
            coach = results.get("coach", {})
            critic = results.get("critic", {})
            render_coach(coach)
            st.markdown("---")
            render_critic(critic)
with c2:
    if st.button("Reset conversation"):
        st.session_state.transcript = []
