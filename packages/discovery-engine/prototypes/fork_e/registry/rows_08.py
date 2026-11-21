# Batch 8: daily sweep, Nov 20 2026 (Fork E); ST-196/197/199 re-sourced to Walmart's own transcript the same day. Q3 FY27 call (Sparky, profiles still "announced", ads, e-commerce, speed); UCP November updates.
from registry import R

Q3 = "https://stock.walmart.com/_assets/_6eff40d47b6de9e4a6d86158aa985c07/walmart/db/938/10001/transcript_management_call/Earnings_Transcript_%28FY27_Q3%29.pdf"
PPC_Q3 = "https://ppc.land/walmarts-global-ad-growth-drops-to-25-as-flipkarts-sale-slips-a-quarter/"
UCP_UPD = "https://developers.google.com/merchant/ucp/latest-updates"

R("ST-196", Q3, "2026-11-19", "John Furner", "President & CEO (Q3 FY27 call, Walmart transcript)", "walmart_primary",
  "metric", "sparky_metrics",
  ["product", "finance", "marketing_crm"], ["shopper"], ["CAP-05"], "high",
  "On the Q3 FY27 call Furner said U.S. Sparky usage grew 129% year over year and Sparky baskets are 40% larger; Sparky added voice and image shopping plus Spanish and French, and recently launched in Mexico, Canada and at Sam's Club U.S. Same figures in three third-party transcripts, PPC Land and CX Dive. Supersedes the Q2 figure (+70%, ST-040) for stage use.",
  "Agents are beginning to play a bigger role in more shopping journeys", as_of="2026-11-20")
R("ST-197", Q3, "2026-11-19", "John Furner", "President & CEO (Q3 FY27 call, Walmart transcript)", "walmart_primary",
  "capability_claim", "agent_profiles_timing",
  ["product", "trust_safety"], ["shopper", "agent_builder", "caregiver"], ["CAP-02", "CAP-01"], "high",
  "On the Nov 19 call Furner restated the October package in the future tense: by assigning profiles to agents, customers will be able to set permissions and spending limits, see agent purchases separately and turn access off; the Agent Gateway gives approved agents a better way to interact while protecting customer information; agentic terms set what agents can and cannot do. No launch date; the name Agent Profiles is not used. CAP-02 stays announced.",
  as_of="2026-11-20")
R("ST-198", PPC_Q3, "2026-11-19", "John David Rainey / Seth Dallaire", "CFO / EVP & Chief Growth Officer (Q3 FY27 call, via PPC Land)", "press",
  "metric", "ads_growth",
  ["connect_ads", "finance"], ["supplier_brand", "marketplace_seller"], ["CAP-34"], "high",
  "Q3 FY27: global advertising grew 25% (38% in Q2), slowed by Flipkart's sale timing; U.S. advertising including VIZIO and Vibe grew 37%, Walmart Connect 36% (43% in Q2). Walmart did not say whether Sparky carries paid placements today or how sponsored items are marked. Asked about a competitor barring third-party agents, Dallaire did not name it and gave no figures.",
  as_of="2026-11-20")
R("ST-199", Q3, "2026-11-19", "John David Rainey / David Guggina", "CFO / President & CEO, Walmart U.S. (Q3 FY27 call, Walmart transcript)", "walmart_primary",
  "metric", "growth_engines",
  ["finance", "marketplace", "supply_chain"], ["shopper", "marketplace_seller"], ["CAP-35"], "high",
  "Q3 FY27: global e-commerce +17%, U.S. e-commerce +23% (11th straight quarter above 20%), Sam's Club e-commerce +30%; U.S. marketplace and WFS net sales +49%, nearly half of marketplace GMV through Walmart Fulfillment Services; U.S. e-commerce incremental margin over 12% and close to break-even excluding ads. Guggina: Walmart can reach 96% of U.S. households in three hours or less and 60% in 30 minutes or less (assuming a 15-minute pick); 30-minute deliveries nearly tripled. No pickup or delivery slot product was discussed.",
  as_of="2026-11-20")
R("ST-200", UCP_UPD, "2026-11", "Google (UCP for Merchant Center)", "UCP developer docs, latest updates (page last updated Nov 17)", "partner",
  "capability_claim", "ucp",
  ["partnerships", "product"], ["agent_builder", "ai_platform"], ["CAP-40", "CAP-10"], "high",
  "Google's UCP change log for November 2026 adds an MCP transport guide (beta) for native checkout and cart over JSON-RPC tools/call, checkout latency work, and order-lifecycle webhook acknowledgments and retries; October added a loyalty extension and grocery ordering for connected apps (location search, catalog search and cart tools). No entry covers pickup or delivery slots, sponsored-item disclosure or AP2.",
  as_of="2026-11-20")
