# Precedent Stress-Test Engine

A **multi-agent legal reasoning system** that tests whether prior matters still provide a reliable playbook for a current matter.

Instead of just retrieving similar matters, it uses **agents with competing roles** to challenge precedent, surface blind spots, and produce a clear recommendation.

---

## What It Does

Given a current matter, the system:

* retrieves similar prior matters
* pulls external context
* runs a **multi-agent debate**
* outputs a **final precedent stress-test memo**

---

## Agents

* **Precedent Advocate** – argues why a prior matter is the right playbook
* **Skeptic / Challenger** – pushes on weak analogies and false matches
* **External Context Agent** – tests precedent against current public developments
* **Blind Spot Detector** – identifies what the team is still missing
* **Synthesizer** – makes the final call on what still holds and what breaks

All agents see the same matter, the same retrieved precedents, and the same external context — then explicitly disagree.

---

## Why Agents?

Legal teams do not just need retrieval.

They need **judgment**.

The real risk is not missing precedent.  
It is trusting the **wrong precedent**.

This system uses agent disagreement to test whether past logic still applies.

---

## Outputs

* **Retrieved Internal Precedents**
* **External Context**
* **Multi-Agent Debate Transcript**
* **Final Precedent Stress-Test Memo**

---

## Use Case

Built for **law firms, knowledge teams, and legal data/analytics teams** exploring how multi-agent systems can improve precedent reuse and legal reasoning.

---

## Tech

* Python
* Streamlit
* aisuite
* Tavily
* scikit-learn

---

## Disclaimer

Educational and experimental use only.  
Not legal advice.

---

## Tags

#AI #Agents #MultiAgent #LegalAI #LawFirmInnovation #GenAI #OpenSource
