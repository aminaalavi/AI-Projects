#AlphaLens Earnings Pack

Automated multi-agent system for generating portfolio-ready earnings analysis. AlphaLens transforms scattered financial data, SEC filings, consensus estimates, and transcripts into a polished, markdown-based Earnings Pack ready for PM briefings or investment committee decks.

🎯 ##What It Does
###AlphaLens automates a complete sell-side research workflow:
1️⃣ Research Agent	Combines SEC / IR filings and Street consensus	“Pre-Call Brief”
2️⃣ Analyst Agent	Builds post-call deltas, scenarios, and risks	“Post-Call Analysis”
3️⃣ Chart Maker Agent	Pulls last 90-day price history via Yahoo Finance	Price Trend Chart
4️⃣ Packaging Agent	Merges everything into a professional markdown report	📈 Earnings Pack (Markdown + inline chart)

The result is a portfolio-manager-grade summary, not a chatbot dump. You get structured sections: Guidance vs Consensus, Scenario Analysis, Top 5 Key Risks, and a clean inline chart.

💼 ##Why It Matters
Investment teams spend hours manually building pre- and post-call decks. AlphaLens replaces that grunt work with a transparent, auditable pipeline:
Pulls objective disclosures (10-Qs, transcripts)
Cross-checks with Street expectations
Auto-formats key numbers, risks, and guidance deltas
Outputs in Markdown for easy sharing to Notion, Slack, or IR notes

🧩 ##Agent Architecture
###Each module can be run independently or chained via the orchestrator:
research_agent()  →  analyst_agent()  →  chart_maker_agent()  →  earnings_packaging_agent()

##Agents Overview
Research Agent: Summarizes management tone + Street consensus	
Analyst Agent:	Compares KPIs, builds Bull/Base/Bear scenarios	
Chart Maker Agent:	Generates 90-day price trend chart 
Earnings packaging Agent:	Combines and beautifies all content	
