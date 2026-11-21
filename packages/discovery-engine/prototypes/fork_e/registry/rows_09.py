# Batch 9: deep read of the Q3 FY27 call (Nov 19 2026), Walmart's release and the Q&A. Fork E, Nov 20 2026.
# ST-203/204/206/207 cite Walmart's own transcript, read in full (21 pages); ST-201 keeps the Investing.com transcript for its quote.
from registry import R

Q3 = "https://stock.walmart.com/_assets/_6eff40d47b6de9e4a6d86158aa985c07/walmart/db/938/10001/transcript_management_call/Earnings_Transcript_%28FY27_Q3%29.pdf"
Q3_INV = "https://www.investing.com/news/transcripts/earnings-call-transcript-walmart-beats-q3-2026-estimates-but-shares-fall-premarket-93CH-5039191"
REL = "https://www.sec.gov/Archives/edgar/data/0000104169/000010416926000168/earningsreleasefy27q3.htm"
D = "2026-11-20"

R("ST-201", Q3_INV, "2026-11-19", "John Furner", "President & CEO (Q3 FY27 call, via Investing.com transcript)", "press",
  "constraint", "trust_through_agents",
  ["trust_safety", "product", "supply_chain"], ["shopper", "agent_builder"], ["CON-03", "CON-19", "CAP-10"], "high",
  "Furner said Walmart's business is built on trust: whether customers shop directly with Walmart or through an agent, they should be able to count on accurate pricing, reliable availability and clear delivery options. Same wording in Walmart's own transcript and two other third-party transcripts.",
  "count on accurate pricing, reliable availability, and clear delivery options", as_of=D)
R("ST-202", Q3, "2026-11-19", "John Furner", "President & CEO (Q3 FY27 call, Walmart transcript)", "walmart_primary",
  "goal", "agentic_pillar",
  ["product", "partnerships", "supply_chain"], ["shopper", "agent_builder"], ["CAP-01", "CAP-07", "CAP-35"], "high",
  "Furner listed agentic experiences with stores, clubs and e-commerce as the strengths behind Walmart's value proposition, said the next steps in agentic commerce build on the omnichannel foundation, and said Walmart is creating an environment where agents can help a customer discover new items and decide what to buy. ChatGPT, Gemini, OpenAI, Google and Meta were not named anywhere on the call.",
  as_of=D)
R("ST-203", Q3, "2026-11-19", "Seth Dallaire", "EVP & Chief Growth Officer (Q3 FY27 Q&A, answering Scot Ciccarelli, Truist; Walmart transcript)", "walmart_primary",
  "risk", "ads_in_agents",
  ["connect_ads", "finance"], ["supplier_brand", "agent_builder"], ["CAP-34"], "high",
  "Ciccarelli cited concerns in the investment community about the value of advertising in an agentic-dominated world, with one of Walmart's largest competitors barring third-party agents. Dallaire said Walmart engages with agentic commerce to learn, wants to be where customers are if they shop through agents, is still learning how conversational queries and prompts differ, and that the desire to discover new products and brands has not changed; brand advertising is the important part. He did not name the competitor or address sponsored items, labeling or measurement. It was the only analyst question about agents and ads.",
  as_of=D)
R("ST-204", Q3, "2026-11-19", "Seth Dallaire", "EVP & Chief Growth Officer (Q3 FY27 Q&A, answering Peter Benedict, Baird; Walmart transcript)", "walmart_primary",
  "capability_claim", "agentic_ad_tools",
  ["connect_ads"], ["supplier_brand", "small_business"], ["CAP-34"], "medium",
  "Dallaire described two agentic uses on the ad side: search and discovery of content for VIZIO TV owners, and agentic capability inside Vibe that powers ad buying for smaller advertisers; VIZIO sets now support sales attribution for advertisers.",
  as_of=D)
R("ST-205", REL, "2026-11-19", "Walmart, corporate / John Furner", "Q3 FY27 earnings release (8-K exhibit)", "walmart_primary",
  "risk", "agentic_disclosure",
  ["finance", "product"], ["shopper"], ["CAP-01"], "high",
  "The release's forward-looking statements list consumer acceptance of Walmart's stores, clubs, e-commerce, digital and agentic platforms, and pressures from AI development and deployment, among factors that could change results; Furner's release quote names agentic shopping, with membership, as a source of growth.",
  "From membership and agentic shopping to new ways of using our stores", as_of=D)
R("ST-206", Q3, "2026-11-19", "John Furner / John David Rainey", "CEO / CFO (Q3 FY27 Q&A; Walmart transcript)", "walmart_primary",
  "metric", "consumer_health",
  ["finance", "merchandising", "marketing_crm"], ["shopper"], ["CAP-04"], "high",
  "Furner called the customer stable and resilient; about 7,700 rollbacks were running against a typical 5,000 to 5,500; food inflation is 1% to 2%; management priced a Thanksgiving meal at just over $3.50 a person. Rainey said elevated diesel and transport added over $2B of incremental cost this year.",
  as_of=D)
R("ST-207", Q3, "2026-11-19", "John Furner / Seth Dallaire / David Guggina", "CEO / Chief Growth Officer / President, Walmart U.S. (Q3 FY27 Q&A; Walmart transcript)", "walmart_primary",
  "metric", "membership_bundle",
  ["marketing_crm", "finance", "b2b"], ["shopper", "small_business"], [], "high",
  "The Walmart+ and Sam's Club Plus bundle launched Oct 20 at $120 a year ($10 a month) and added a couple million new Sam's Club members; early bundle customers spend more than 80% more online; members spend about four times what non-members do; global membership fee revenue grew 17%.",
  as_of=D)
