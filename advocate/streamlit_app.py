
import os, json
import streamlit as st
from autogen import AssistantAgent

# For streamlit--------------------------------------------------
# ---------- PRETTY RENDER HELPERS ----------
# import math
# import streamlit as st

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

    # Scores as metrics + progress bars
    cols = st.columns(4)
    order = ["Clarity", "Assertiveness", "Evidence", "Boundaries"]
    for i, k in enumerate(order):
        with cols[i]:
            _score_bar(k, scores.get(k, 0))

    # Tips
    if tips:
        st.markdown("**Tips (try these next time):**")
        for t in tips:
            st.markdown(f"- {t}")

    # Stronger phrasing examples
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

#end of streamlit addition----------------------------------------------


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

def judge_turn(transcript, api_key):
    llm_config = build_llm_config(api_key)
    judge = AssistantAgent(name="Judge", system_message=JUDGE_SYSTEM, llm_config=llm_config)

    # Last exchange focus: take last 4 lines for context
    ctx = "\n".join([f"{spk}: {msg}" for spk, msg in transcript[-4:]])
    prompt = (
        "Decide if the Challenger would concede now based on this recent exchange.\n"
        f"{ctx}\n"
        "Return JSON only."
    )
    raw = judge.generate_reply(messages=[{"role":"user","content":prompt}])
    try:
        data = json.loads(raw.strip())
    except:
        import re
        m = re.search(r"\{.*\}", raw, flags=re.S)
        data = json.loads(m.group(0)) if m else {"convinced": False, "confidence": 0.0, "why": "Parse error", "tips": []}
    # Safety defaults
    data.setdefault("convinced", False)
    data.setdefault("confidence", 0.0)
    data.setdefault("why", "")
    data.setdefault("tips", [])
    # --- make it easier: light heuristic on last user message ---
    last_user = ""
    for spk, m in reversed(transcript):
        if spk.lower() == "user":
            last_user = m.lower()
            break
    
    keywords_ask = ["i want", "i need", "i would like", "i’m asking", "i am asking"]
    keywords_boundary = ["i won’t", "not acceptable", "that doesn’t work", "i can’t agree"]
    # crude evidence: numbers, $, %, dates-ish
    has_evidence = any(ch.isdigit() for ch in last_user) or "$" in last_user or "%" in last_user
    
    clear_ask = any(k in last_user for k in keywords_ask)
    clear_bound = any(k in last_user for k in keywords_boundary)
    
    # lower the bar: if there is any clear ask/boundary/evidence, boost outcome
    conf = float(data.get("confidence", 0) or 0)
    if (clear_ask or clear_bound or has_evidence) and conf >= 0.30:
        data["convinced"] = True
        data["confidence"] = max(conf, 0.55)

    return data


def make_challenger_system(role: str, level: int) -> str:
    tones = {
        1: "polite but firm",
        3: "curt, slightly dismissive",
        5: "sharply dismissive (still non-abusive)"
    }
    style = tones.get(level, "curt")
    return (
        f"You are roleplaying as the USER's {role}. "
        f"Your pushback intensity is {level}/5 and your tone is {style}. "
        "Be realistic, never abusive, but you may be curt, dismissive, or subtly demeaning. "
        "Stay in character. Keep replies under 80 words."
    )


def challenger_reply(challenger: AssistantAgent, transcript):
    """Generate a Challenger reply based on transcript + role + difficulty."""
    ctx = "\n".join([f"{spk}: {msg}" for spk, msg in transcript[-6:]])
    latest_user = next((m for spk, m in reversed(transcript) if spk.lower() == "user"), "")

    prompt = (
        f"Context so far:\n{ctx}\n\n"
        f"User's latest message:\n{latest_user}\n\n"
        "Reply IN CHARACTER as the assigned role "
        "with the specified pushback intensity. "
        "Keep your message under 80 words."
    )

    return challenger.generate_reply(messages=[
        {"role": "system", "content": challenger.system_message},
        {"role": "user", "content": prompt},
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
difficulty = st.slider("Difficulty (pushback level)", 1, 5, 3)

if role == "other":
    role = st.text_input("Enter a custom role:", "").strip() or "peer"
# Mode toggle buttons
m1, m2 = st.columns(2)
with m1:
    if st.button("🎮 Game mode"):
        st.session_state.mode = "game"
        st.session_state.game_active = True
        st.session_state.game_over = False
        st.session_state.turns = 0
        st.session_state.score = 0
        st.session_state.streak = 0
        st.session_state.transcript = []
        st.success("Game mode: started a new game (3 turns). Convince the Challenger!")

with m2:
    if st.button("🗨️ Regular mode"):
        st.session_state.mode = "regular"
        st.session_state.game_active = False
        st.session_state.game_over = False
        st.info("Regular mode: free practice. No turns, no scoring.")


if "transcript" not in st.session_state: st.session_state.transcript = []
if "challenger_role" not in st.session_state: st.session_state.challenger_role = None
if "challenger_agent" not in st.session_state: st.session_state.challenger_agent = None

# --- Game state for gamified version ---
if "game_active" not in st.session_state: st.session_state.game_active = False
if "game_over" not in st.session_state: st.session_state.game_over = False
if "turns" not in st.session_state: st.session_state.turns = 0
if "max_turns" not in st.session_state: st.session_state.max_turns = 3   # tweakable
if "score" not in st.session_state: st.session_state.score = 0
if "streak" not in st.session_state: st.session_state.streak = 0

if "mode" not in st.session_state: st.session_state.mode = "regular"

# --- Game Controls ---
# --- Game Controls (only in Game mode) ---
if st.session_state.mode == "game":
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🎮 Start Game"):
            st.session_state.game_active = True
            st.session_state.game_over = False
            st.session_state.transcript = []
            st.session_state.turns = 0
            st.session_state.score = 0
            st.session_state.streak = 0
            st.success("Game started! Convince the Challenger before turns run out.")

    with c2:
        if st.button("🔄 Reset Game"):
            st.session_state.game_active = False
            st.session_state.game_over = False
            st.session_state.transcript = []
            st.session_state.turns = 0
            st.session_state.score = 0
            st.session_state.streak = 0
            st.info("Conversation reset.")





def ensure_agent(role: str, difficulty: int, api_key: str):
    """Create/recreate the Challenger agent when role or difficulty changes."""
    if not api_key:
        return

    # Init state holders if missing
    if "challenger_agent" not in st.session_state:
        st.session_state.challenger_agent = None
    if "challenger_role" not in st.session_state:
        st.session_state.challenger_role = None
    if "challenger_difficulty" not in st.session_state:
        st.session_state.challenger_difficulty = None
    if "transcript" not in st.session_state:
        st.session_state.transcript = []

    # Rebuild when role or difficulty changed, or agent missing
    changed_role = (st.session_state.challenger_role != role)
    changed_diff = (st.session_state.challenger_difficulty != difficulty)
    missing = st.session_state.challenger_agent is None

    if changed_role or changed_diff or missing:
        llm_config = build_llm_config(api_key)
        st.session_state.challenger_agent = AssistantAgent(
            name="Challenger",
            system_message=make_challenger_system(role, difficulty),
            llm_config=llm_config,
        )
        st.session_state.challenger_role = role
        st.session_state.challenger_difficulty = difficulty
        st.session_state.transcript = []  # reset when persona intensity changes


ensure_agent(role, difficulty, api_key)

# Scenario presets
st.subheader("Scenario presets")

presets = {
    "Teenager party": {
        "role": "teenager",
        "first": "I don’t want you going to the party where there’s drinking."
    },
    "Customer refund": {
        "role": "customer service rep",
        "first": "I’d like a refund for the subscription that auto-renewed."
    },
    "Peer taking credit": {
        "role": "peer",
        "first": "Please stop presenting my work without attribution. I need co-credit."
    },
    "Boss scope creep": {
        "role": "boss",
        "first": "I can’t add this project without moving deadlines or dropping X. Let’s prioritize."
    },
}

cols = st.columns(len(presets))
for i, (k, v) in enumerate(presets.items()):
    if cols[i].button(k):
        # Rebuild agent with preset role + current difficulty
        ensure_agent(v["role"], difficulty, api_key)
        st.session_state.transcript = [("User", v["first"])]
        if st.session_state.challenger_agent:
            reply = challenger_reply(st.session_state.challenger_agent, st.session_state.transcript)
            st.session_state.transcript.append(("Challenger", reply))


st.write("Type a message, press Send. Click Evaluate anytime for feedback.")

if st.session_state.mode == "game":
    cX, cY = st.columns(2)
    with cX: st.metric("Score", st.session_state.score)
    with cY: st.metric("Win streak", st.session_state.streak)
    st.caption(f"Turns: {st.session_state.turns}/{st.session_state.max_turns}")
    st.progress(min(1.0, st.session_state.turns / max(1, st.session_state.max_turns)))




    
with st.form("chat"):
    # Disable only if we're in Game mode AND the game is over
    in_game = (st.session_state.get("mode", "regular") == "game")
    disabled = in_game and st.session_state.get("game_over", False)

    user_msg = st.text_area(
        "Your message",
        height=110,
        placeholder="State your ask / boundary...",
        disabled=disabled,
        key="chat_input"  # lets us clear after send
    )
    submitted = st.form_submit_button("Send", disabled=disabled)

    if submitted and user_msg.strip():
        st.session_state.transcript.append(("User", user_msg.strip()))
        if not api_key:
            st.warning("Please add your API key first.")
        elif st.session_state.challenger_agent is None:
            st.warning("Set the role to create the Challenger.")
        else:
            # Challenger responds
            reply = challenger_reply(st.session_state.challenger_agent, st.session_state.transcript)
            st.session_state.transcript.append(("Challenger", reply))

            # Judge only in Game mode, while active and not over
            if (
                st.session_state.mode == "game"
                and st.session_state.get("game_active", False)
                and not st.session_state.get("game_over", False)
            ):
                st.session_state.turns += 1
                verdict = judge_turn(st.session_state.transcript, api_key)

                # Light scoring: +10 on win, +2 per turn if confidence ≥ 0.5
                st.session_state.score += 2 if verdict.get("confidence", 0) >= 0.5 else 0

                if verdict.get("convinced", False):
                    st.success(f"You win! Judge: convinced (confidence {verdict.get('confidence',0):.2f}).")
                    if verdict.get("why"):
                        st.caption(f"Why: {verdict['why']}")
                    st.session_state.score += 10
                    st.session_state.streak = st.session_state.get("streak", 0) + 1
                    st.session_state.game_over = True
                    st.balloons()
                else:
                    st.info("Judge: not convinced yet.")
                    if verdict.get("why"):
                        st.caption(f"Why: {verdict['why']}")
                    tips = verdict.get("tips", [])
                    if tips:
                        st.write("Try next:")
                        for t in tips:
                            st.markdown(f"- {t}")
                    if st.session_state.turns >= st.session_state.max_turns:
                        st.error("Out of turns. Game over.")
                        st.session_state.streak = 0
                        st.session_state.game_over = True

        # ✅ Clear the input box after sending
        st.session_state.chat_input = ""



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
            coach = results.get("coach", {})
            critic = results.get("critic", {})
            
            # Pretty UI
            render_coach(coach)
            st.markdown("---")
            render_critic(critic)
            
            # Optional: raw JSON in an expander
            with st.expander("Show raw JSON"):
                st.code(json.dumps(results, indent=2), language="json")

with c2:
    if st.button("Reset conversation"):
        st.session_state.transcript = []
