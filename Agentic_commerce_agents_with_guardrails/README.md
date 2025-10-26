## 🧩 Overview — Agentic Commerce Multi-Agent System

This notebook demonstrates an **agentic commerce pipeline**, a simulated multi-agent system that automates product discovery, pricing, content generation, supervision, and transaction validation with trust at its core.  

It showcases how **AI agents collaborate** to plan, optimize, and execute a commerce flow end-to-end while using **guardrails** to ensure safety, transparency, and trust.  

When complete, the system compiles a detailed JSON report capturing the essential data of this new *agentic commerce flow* that can then be passes on the payment transaction system.
- 🧩 **Agent Names** – which AI module handled each decision stage  
- 💭 **Intent** – the user’s shopping request in structured form  
- 💰 **Budget** – the detected spending limit and the system’s cost estimates  
- 🛡️ **Guardrail Status** – pass or fail, depending on ethical and budget adherence  


The agents involved include:
- **Intent Planner Agent** – understands user goals and budgets  
- **Product Discovery Agent** – finds relevant products using Tavily search  
- **Price Optimizer Agent** – estimates costs and ensures they fit within budget  
- **Commerce Copywriter Agent** – creates persuasive, ethical ad copy  
- **Supervisor Agent** – validates quality, compliance, and safety  
- **Transaction Agent** – simulates payment handling  
- **Checkout Simulator** – mimics a checkout and shows if the process succeeds  
- **Trust Guardrails Agent** – checks ethical and budgetary consistency  

👉 The saved example run shows a case where **the guardrail fails**, meaning the transaction is **blocked before payment**, demonstrating how the system prevents untrustworthy or unsafe operations.  
Some modules (like web search and transactions) are **simulated** for demonstration purposes.


