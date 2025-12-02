# streamlit_ic_shadow_agents.py

import os
import json
import re
from datetime import datetime

import streamlit as st
import aisuite


# ========= CONFIG / CLIENT =========

MODEL_NAME = "openai:o4-mini"


@st.cache_resource
def get_client():
    """
    Lazily create the aisuite client AFTER the API key is set.
    Cached so we don't recreate it on every rerun.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set.")
    return aisuite.Client()


# ========= LOGGING HELPERS (STREAMLIT VERSION) =========

def log_agent_title_html(title, icon="🧠"):
    st.markdown(
        f"""
        <div style="padding:1em;margin:1em 0;background-color:#f0f4f8;border-left:6px solid #1976D2;">
          <h2 style="margin:0;color:#0D47A1;">{icon} {title}</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )


def log_final_summary_html():
    st.markdown(
        """
        <div style="border-left:4px solid #2E7D32;padding:1em;margin:1em 0;
                    background-color:#e8f5e9;color:#1B5E20;">
          <strong>Shadow IC Output Generated</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ========= CORE SHADOW IC LOGIC (FROM PROGRAM 1) =========

def run_shadow_ic_debate(
    memo_text: str,
    deal_name: str = "Acme Industries",
    rounds: int = 2,
    crossfire: bool = True,
) -> str:
    """
    Simulate a multi-agent Shadow IC debate with full professional role names.

    If crossfire=True, agents are encouraged to respond directly to prior comments,
    not just the memo.
    """

    log_agent_title_html("Shadow IC Debate", "🧮")

    roles = [
        ("Portfolio Manager",
         "Portfolio Manager focusing on risk/return, relative value, portfolio overlap, exposure sizing."),
        ("Credit Risk Officer",
         "Credit Risk Officer focusing on leverage, liquidity, coverage, asset quality and LGD dynamics."),
        ("Documentation Counsel",
         "Documentation Counsel focusing on covenants, baskets, leakage, remedies, and enforceability."),
        ("Macro & Sector Analyst",
         "Macro & Sector Analyst focusing on cycles, rate environment, commodity pricing, sector volatility and pass-through."),
    ]

    transcript = []
    memo_snippet = memo_text[:12000]   # keep prompt manageable

    client = get_client()

    for r in range(rounds):
        for role_name, description in roles:
            # Only feed a window of the last few comments for context
            previous_discussion = "\n".join(transcript[-16:]) if transcript else "(none yet)"

            crossfire_instructions = (
                """
- Explicitly reference one or two prior comments if relevant (agree, disagree, or extend them).
- If you disagree, explain why briefly but clearly.
- You can call out other roles by name, e.g. "As the Credit Risk Officer noted..." or "I disagree with the Portfolio Manager on sizing because...".
"""
                if crossfire
                else """
- You may mention that others have raised points, but you do NOT need to directly react to them.
"""
            )

            prompt = f"""
You are acting as **{role_name}** in a private credit Shadow Investment Committee for the deal "{deal_name}".

Your perspective:
{description}

You are reviewing the following Investment Committee memo:

MEMO_START
{memo_snippet}
MEMO_END

Shadow IC discussion so far:
{previous_discussion}

Your task:
- Provide one concise, pointed comment (3–6 sentences max).
- Focus only on what is contained in the memo (no external data).
- Critique assumptions, highlight risks, challenge structure, or support the deal based on your role.
- Refer to memo sections when appropriate.
{crossfire_instructions}
- Start your comment EXACTLY with "[{role_name}]:".
- Output ONLY your comment.
"""

            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You simulate realistic, technically detailed private credit IC debates among professionals."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            output = response.choices[0].message.content.strip()

            # Ensure the role tag is present
            if not output.startswith(f"[{role_name}]"):
                output = f"[{role_name}]: " + output

            # Bold the role tag for nicer Markdown
            formatted = output.replace(f"[{role_name}]:", f"**[{role_name}]:**", 1)
            transcript.append(formatted)

    # Add readable spacing between turns
    full_discussion = "\n\n".join(transcript)
    return full_discussion


def build_shadow_ic_checklist(
    memo_text: str,
    discussion: str,
    deal_name: str = "Acme Industries"
) -> str:
    """
    Build a structured checklist of IC-style questions and gaps
    based on the memo and the shadow IC discussion.
    """

    log_agent_title_html("Shadow IC Challenge Checklist", "📋")

    memo_snippet = memo_text[:12000]
    discussion_snippet = discussion[-12000:]

    prompt = f"""
You are acting as the IC Chair of a private credit Investment Committee for the deal "{deal_name}".

You have:
1) The Investment Committee memo (for the deal team presentation).
2) A transcript of a Shadow IC discussion between:
   - Portfolio Manager (PM)
   - Credit Risk Officer (CRO)
   - Documentation Counsel (DOC)
   - Macro / Sector Specialist (MACRO)

Your job is to convert this into a practical, structured checklist
the deal team must address BEFORE going to a real IC.

MEMO_START
{memo_snippet}
MEMO_END

DISCUSSION_START
{discussion_snippet}
DISCUSSION_END

Output in Markdown with this structure:

Shadow IC Challenge Checklist for the Deal Team – {deal_name}

A. Business & Sponsor
- [question 1]
- [question 2]
...

B. Financials, Leverage & Liquidity
- ...

C. Structure, Covenants & Documentation
- ...

D. Sector, Macro & Scenario Analysis
- ...

E. Process, Monitoring & IC Decision
- ...

Guidelines:
- 5–10 questions under each heading.
- Questions should be specific, sharp, and grounded in the memo content and the Shadow IC concerns.
- Focus especially on:
  • Where the memo is vague or optimistic.
  • Where downside is not fully explored.
  • Where documentation / covenants might have gaps or weak teeth.
  • What must be clarified before assigning INVEST / DECLINE / WATCHLIST.
- Do NOT introduce external facts; you can only critique or question what is in the memo.
"""

    client = get_client()
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an IC Chair who produces structured, critical checklists for private credit deal teams."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )

    checklist = response.choices[0].message.content.strip()
    return checklist


def run_shadow_ic_from_text(
    memo_text: str,
    deal_name: str = "Acme Industries",
    rounds: int = 2,
    crossfire: bool = True,
) -> tuple[str, str, str]:
    """
    End-to-end Shadow IC pipeline starting from memo text.

    Returns:
      discussion, checklist, full_output_markdown
    """

    log_agent_title_html(f"Running Shadow IC on: {deal_name}", "📊")

    discussion = run_shadow_ic_debate(
        memo_text=memo_text,
        deal_name=deal_name,
        rounds=rounds,
        crossfire=crossfire,
    )

    checklist = build_shadow_ic_checklist(
        memo_text=memo_text,
        discussion=discussion,
        deal_name=deal_name,
    )

    full_output = f"""# Shadow IC Review – {deal_name}

## Part 1 – Shadow IC Discussion

{discussion}

## Part 2 – Shadow IC Challenge Checklist for the Deal Team

{checklist}
"""

    log_final_summary_html()
    return discussion, checklist, full_output


# ========= STREAMLIT APP (BORROWING PROGRAM 2 PATTERNS) =========

st.set_page_config(page_title="IC Shadow Agents", page_icon="📊", layout="wide")
st.title("IC Shadow Agents – Shadow Investment Committee Simulator")

st.info(
    "Upload or paste an IC memo, set the deal name and number of rounds, "
    "and generate a multi-role Shadow IC debate plus a structured challenge checklist."
)

# Persist state (optional, very lightweight here)
if "discussion" not in st.session_state:
    st.session_state.discussion = None
if "checklist" not in st.session_state:
    st.session_state.checklist = None
if "full_output" not in st.session_state:
    st.session_state.full_output = None

# API key similar to Program 2
api_key = st.text_input(
    "OpenAI API Key",
    type="password",
    value=os.getenv("OPENAI_API_KEY", ""),
    help="Your OpenAI-compatible key used by aisuite.",
)
if api_key:
    os.environ["OPENAI_API_KEY"] = api_key

# Main controls
col_left, col_right = st.columns([2, 1])

with col_right:
    deal_name = st.text_input("Deal Name (alias)", value="Acme Industries")
    rounds = st.slider("Number of Debate Rounds", min_value=1, max_value=4, value=2, step=1)
    crossfire = st.checkbox(
        "Enable crossfire (agents respond to each other)",
        value=True,
        help="If enabled, roles explicitly respond to prior comments.",
    )

    memo_mode = st.radio(
        "How do you want to provide the IC memo?",
        ["Upload .md/.txt file", "Paste memo text"],
        index=0,
    )

with col_left:
    uploaded_file = None
    memo_text_input = ""

    if memo_mode == "Upload .md/.txt file":
        uploaded_file = st.file_uploader(
            "Upload IC memo file",
            type=["md", "txt"],
            help="Markdown or plain-text IC memo.",
        )
    else:
        memo_text_input = st.text_area(
            "Paste IC memo text",
            height=300,
            placeholder="Paste the full Investment Committee memo here...",
        )

run_button = st.button("Run Shadow IC")

if run_button:
    # Basic validation
    if not api_key:
        st.warning("Please enter your OpenAI API Key before running.")
    else:
        if memo_mode == "Upload .md/.txt file":
            if not uploaded_file:
                st.warning("Please upload a memo file or switch to paste mode.")
            else:
                try:
                    memo_text = uploaded_file.read().decode("utf-8")
                except Exception as e:
                    st.error(f"Could not read uploaded file: {e}")
                    memo_text = ""
        else:
            memo_text = memo_text_input

        if memo_text and memo_text.strip():
            try:
                with st.spinner("Running Shadow IC pipeline..."):
                    discussion, checklist, full_output = run_shadow_ic_from_text(
                        memo_text=memo_text,
                        deal_name=deal_name or "Acme Industries",
                        rounds=rounds,
                        crossfire=crossfire,
                    )

                st.session_state.discussion = discussion
                st.session_state.checklist = checklist
                st.session_state.full_output = full_output

                st.success("Shadow IC run completed.")
            except Exception as e:
                st.error(f"Error while running Shadow IC: {e}")
        else:
            st.warning("Memo is empty. Please upload a file or paste memo text.")

# Show results if present
if st.session_state.discussion or st.session_state.checklist:
    st.subheader("Part 1 – Shadow IC Discussion")
    if st.session_state.discussion:
        st.markdown(st.session_state.discussion)

    st.subheader("Part 2 – Shadow IC Challenge Checklist for the Deal Team")
    if st.session_state.checklist:
        st.markdown(st.session_state.checklist)

    # Download button for Markdown
    if st.session_state.full_output:
        default_filename = f"{(deal_name or 'Deal').replace(' ', '_')}_ShadowIC_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.md"
        st.download_button(
            "Download full Shadow IC output (Markdown)",
            data=st.session_state.full_output,
            file_name=default_filename,
            mime="text/markdown",
        )
