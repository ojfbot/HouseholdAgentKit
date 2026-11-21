# Batch 6: rows needed by org@2 re-sourcing (accessibility carve-out, privacy split, taco example, SNAP).
from registry import R

TERMS = "https://www.walmart.com/help/article/walmart-agentic-access-terms/d048fc229d7549738d7c05a4317e24d7"
R("ST-188", "https://benefitsusa.org/en/blog/does-walmart-accept-ebt", "2026-01-01", "Benefits USA (explainer)", "secondary", "press", "capability_claim", "snap_online",
  ["finance", "trust_safety"], ["shopper"], ["CAP-12", "CON-10"], "low",
  "Secondary explainer: Walmart accepts SNAP EBT online for pickup, delivery and shipping in all 50 states; only items marked SNAP EBT eligible and sold by Walmart.com qualify, not Marketplace items. Not re-verified against walmart.com.")
R("ST-189", TERMS, "2026-10-21", "Walmart, corporate", "Agentic Access Terms, definitions", "walmart_primary", "constraint", "accessibility_carveout",
  ["trust_safety", "product"], ["shopper"], ["CON-23"], "high",
  "The terms define an Agent broadly (AI assistants, browser automation, API-connected services) but exclude assistive technologies that let people with disabilities use the sites.")
R("ST-190", TERMS, "2026-10-21", "Walmart, corporate", "Agentic Access Terms", "walmart_primary", "constraint", "privacy_split",
  ["trust_safety", "partnerships"], ["agent_builder"], ["CON-24", "CON-01"], "high",
  "The agent's own privacy policy governs what it receives; Walmart handles what the agent provides under Walmart's Privacy Notice. Data is licensed, not sold, and may not be sublicensed, resold or redistributed; retention only as long as the permitted purpose needs.")
R("ST-191", "https://www.axios.com/2025/10/14/walmart-chatgpt-openai-shopping", "2025-10-14", "Walmart (via Axios)", "announcement coverage", "press", "desire", "taco_example",
  ["product", "marketing_crm"], ["shopper", "ai_platform"], ["CAP-32"], "medium",
  "Walmart's example prompts for shopping in ChatGPT included planning a weeknight taco dinner and reordering staples, with curated picks and one-step checkout: taco night is Walmart's own illustration.",
  "plan a weeknight taco dinner")
R("ST-192", "https://www.constellationr.com/insights/news/walmart-retailers-tout-ai-digital-transformation-efforts-argue-theyre-more-their", "2026-08-20", "John David Rainey", "EVP & CFO (Q2 FY27 call, via Constellation)", "analyst", "goal", "density",
  ["supply_chain", "finance"], ["shopper"], ["CAP-35", "CAP-10"], "medium",
  "Rainey tied delivery speed to network economics: improving density and utilization lets speed and profitability reinforce one another. Relevant to shifting agent orders off peaks.",
  "speed and profitability reinforce one another")
