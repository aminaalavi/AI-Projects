# 🧠 Hybrid Data Migration with LangGraph Agents

This project demonstrates an **intelligent, end-to-end data migration pipeline** that combines:
- **Agents (LLMs via LangGraph & LangChain)** for reasoning, mapping, and narration  
- **Python** for deterministic execution, validation, and reporting  

It automates schema reading, mapping generation, SQL creation, execution, and validation — all orchestrated through a hybrid LangGraph workflow.

---

## 🤖 Agents Used

| Agent | Role | Description |
|--------|------|-------------|
| 🧱 **Schema Agent** | `node_schema` | Reads both source and target database schemas and captures table structures. |
| 🗺️ **Mapping Agent** | `node_mapplan` | Uses LLM to propose JSON-based column mappings between source and target tables; falls back to deterministic heuristics when no API key is available. |
| 🧮 **Planner Agent** | `node_plan` | Converts mappings into a deterministic execution plan (CREATE, TRANSFER, VALIDATE, CHECKSUM). |
| 🧩 **SQL Generator Agent** | `node_sqlgen` | Produces executable SQL scripts from the plan, including derived fields and type inference. |
| ⚙️ **Executor Agent** | `node_execute` | Executes SQL scripts, logs actions, and records any errors during migration. |
| ✅ **Validation Agent** | `node_validate` | Verifies migration accuracy using row counts and checksum comparisons. |
| 🔁 **Remediation Agent** | `node_remediate` | If validation or execution fails, uses the LLM to patch the mapping and retry once. |
| 🗣️ **Narration Agent** | `node_narrate` | Summarizes the entire migration in plain English, including results, errors, and overall status. |

Each agent is represented as a **node** in the LangGraph workflow, passing structured state (`MigState`) between stages.

---

## 🧩 Architecture Overview

**Workflow Stages:**

| Stage | Description |
|-------|--------------|
| `schema` | Read both DB schemas |
| `mapplan` | LLM proposes mapping JSON (fallback to heuristics) |
| `plan` | Generate deterministic execution plan |
| `sqlgen` | Generate SQL scripts |
| `exec` | Execute SQL (with error capture) |
| `validate` | Compare counts and checksums |
| `remediate` | Retry failed migrations using LLM |
| `narrate` | Generate a natural-language summary |

---


