# Batch 5: responsible AI, Global Tech primary posts, Amazon/Jassy, pricing watchdogs, Adobe, misc partner voices.
from registry import R

RAI = "https://corporate.walmart.com/news/2023/10/17/our-responsible-ai-pledge-setting-the-bar-for-ethical-ai"
R("ST-166", RAI, "2023-10-17", "Walmart, corporate", "Responsible AI Pledge", "walmart_primary", "constraint", "rai_pledge",
  ["trust_safety"], ["shopper", "store_associate"], ["CON-09", "CON-22"], "high",
  "Walmart's Responsible AI Pledge has six commitments: transparency, security, privacy, fairness, accountability, customer-centricity. Fairness: evaluate AI tools for bias and repeat the checks.",
  "evaluate AI tools for bias")
R("ST-167", RAI, "2023-10-17", "Walmart, corporate", "Responsible AI Pledge", "walmart_primary", "constraint", "human_accountability",
  ["trust_safety", "product"], ["shopper"], ["CON-22", "CAP-03"], "high",
  "Accountability: AI stays managed by people and Walmart takes responsibility for its effects. Customer-centricity: measure satisfaction with AI interactions and check tools stay accurate and useful.",
  "We will use AI managed by people")
R("ST-168", "https://tech.walmart.com/content/walmart-global-tech/en_us/blog/post/the-importance-of-digital-citizenship-at-walmart.html", "2023-01-01", "Walmart Global Tech", "Digital Citizenship post", "walmart_primary", "constraint", "digital_trust",
  ["trust_safety"], ["shopper", "store_associate"], ["CON-08", "CON-22"], "medium",
  "Walmart's four Digital Trust Commitments restate its values for data and technology, e.g. service (technology in service of people) and respect (treat people fairly, with dignity and respect); a Digital Citizenship team under the Chief Legal Officer oversees them.")
R("ST-169", "https://tech.walmart.com/content/walmart-global-tech/en_us/blog/post/a-conversation-with-john-furner-and-suresh-kumar.html", "2026-04-24", "John Furner / Suresh Kumar", "CEO / Global CTO & CDO (fireside)", "walmart_primary", "goal", "intent_to_solution",
  ["product", "supply_chain"], ["shopper"], ["CAP-35"], "medium",
  "The fireside frames the goal as moving from a customer's intent to a delivered solution in under 40 minutes, and says speed depends on the teams behind the technology and on trust.",
  "the secret ingredient isn't in the code, it's in the culture")
R("ST-170", "https://tech.walmart.com/content/walmart-global-tech/en_us/blog/post/inside-the-ai-network-orchestrating-walmarts-fastest-holiday-deliveries-yet.html", "2025-12-08", "Walmart Global Tech", "engineering blog", "walmart_primary", "capability_claim", "fulfillment_orchestration",
  ["supply_chain"], ["shopper", "store_associate"], ["CAP-37", "CAP-10"], "medium",
  "Walmart describes a connected system of predictive, agentic and real-time models that decides which products are needed and where to position them before a customer buys, orchestrating fulfillment, logistics and delivery in real time.")
R("ST-171", "https://www.8thandwalton.com/?p=74341", "2025-12-05", "Walmart, corporate (via MassMarketRetailers / 8th & Walton)", "holiday recap", "press", "metric", "same_day_peak",
  ["supply_chain"], ["shopper"], ["CAP-35"], "low",
  "Walmart said its same-day network fulfilled 57% more orders than the prior holiday, nearly half in under three hours and the fastest in 10 minutes.")

# --- Amazon (competitor voice)
R("ST-172", "https://www.retailbrew.com/stories/2026/02/10/amazon-ceo-says-shoppers-will-choose-retailers-over-third-party-ai-platforms", "2026-02-05", "Andy Jassy", "CEO, Amazon (Q4 2025 call, via Retail Brew)", "press", "non_goal", "horizontal_agents",
  ["partnerships"], ["ai_platform"], [], "high",
  "Jassy argued many customers will choose a retailer's own shopping agent over horizontal agents, which lack shopping history and get product details and pricing wrong; shoppers want selection, low prices, fast delivery and a trusted retailer.",
  "These horizontal agents don't have any of your shopping history.")
R("ST-173", "https://ppc.land/us-alexa-for-shopping-users-spend-50-more-per-order-amazon-says/", "2026-10-29", "Andy Jassy", "CEO, Amazon (Q3 2026 call, via PPC Land)", "press", "metric", "alexa_for_shopping",
  ["product", "finance"], ["shopper"], [], "high",
  "Jassy said U.S. Alexa for Shopping users spend 50% more per order, 400M+ customers used it in 12 months, and Amazon expects it to be the primary agent customers use to shop Amazon while it anticipates working with horizontal agents.",
  "the primary shopping agent customers use to shop Amazon")

# --- Pricing watchdogs and regulators
R("ST-174", "https://techcrunch.com/2026/01/13/a-consumer-watchdog-issued-a-warning-about-googles-ai-agent-shopping-protocol-google-says-shes-wrong/", "2026-01-13", "Lindsay Owens / Google", "Exec. Director, Groundwork Collaborative / Google comms", "press", "risk", "personalized_upsell",
  ["trust_safety", "connect_ads", "finance"], ["shopper"], ["CON-05", "CON-21"], "high",
  "Groundwork's Owens warned UCP's roadmap item on personalized upsells could enable surveillance pricing; Google called the claims inaccurate and said merchants may not show prices on Google higher than on their own site.")
R("ST-175", "https://www.searchenginejournal.com/google-ai-mode-checkout-cant-raise-prices/565016/", "2026-01-14", "Search Engine Journal", "press", "press", "risk", "upsell_roadmap",
  ["connect_ads", "trust_safety"], ["shopper", "ai_platform"], ["CON-21"], "medium",
  "The UCP public roadmap lists native cross-sell and upsell modules for personalized recommendations based on user context: the feature critics point to.")
R("ST-176", "https://stellagent.ai/insights/google-ai-checkout-warren-privacy", "2026-05-01", "Sen. Elizabeth Warren (via Stellagent / eWeek)", "regulator letter", "press", "risk", "checkout_privacy",
  ["trust_safety", "partnerships"], ["shopper", "ai_platform"], ["CON-01", "CON-07"], "low",
  "Senator Warren pressed Google's CEO for clarity on Gemini checkout privacy as UCP expanded across retailers: congressional attention to agent checkout data flows. Secondary report.")

# --- Market signals
R("ST-177", "https://www.retailtouchpoints.com/?p=621887", "2026-10-29", "Adobe Digital Insights (via Retail TouchPoints)", "analyst data", "analyst", "metric", "ai_referrals",
  ["marketing_crm", "finance"], ["shopper"], [], "high",
  "Adobe: AI-referred traffic to U.S. retail sites grew 71% YoY in Sep 2026 (1,772% since Oct 2024), converted 90% better and earned 83% more revenue per visit than non-AI traffic.")
R("ST-178", "https://business.adobe.com/resources/sdk/.q3-ai-traffic-trends-report/q3-2026-ai-sourced-traffic-insights.pdf", "2026-07-01", "Adobe Digital Insights", "report", "analyst", "metric", "ai_referrals_trust",
  ["marketing_crm"], ["shopper"], [], "medium",
  "Adobe's mid-2026 report: AI-referred visitors converted 54% better in May 2026, reversing the prior year's gap; it flags meaningful content gaps in retailers' AI readability.")
R("ST-179", "https://www.pymnts.com/?p=4214915", "2026-06-15", "PYMNTS Intelligence with Visa Acceptance Solutions", "survey", "analyst", "problem", "merchant_readiness",
  ["marketplace", "partnerships"], ["marketplace_seller", "small_business"], ["CAP-20"], "medium",
  "Survey: only 15% of merchants overall have structured product data ready for agent access; small merchants could move faster.")
R("ST-180", "https://www.pymnts.com/?p=4329007", "2026-10-21", "PYMNTS Intelligence", "survey", "analyst", "problem", "merchant_unprepared",
  ["marketplace"], ["marketplace_seller", "supplier_brand"], [], "medium",
  "PYMNTS report on the 2026 season: merchants expect agentic commerce to become a paid sales channel but many feel unprepared to connect with agents.")
R("ST-181", "https://www.bain.com/insights/rewiring-demand-generation-in-age-of-AI-agents/", "2026-05-08", "Bain & Company", "consumer survey", "analyst", "metric", "consumer_openness",
  ["marketing_crm"], ["shopper"], [], "medium",
  "Bain surveys: 30-45% of U.S. consumers use AI for shopping support and 64% have used or are open to using AI to complete a purchase; 44% of online buyers mostly start in an LLM or split time with search.")

# --- Other partner and competitor voices
R("ST-182", "https://www.eweek.com/news/instacart-ai-cart-assistant/", "2025-10-01", "Yael Cosset", "EVP & Chief Digital Officer, Kroger (via eWeek)", "press", "desire", "kroger_agentic",
  ["product"], ["shopper"], [], "medium",
  "Kroger's Cosset said interacting with an AI agent makes shopping and meal planning as simple as a conversation, building baskets and understanding what matters to customers; Kroger adopts Instacart's Cart Assistant.")
R("ST-183", "https://aimmediahouse.com/retail/ai-shopping-agents-fail-43-of-the-time-most-failures-still-end-in-a-purchase", "2026-11-12", "AIM Media House", "press", "press", "non_goal", "cross_industry_blocks",
  ["partnerships", "trust_safety"], ["ai_platform"], [], "medium",
  "Days after Visa's benchmark, United Airlines said (Nov 11) it will restrict third-party AI agents on its platforms and via OTAs; openness to agents is not the default outside retail.")
R("ST-184", "https://thenewstack.io/?p=22837835", "2026-09-23", "The New Stack", "press", "press", "capability_claim", "shopify_muse",
  ["partnerships"], ["ai_platform", "marketplace_seller"], [], "medium",
  "After Amazon blocked Muse for not identifying itself and appearing to hold passwords, Shopify wired Muse into its merchants with Shop Pay checkout: platforms that offer a sanctioned path win the agent traffic.")
R("ST-185", "https://www.pulse.bot/cio-pulse/news/target-forces-shoppers-to-own-aimade-purchases-in-new-gemini-terms-2998f952-44ee-4b49-90c6-e759ad3bed85", "2026-04-01", "Pulse (aggregator)", "press", "forum", "constraint", "liability_shift",
  ["trust_safety"], ["shopper"], ["CON-17"], "low",
  "Aggregator report: Target's Gemini terms make shoppers responsible for AI-made purchases. Comparable to Walmart's terms keeping the customer responsible for payment, returns and disputes. Unverified.")
R("ST-186", "https://talkbusiness.net/2026/07/the-supply-side-walmarts-sparky-shopping-agent-drives-more-sales/", "2026-04-01", "John Furner", "President & CEO (via Talk Business)", "press", "goal", "intent_driven",
  ["product", "supply_chain"], ["shopper"], ["CAP-05", "CAP-35"], "medium",
  "Furner described Sparky as Walmart's evolution into intent-driven commerce: when the AI builds a basket, Walmart fulfills it through fast delivery or pickup, turning AI engagement into immediate physical outcomes.",
  "immediate physical outcomes")
R("ST-187", "https://talkbusiness.net/2026/05/the-supply-side-ai-changing-relationships-between-retailers-suppliers/", "2026-05-01", "Talk Business & Politics (supplier community)", "press", "press", "risk", "supplier_adoption",
  ["merchandising"], ["supplier_brand"], ["CAP-39"], "low",
  "Supplier-side commentators in Northwest Arkansas say suppliers that do not adopt agentic systems risk being left behind as Walmart's buying and replenishment tools become agentic.")
