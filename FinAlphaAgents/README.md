\#AI Project: Debating Alpha Agents — Investment Portfolio Construction (AG2)



Building AI-powered agents that debate like a team of analysts—all in Google Colab.



I used AG2 (formerly AutoGen) to build specialized agents that collaborate and then debate before producing a BUY/SELL/HOLD decision. Tools fetch facts first; the debate runs on those facts for stability and reproducibility.



Agents in Action

🔹 Valuation Agent — annualized return \& volatility from historical prices

🔹 Sentiment Agent — tone \& risks from news + SEC filings

🔹 Fundamental Agent — targeted 10-K/10-Q snippets via a tiny RAG

🔹 Coordinator — synthesizes a final decision as clean JSON



What’s special

• Facts are gathered outside the debate → agents argue from the same ground truth

• Tools are paused during the debate → fewer hallucinated calls

• Outputs are parseable JSON → easy to plug into downstream notebooks

• Fully reproducible in Colab—add your API key and run



Inspiration \& Paper

Inspired by and builds on: AlphaAgents: Large Language Model based Multi-Agents for Equity Portfolio Constructions

arXiv: https://arxiv.org/abs/2508.11152



Citation (arXiv)

Zhao, T., Lyu, J., Jones, S., Garber, H., Pasquali, S., \& Mehta, D. (2025). AlphaAgents: Large Language Model based Multi-Agents for Equity Portfolio Constructions. arXiv:2508.11152. https://doi.org/10.48550/arXiv.2508.11152



Educational use only, not financial advice.

Have ideas for other finance or research workflows with multi-agent debates? Let’s connect.



\#AI #AG2 #AutoGen #MultiAgent #FinanceAI #GPT4o #Colab #InvestmentResearch #OpenSource #arXiv

