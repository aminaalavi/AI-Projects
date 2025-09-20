import os
import json
import streamlit as st
from autogen import AssistantAgent

# -------------------- CONFIG --------------------
MODEL_NAME = "gpt-4o-mini"

# -------------------- LLM SYSTEMS --------------------
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
    "You are a fair referee. Decide if the Challenger would now concede/agree "
    "based on the USER's latest message and immediate context. "
    "Look for a clear ask with specifics (amount/timeline), a firm boundary, or a brief reason/evidence. "
    "Return STRICT JSON only:\n"
    "{"
    '  "convinced": true|false,'
    '  "confidence": 0.0-1.0,'
    '  "why": "1-2 sentence reason",'
    '  "tips": ["up to 2 short improvements for next turn"]'
    "}"
)

# -------------------- HELPERS (UI) --------------------
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

# -------------------- CORE LOGIC --------------------
def make_challenger_system(role: str, level: int) -> str:
    tones = {1: "polite but firm", 3: "curt, slightly dismissive", 5: "sharply dismissive (still non-abusive)"}
    style = tones.get(level, "curt")
    return (
        f"You are roleplaying as the USER's {role}. "
        f"Your pushback intensity is {level}/5 and your tone is {style}. "
        "Be realistic, never abusive, but you may be curt, dismissive, or subtly demeaning. "
        "Stay in character. Keep replies under 80 words."
    )

def challenger_reply(challenger: AssistantAgent, transcript):
    """Normal (pushback) reply from the challenger."""
    ctx = "\n".join([f"{spk}: {msg}" for spk, msg in transcript[-6:]])
    latest_user = next((m for spk, m in reversed(transcript) if spk.lower() == "user"), "")
    prompt = (
        f"Context so far:\n{ctx}\n\n"
        f"User's latest message:\n{latest_user}\n\n"
        "Reply IN CHARACTER as the assigned role with the specified pushback intensity. "
        "Keep your message under 80 words."
    )
    return challenger.generate_reply(messages=[
        {"role": "system", "content": challenger.system_message},
        {"role": "user", "content": prompt},
    ]).strip()

def challenger_concede_message(role: str) -> str:
    """What the challenger says when conceding after the Judge is convinced."""
    return (
        "Alright, you’ve presented a clear case. I agree to your request and will proceed."
        if role != "customer service rep"
        else "You’re right—consider it approved. I’ll process this now."
    )

def judge_turn(transcript, api_key):
    """
    Judge with balanced strictness:
    - Convinced if there's a boundary OR (ask + amount/timeline) OR (ask + brief reason),
      AND model confidence is moderate.
    """
    llm_config = build_llm_config(api_key)
    judge = AssistantAgent(name="Judge", system_message=JUDGE_SYSTEM, llm_config=llm_config)

    # recent context
    ctx = "\n".join([f"{spk}: {msg}" for spk, msg in transcript[-4:]])
    prompt = (
        "Decide if the Challenger would concede now based on this recent exchange.\n"
        f"{ctx}\n"
        "Return JSON only."
    )
    raw = judge.generate_reply(messages=[{"role":"user","content":prompt}])

    # parse JSON safely
    try:
        data = json.loads(raw.strip())
    except Exception:
        import re
        m = re.search(r"\{.*\}", raw, flags=re.S)
        data = json.loads(m.group(0)) if m else {"convinced": False, "confidence": 0.0, "why": "Parse error", "tips": []}

    # defaults
    data.setdefault("convinced", False)
    data.setdefault("confidence", 0.0)
    data.setdefault("why", "")
    data.setdefault("tips", [])

    # analyze only the last USER message
    last_user = ""
    for spk, m in reversed(transcript):
        if spk.lower() == "user":
            last_user = m.lower()
            break

    # signals
    clear_ask = any(k in last_user for k in [
        "i want", "i need", "i would like", "i’m asking", "i am asking",
        "i request", "i expect", "i'm requesting", "i am requesting"
    ])
    has_amount = any(ch.isdigit() for ch in last_user) or "$" in last_user or "%" in last_user
    has_timeline = any(t in last_user for t in [
        "by ", "before ", "this week", "this month", "this quarter", "today", "tomorrow",
        "by eod", "by end of day", "by friday", "by monday"
    ])
    has_boundary = any(b in last_user for b in [
        "i won’t", "i will not", "not acceptable", "that doesn’t work", "that does not work",
        "i can’t agree", "i cannot agree", "i'm not able to", "i am not able to"
    ])
    has_reason = any(r in last_user for r in ["because", "since ", "due to", "so that", "as "])

    conf = float(data.get("confidence", 0) or 0)

    # balanced thresholds (not too lenient, not too strict)
    strong_substance = has_boundary or (clear_ask and (has_amount or has_timeline)) or (clear_ask and has_reason)
    two_signals = sum([has_boundary, has_amount, has_timeline, has_reason, clear_ask]) >= 2

    if has_boundary and conf >= 0.58:
        data["convinced"] = True
        data["confidence"] = max(conf, 0.60)
    elif clear_ask and (has_amount or has_timeline) and conf >= 0.63:
        data["convinced"] = True
        data["confidence"] = max(conf, 0.65)
    elif clear_ask and has_reason and conf >= 0.65:
        data["convinced"] = True
        data["confidence"] = max(conf, 0.67)
    elif strong_substance and two_signals and conf >= 0.62:
        data["convinced"] = True
        data["confidence"] = max(conf, 0.64)

    # attach a small flag for UI (kept for future use if needed)
    data["_has_signal"] = bool(clear_ask or has_amount or has_timeline or has_boundary or has_reason)
    return data

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

# -------------------- STREAMLIT APP --------------------
st.set_page_config(page_title="AdvocateAI", page_icon="💬", layout="centered")
st.title("AdvocateAI — Self-Advocacy Practice")

# very brief how-to
st.info("How to use: pick a role, type your ask, and send. In Game mode you get 3 tries to convince the Challenger. Over time it trains you to be clearer, more assertive, and better at self-advocating.")

# Init states
if "transcript" not in st.session_state: st.session_state.transcript = []
if "challenger_role" not in st.session_state: st.session_state.challenger_role = None
if "challenger_agent" not in st.session_state: st.session_state.challenger_agent = None
if "chat_input" not in st.session_state: st.session_state.chat_input = ""
if "game_active" not in st.session_state: st.session_state.game_active = False
if "game_over" not in st.session_state: st.session_state.game_over = False
if "turns" not in st.session_state: st.session_state.turns = 0
if "max_turns" not in st.session_state: st.session_state.max_turns = 3
if "mode" not in st.session_state: st.session_state.mode = "regular"
if "last_verdict" not in st.session_state: st.session_state.last_verdict = None
if "convinced_win" not in st.session_state: st.session_state.convinced_win = False  # blocks input after win in any mode

api_key = st.text_input("OpenAI API Key", type="password", value=os.getenv("OPENAI_API_KEY",""))
if api_key: os.environ["OPENAI_API_KEY"] = api_key

# Default role = boss
role = st.selectbox(
    "Who should the Challenger roleplay as?",
    ["teenager","spouse","parent","sibling","peer","boss","customer service rep","roommate","friend","teacher","landlord","other"],
    index=5
)
difficulty = st.slider("Difficulty (pushback level)", 1, 5, 3)
if role == "other":
    role = st.text_input("Enter a custom role:", "").strip() or "boss"

# Mode buttons
m1, m2 = st.columns(2)
with m1:
    if st.button("🎮 Game mode"):
        st.session_state.mode = "game"
        st.session_state.game_active = True
        st.session_state.game_over = False
        st.session_state.turns = 0
        st.session_state.transcript = []
        st.session_state.last_verdict = None
        st.session_state.convinced_win = False
        st.success("Game mode started. You have 3 attempts.")
with m2:
    if st.button("🗨️ Regular mode"):
        st.session_state.mode = "regular"
        st.session_state.game_active = False
        st.session_state.game_over = False
        st.session_state.convinced_win = False
        st.info("Regular mode: free practice.")

# Agent setup
def ensure_agent(role: str, difficulty: int, api_key: str):
    if not api_key:
        return
    changed_role = (st.session_state.get("challenger_role") != role)
    changed_diff = (st.session_state.get("challenger_difficulty") != difficulty)
    missing = st.session_state.get("challenger_agent") is None
    if changed_role or changed_diff or missing:
        llm_config = build_llm_config(api_key)
        st.session_state.challenger_agent = AssistantAgent(
            name="Challenger",
            system_message=make_challenger_system(role, difficulty),
            llm_config=llm_config,
        )
        st.session_state.challenger_role = role
        st.session_state.challenger_difficulty = difficulty
        st.session_state.transcript = []
        st.session_state.last_verdict = None
        st.session_state.convinced_win = False

ensure_agent(role, difficulty, api_key)

# Game HUD
in_game = (st.session_state.get("mode") == "game")
if in_game:
    attempts_left = max(0, st.session_state.max_turns - st.session_state.turns)
    cA, = st.columns(1)
    with cA: st.metric("Attempts left", f"{attempts_left}/{st.session_state.max_turns}")
    st.progress(min(1.0, st.session_state.turns / max(1, st.session_state.max_turns)))

# Chat input form (disabled after win, or when game over)
input_disabled = st.session_state.convinced_win or (in_game and st.session_state.get("game_over", False))
with st.form("chat_form", clear_on_submit=True):
    user_msg = st.text_area(
        "Your message",
        height=110,
        placeholder="State your ask / boundary (add specifics or a brief reason to win).",
        disabled=input_disabled,
        key="chat_input"
    )
    submitted = st.form_submit_button("Send", disabled=input_disabled)

if submitted and user_msg.strip():
    # 1) append user message first
    st.session_state.transcript.append(("User", user_msg.strip()))

    if not api_key:
        st.warning("Please add your API key first.")
    elif st.session_state.challenger_agent is None:
        st.warning("Set the role to create the Challenger.")
    else:
        # 2) Judge FIRST on the user's message (decide win before challenger replies)
        verdict = judge_turn(st.session_state.transcript, api_key)
        st.session_state.last_verdict = verdict

        # 3) If convinced -> challenger CONCEDES (no more pushback), end + block input
        if verdict.get("convinced", False):
            st.session_state.transcript.append(("Challenger", challenger_concede_message(st.session_state.challenger_role or role)))
            if in_game and st.session_state.get("game_active", False) and not st.session_state.get("game_over", False):
                st.session_state.game_over = True
            st.session_state.convinced_win = True  # block further input in any mode

        else:
            # 4) Otherwise, normal challenger pushback
            reply = challenger_reply(st.session_state.challenger_agent, st.session_state.transcript)
            st.session_state.transcript.append(("Challenger", reply))

            # 5) In game mode, consume a turn and possibly end after 3 non-winning tries
            if in_game and st.session_state.get("game_active", False) and not st.session_state.get("game_over", False):
                st.session_state.turns += 1
                if st.session_state.turns >= st.session_state.max_turns:
                    st.session_state.game_over = True

# Judge section (always visible)
st.subheader("Judge")
_verdict = st.session_state.get("last_verdict")
if _verdict:
    if _verdict.get("convinced", False):
        st.success(f"Convinced ✅ (confidence {_verdict.get('confidence',0):.2f}) — WIN!")
    else:
        st.info(f"Not convinced yet (confidence {_verdict.get('confidence',0):.2f}). Keep going.")
    if _verdict.get("why"):
        st.caption(f"Why: {_verdict['why']}")
    tips = _verdict.get("tips", [])
    if tips:
        st.markdown("**Try next:**")
        for t in tips:
            st.markdown(f"- {t}")
else:
    st.caption("No verdict yet — send a message to get a ruling.")

# Transcript display
st.subheader("Transcript")
for spk, msg in st.session_state.transcript:
    st.markdown(f"**{spk}:** {msg}")

# Evaluate + Reset
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
            render_critic(critic)
            with st.expander("Show raw JSON"):
                st.code(json.dumps(results, indent=2), language="json")
with c2:
    if st.button("Reset conversation"):
        st.session_state.transcript = []
        st.session_state.last_verdict = None
        st.session_state.turns = 0
        st.session_state.game_over = False
        st.session_state.convinced_win = False
