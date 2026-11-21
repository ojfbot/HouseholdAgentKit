# Batch 3: payments/protocol partners, AI platforms, sellers, suppliers, associates/drivers, competitors, Sparky releases, eng blog.
from registry import R

# --- AI platform and protocol partners
R("ST-081", "https://developers.googleblog.com/under-the-hood-universal-commerce-protocol-ucp/", "2026-01-11", "Amit Handa / Ashish Gupta", "Google Commerce engineering", "partner", "capability_claim", "ucp",
  ["partnerships", "product"], ["ai_platform", "agent_builder"], ["CAP-32", "CAP-40"], "high",
  "Google describes UCP as an open-source standard for agentic commerce that works with existing retail infrastructure and is compatible with AP2 for agent payments; businesses integrate via APIs, A2A or MCP, with an embedded option to keep a custom checkout.")
R("ST-082", "https://www.computerweekly.com/blog/Open-Source-Insider/Google-banks-on-Universal-Commerce-Protocol-UCP-for-agentic-commerce", "2026-01-12", "Vidhya Srinivasan", "VP & GM Ads & Commerce, Google (via Computer Weekly)", "press", "capability_claim", "ucp_codev",
  ["partnerships"], ["ai_platform"], ["CAP-40"], "medium",
  "UCP was co-developed with Shopify, Etsy, Wayfair, Target and Walmart and is designed to work alongside A2A, AP2 and MCP.")
R("ST-083", "https://agentpedia.codes/blog/ucp-universal-commerce-protocol-guide", "2026-05-01", "agentpedia (developer guide)", "press", "press", "capability_claim", "ucp_scope",
  ["product", "partnerships"], ["agent_builder"], ["CAP-40", "CAP-10"], "low",
  "Developer guide: UCP negotiates capabilities such as Checkout, Cart, Catalog, Order Management and Identity Linking over REST, MCP, A2A or embedded; payments are delegated to AP2. No fulfillment-slot capability is listed. Secondary source; verify against the spec.")
R("ST-084", "https://ap2-protocol.org/", "2025-09-16", "AP2 project (Google + 60 partners)", "protocol site", "partner", "capability_claim", "mandates",
  ["trust_safety", "product"], ["agent_builder", "ai_platform"], ["CAP-30", "CAP-29"], "high",
  "AP2 defines an Intent Mandate (conditions under which an agent may buy when the human is not present) and a Cart Mandate (the user's explicit sign-off on exact items and price when present); a Payment Mandate signals agent involvement to networks.")
R("ST-085", "https://martech.zone/acronym/ap2/", "2026-04-30", "MarTech Zone", "press", "press", "capability_claim", "mandates",
  ["trust_safety"], ["agent_builder"], ["CAP-30"], "medium",
  "AP2 v0.2 (April 2026) added autonomous human-not-present payments, and Google donated the protocol to the FIDO Alliance.")
R("ST-086", "https://forkast.news/openai-built-in-chat-checkout-for-ai-commerce-five-months-later-it-walked-away/", "2026-03-10", "Forkast", "press analysis", "press", "problem", "in_chat_checkout",
  ["partnerships"], ["ai_platform"], ["CAP-32"], "medium",
  "OpenAI launched Instant Checkout with the Stripe-built Agentic Commerce Protocol on Sep 29 2025 and withdrew it by early March 2026, moving checkout into retailer apps inside ChatGPT; ACP survives as discovery-to-merchant plumbing.")
R("ST-087", "https://ecommercenews.com.au/story/chatgpt-s-checkout-retreat-an-opportunity-for-aussie-retailers", "2026-03-12", "OpenAI spokesperson (via eCommerceNews)", "partner statement", "partner", "desire", "discovery_first",
  ["partnerships", "marketing_crm"], ["ai_platform"], ["CAP-32"], "medium",
  "OpenAI said it is prioritizing making ChatGPT search and product discovery great, with ACP as infrastructure connecting users to merchants.")
R("ST-088", "https://seekingalpha.com/pr/20264002-visa-introduces-trusted-agent-protocol-an-ecosystem-led-framework-for-ai-commerce", "2025-10-14", "Visa", "press release", "partner", "problem", "agent_identity",
  ["trust_safety", "partnerships"], ["agent_builder"], ["CON-16", "CAP-02"], "high",
  "Visa launched Trusted Agent Protocol citing merchant problems: bot detection wrongly blocking legitimate agents, supporting agent guest and logged-in checkout, and keeping visibility into the consumer behind the agent; it cited a 4,700% surge in AI-driven retail traffic.")
R("ST-089", "https://corporate.visa.com/en/sites/visa-perspectives/press-releases/visa-intelligent-commerce-connect-ai-shopping-for-businesses.html", "2026-04-20", "Visa", "press release", "partner", "capability_claim", "protocol_agnostic",
  ["partnerships", "finance"], ["agent_builder"], ["CAP-40"], "high",
  "Visa Intelligent Commerce Connect is pitched as a network-, protocol- and token-vault-agnostic on-ramp that accepts agent payments via TAP, MPP, ACP and UCP.")
R("ST-090", "https://www.pymnts.com/visa/2026/visa-ceo-says-ai-shopping-has-arrived-but-agentic-payments-havent", "2026-09-08", "Ryan McInerney", "CEO, Visa (Goldman Sachs conference)", "partner", "problem", "trust_barrier",
  ["trust_safety", "marketing_crm"], ["shopper"], ["CAP-02", "CAP-29"], "high",
  "McInerney said consumers use AI to shop but still go to sellers' sites to pay; the barrier to autonomous payment, in one word, is trust.",
  "adoption for shopping, but not yet for autonomous payments")
R("ST-091", "https://www.mastercard.com/au/en/news-and-trends/stories/2025/agentic-commerce-framework.html", "2025-05-01", "Mastercard", "Agent Pay Acceptance Framework", "partner", "capability_claim", "agentic_tokens",
  ["trust_safety", "finance"], ["agent_builder"], ["CON-02", "CAP-03"], "high",
  "Mastercard registers each agent and lets it transact with agentic tokens, dynamic credentials making every transaction traceable and authenticated, usable in existing checkout forms.")
R("ST-092", "https://diginomica.com/agentic-commerce-and-legacy-payments-providers-ceos-visa-mastercard-and-amex-why-theres-life-old", "2026-05-05", "Michael Miebach", "CEO, Mastercard (via diginomica)", "partner", "desire", "assisted_first",
  ["trust_safety", "product"], ["shopper"], [], "medium",
  "Miebach expects agent-assisted commerce first and autonomy later, and frames Agent Pay as a trust layer for the extra party in the payment chain, the agent.")
R("ST-093", "https://www.benzinga.com/markets/tech/26/09/61963074", "2026-09-17", "Mark Zuckerberg", "CEO, Meta (Connect 2026, via Benzinga)", "partner", "desire", "muse_model",
  ["partnerships", "finance"], ["ai_platform"], ["CAP-01"], "medium",
  "Zuckerberg said Muse stays free for most use and Meta expects to profit by taking a small fee from transactions Muse completes, such as purchases; Walmart, Best Buy and others signed on as shopping partners.")
R("ST-094", "https://www.ctvnews.ca/sci-tech/article/walmart-welcomes-ai-agents-as-anthropic-launches-its-own/", "2026-10-21", "AFP (via CTV)", "press", "press", "capability_claim", "agent_wave",
  ["partnerships"], ["ai_platform", "agent_builder"], [], "medium",
  "The same day as Walmart's launch, Anthropic previewed Claude Duet, a background agent across connected apps that can buy with approval; OpenAI launched always-on agents called Dots a month earlier. Outside agents are becoming background, triggered actors.")

# --- Marketplace sellers
R("ST-095", "https://eva.guru/answers/what-walmart-agent-gateway-means-for-sellers/", "2026-10-22", "Eva (seller agency)", "partner guidance", "partner", "desire", "seller_readiness",
  ["marketplace"], ["marketplace_seller"], ["CAP-20"], "medium",
  "Seller-agency reading: there is no seller enrollment step for the Gateway; the listing, price and availability are what an agent reads, so listing quality and in-stock rates matter more; same price for agents means no agent price to manage.")
R("ST-096", "https://marketplacepulse.com/articles/walmart-marketplace-growth-reaches-fastest-pace-in-years", "2026-06-04", "Marketplace Pulse", "analyst", "analyst", "metric", "marketplace_scale",
  ["marketplace", "finance"], ["marketplace_seller"], [], "medium",
  "Marketplace Pulse estimates about 200,000 active sellers; U.S. third-party sales grew nearly 50% in Q1 FY27, with a cross-border marketplace into Canada and Mexico.")
R("ST-097", "https://marketplacelearn.walmart.com/releasenotes", "2026-11-12", "Walmart Marketplace", "Seller Center release notes", "walmart_primary", "constraint", "seller_standards",
  ["marketplace", "care_returns"], ["marketplace_seller"], ["CAP-18"], "medium",
  "Recent seller release notes: from Oct 19 seller-fulfilled offers with return-policy exemptions lose the Walmart+ badge; reminders on fulfillment lag time; Ship with Walmart labels in ShipStation (Nov 12).")
R("ST-098", "https://marketplacelearn.walmart.com/guides/Policies%20&%20standards/Performance/Seller-performance-standards", "2026-06-05", "Walmart Marketplace", "Seller performance standards", "walmart_primary", "constraint", "edd",
  ["marketplace", "supply_chain"], ["marketplace_seller"], ["CAP-10"], "medium",
  "Sellers must pick lag time, shipping method, carrier and service level to meet the Expected Delivery Date; late handover, late shipment and missing carrier scans count against them; suppression, suspension, termination escalate.")
R("ST-099", "https://www.pulse.bot/ecommerce/news/walmart-marketplace-suspends-hundreds-of-sellers-in-alleged-priceparity-crackdown-0f9e279a-eed3-4a3a-a796-1c77cfb09a6f/", "2026-06-07", "Pulse (aggregator, uncited)", "press", "forum", "problem", "price_parity",
  ["marketplace", "trust_safety"], ["marketplace_seller"], ["CAP-04"], "low",
  "Weak signal: an uncited aggregator reported suspensions of sellers pricing higher on Walmart than Amazon and agencies complaining of suspensions without clear explanation. Treat as unverified.")
R("ST-100", "https://stellagent.ai/insights/walmart-sparky-brand-visibility-azoma", "2026-09-01", "Azoma (via Stellagent)", "vendor analysis", "analyst", "problem", "sparky_citations",
  ["marketplace", "connect_ads", "merchandising"], ["marketplace_seller", "supplier_brand"], ["CAP-20", "CAP-34"], "low",
  "A visibility-tool vendor claims most of what Sparky cites sits outside the retailer listing (earned media, brand sites); vendor-sourced and unaudited, but it signals sellers' anxiety about how agents choose.")
R("ST-101", "https://www.foodnavigator.com/Article/2026/09/21/walmarts-ai-and-fulfillment-push-boosts-cpg-brand-discovery/", "2026-09-14", "David Guggina", "President & CEO, Walmart U.S. (Goldman Sachs conf., via FoodNavigator)", "press", "goal", "aeo",
  ["merchandising", "marketplace", "product"], ["supplier_brand", "marketplace_seller", "ai_platform"], ["CAP-32"], "high",
  "Guggina said Walmart is embracing agentic engine optimization to stay discoverable in AI shopping; customers arriving from ChatGPT and Gemini convert at very high rates, many new or returning, with high organic repeat.",
  "converting at very high rates")
R("ST-102", "https://www.foodnavigator.com/Article/2026/09/21/walmarts-ai-and-fulfillment-push-boosts-cpg-brand-discovery/", "2026-09-14", "David Guggina", "President & CEO, Walmart U.S. (via FoodNavigator)", "press", "metric", "speed_assortment",
  ["supply_chain", "merchandising"], ["shopper"], ["CAP-35"], "medium",
  "Guggina: about 70% of online orders delivered same day or faster; visual shopping lifts conversion 57% over text; Sparky usage +60% QoQ; fewer units per SKU to carry more SKUs.",
  "You reduce your units per SKU, so you can have more SKUs.")

# --- Suppliers and brands
R("ST-103", "https://w3c.github.io/ecommerce-for-humans-and-AI-Agents-workshop/position_statement/PG_Position_Statement_W3C_GS1_Agentic_Commerce.pdf", "2026-09-01", "Procter & Gamble", "W3C/GS1 workshop position statement", "partner", "problem", "product_data",
  ["merchandising", "marketplace"], ["supplier_brand"], ["CAP-22", "CAP-20"], "high",
  "P&G says product content can fall short of what agents need to recommend confidently, data is rebuilt per retailer and agent, and brands need a way to correct inaccurate health, safety and regulatory claims.",
  "one trusted source of truth")
R("ST-104", "https://w3c.github.io/ecommerce-for-humans-and-AI-Agents-workshop/position_statement/PG_Position_Statement_W3C_GS1_Agentic_Commerce.pdf", "2026-09-01", "Procter & Gamble", "W3C/GS1 workshop position statement", "partner", "desire", "consumer_choice",
  ["trust_safety", "connect_ads"], ["supplier_brand", "shopper"], ["CON-03"], "high",
  "P&G wants GTIN/GS1-based retailer-agnostic product data, open and auditable checkout, retained visibility into the shopper, clear disclosure when agents recommend, and consumers keeping meaningful choice.",
  "meaningful choice")
R("ST-105", "https://www.bain.com/insights/rewiring-demand-generation-in-age-of-AI-agents/", "2026-05-08", "Bain & Company", "analyst brief", "analyst", "risk", "invisible_shelf",
  ["merchandising", "connect_ads", "finance"], ["supplier_brand"], [], "medium",
  "Bain: if an agent does not select a product it effectively does not exist; agents favor concrete, review-backed attributes; fully agentic U.S. commerce could reach $300-500B by 2030; CPG firms will need to train retailers' own agents.")
R("ST-106", "https://clarkstonconsulting.com/?p=66278", "2026-10-28", "Clarkston Consulting", "analyst note", "analyst", "problem", "agent_attribution",
  ["connect_ads", "merchandising"], ["supplier_brand"], ["CAP-02", "CON-01"], "low",
  "CPG view: agent-assisted shopping adds a layer between brand communication and product choice, and manufacturers may struggle to tell agent purchases from shopper purchases.")
R("ST-107", "https://talkbusiness.net/2026/07/the-supply-side-walmarts-sparky-shopping-agent-drives-more-sales/", "2026-06-09", "David Guggina", "President & CEO, Walmart U.S. (Oppenheimer conf., via Talk Business)", "press", "metric", "sparky_metrics",
  ["product", "finance"], ["shopper"], ["CAP-05"], "medium",
  "Guggina: Sparky weekly active users up 110%+ QoQ, Sparky-attributed sales +150% in Q1, baskets 35% larger, units via Sparky up 4x YoY driven by food and consumables; still very early.",
  "it is still very early in this space")
R("ST-108", "https://talkbusiness.net/2026/07/the-supply-side-walmarts-sparky-shopping-agent-drives-more-sales/", "2026-07-01", "Daniel Danker", "EVP AI Acceleration, Product & Design (via Talk Business)", "press", "desire", "problem_to_solution",
  ["product", "store_ops"], ["shopper"], ["CAP-05", "CAP-06"], "medium",
  "Danker said customers have shifted from asking for search help to describing a problem and letting the agent provide solutions; 85% of shopping is still in stores, a blind spot; Sparky will eventually restock pantry and fridge automatically.",
  "describing a problem and having the agent provide solutions")

# --- Associates and drivers
R("ST-109", "https://corporate.walmart.com/news/2025/06/24/walmart-unveils-new-ai-powered-tools-to-empower-1-5-million-associates/", "2025-06-24", "Walmart, corporate", "newsroom", "walmart_primary", "capability_claim", "associate_tools",
  ["store_ops"], ["store_associate"], ["CAP-09"], "high",
  "Associate app tools: AI task management (shift planning cut from 90 to 30 minutes), real-time translation in 44 languages, a gen-AI upgrade of the associate assistant (900k+ weekly users, 3M+ queries a day), RFID plus AR (VizPick).")
R("ST-110", "https://fortune.com/2025/09/30/billion-dollar-retail-giant-walmart-ceo-doug-mcmillon-cant-think-of-a-single-job-that-wont-be-changed-by-ai-artifical-intelligence-how-employees-can-prepare/", "2025-09-30", "Doug McMillon", "then President & CEO (via WSJ/Fortune)", "press", "goal", "workforce",
  ["store_ops", "finance"], ["store_associate"], ["CAP-09"], "high",
  "McMillon said AI will change literally every job; Walmart expects headcount to stay roughly flat at 2.1M for three years as the mix changes, and created agent-builder roles.",
  "AI is going to change literally every job")
R("ST-111", "https://www.retailbrew.com/stories/key-takeaways-from-walmart-associates-week", "2026-06-10", "John Furner / Daniel Danker", "CEO / EVP (Associates Week, via Retail Brew)", "press", "capability_claim", "sparky_in_store",
  ["store_ops", "product"], ["store_associate", "shopper"], ["CAP-09", "CAP-05"], "medium",
  "About 1.3M U.S. associates carry fresh touring agents surfacing the next best action and store layouts; Danker said Sparky serves customers in stores as well as online.")
R("ST-112", "https://www.ftc.gov/news-events/news/press-releases/2026/02/walmart-agrees-100-million-judgment-settle-ftc-states-charges-over-deceptive-earnings-claims-related/walmart-spark-driver-faqs", "2026-02-26", "FTC", "regulator", "press", "risk", "driver_pay_honesty",
  ["trust_safety", "supply_chain"], ["spark_driver"], ["CAP-19", "CON-11"], "high",
  "Walmart agreed to a $100M judgment with the FTC and 11 states over alleged inflated base-pay and tip displays to Spark drivers and claims that 100% of tips reached drivers; it must not misrepresent offer earnings. Texas separately settled for $13M+.")
R("ST-113", "https://mwm.ai/articles/app-updates/spark-driver-v4-48-1-sparks-backlash-over-new-rewards-tiers-and-pay-changes-in-september-2026", "2026-10-05", "app-review analysis", "forum signal", "forum", "problem", "driver_experience",
  ["supply_chain"], ["spark_driver"], ["CAP-19"], "low",
  "Weak signal: after Spark Driver v4.48.1 (Sep 30 2026) introduced reward tiers, app-store ratings for the version fell (about 3.5 to 2.5) amid complaints of penalties and pay instability.")
R("ST-114", "https://news.yahoo.com/gig-drivers-walmart-forced-compete-175300785.html", "2025-08-01", "Walmart, corporate (statement to press)", "statement", "press", "constraint", "driver_bots",
  ["trust_safety", "supply_chain"], ["spark_driver"], ["CON-16"], "medium",
  "Drivers reported competing against bots for offers; Walmart said bot use breaks Spark Driver terms and it deactivates drivers who misuse the platform. Automation is unwelcome on the driver side.")

# --- Competitors
R("ST-115", "https://www.thestar.com.my/tech/tech-news/2026/09/22/amazon-blocks-metas-muse-ai-agent-from-its-retail-site", "2026-09-22", "Amazon (statement, via Bloomberg)", "competitor", "press", "non_goal", "closed_garden",
  ["partnerships", "finance"], ["ai_platform"], [], "high",
  "Amazon blocked Meta's Muse and asked Meta to remove Amazon, saying third-party agents must operate openly; Amazon sued Perplexity over Comet and builds its own agents (Alexa for Shopping, Buy for Me).")
R("ST-116", "https://www.modernretail.co/technology/marketplace-briefing-why-amazon-discontinued-its-ai-powered-rufus-chatbot-for-alexa-shopping-agent/", "2026-05-14", "Modern Retail", "press", "press", "capability_claim", "alexa_for_shopping",
  ["product"], ["shopper"], [], "medium",
  "Amazon replaced Rufus with Alexa for Shopping (May 2026), bringing Alexa+ into search; it can track prices and auto-buy at shopper-set thresholds; Buy for Me buys from outside brand sites.")
R("ST-117", "https://corporate.target.com/press/fact-sheets/2026/06/conversational-ai", "2026-06-16", "Target", "fact sheet", "press", "capability_claim", "target_agentic",
  ["partnerships"], ["ai_platform"], ["CAP-40"], "high",
  "Target says shoppers can buy directly in Google AI Mode and Gemini via UCP, in a Target app in ChatGPT (with Circle benefits at checkout) and in Microsoft Copilot; it named a first chief AI officer in Aug 2026.")
R("ST-118", "https://www.pymnts.com/commerce/ecommerce/2026/walmart-and-home-depot-set-the-rules-for-ai-shoppers/", "2026-10-30", "PYMNTS", "press", "press", "constraint", "rules_trend",
  ["trust_safety", "partnerships"], ["agent_builder"], ["CON-15"], "medium",
  "PYMNTS groups Walmart with Home Depot as retailers publishing rules for AI shoppers; publishing terms is becoming the norm for open retailers.")
R("ST-119", "https://www.axios.com/2026/10/21/walmart-amazon-agents-muse", "2026-10-21", "Neil Saunders", "Managing Director, GlobalData Retail (via Axios)", "analyst", "risk", "ads_conflict",
  ["connect_ads", "finance"], ["ai_platform"], ["CAP-34"], "medium",
  "Saunders says Amazon keeps a closed ecosystem likely fearing agentic shopping undermines its ad business, and that the calculation could change if third-party agents take a bigger share of discovery.",
  "its closed ecosystem")

# --- Sparky releases (don't-pitch inputs)
R("ST-120", "https://ppc.land/walmarts-ai-agent-sparky-turns-photos-of-handwritten-lists-into-carts/", "2026-10-30", "Walmart, corporate (newsroom, via PPC Land)", "newsroom", "walmart_primary", "capability_claim", "sparky_holiday",
  ["product", "store_ops"], ["shopper"], ["CAP-05", "CAP-41"], "high",
  "Six new Sparky features (Oct 30 2026): photo of a problem to products; photo of a handwritten or Notes list to a cart matched to past purchases at the usual store; Shop to Light shelf labels; recipe generation with ingredients to cart; healthier swaps; Spanish and French. Voice chainwide by year end.")
R("ST-121", "https://retaildive.com/news/walmart-sparky-features-AI-holidays/873718", "2026-11-02", "Retail Dive", "press", "press", "capability_claim", "holiday_competition",
  ["product"], ["shopper"], ["CAP-05"], "medium",
  "Retail Dive places the update alongside Target's Ask Target beta, Amazon's Alexa for Shopping and Best Buy's Ask Blue; no accuracy figures were given for image or list features.")
R("ST-122", "https://www.retaildive.com/news/walmart-launches-generative-ai-assistant-sparky/750300", "2025-06-06", "Walmart, corporate (via Retail Dive)", "launch", "press", "capability_claim", "sparky_design",
  ["product"], ["shopper"], ["CAP-05", "CAP-07"], "medium",
  "At launch Walmart said early tests showed agents work best on highly specific tasks, and Sparky stitches together results from those tasks to solve complex queries; reordering and service booking were promised.")

# --- Engineering voice
R("ST-123", "https://tech.walmart.com/content/walmart-global-tech/en_us/blog/post/using-llms-to-manage-product-catalogs.html", "2025-01-01", "Walmart Global Tech", "engineering blog", "walmart_primary", "problem", "catalog_quality",
  ["merchandising", "marketplace"], ["marketplace_seller", "supplier_brand"], ["CAP-20", "CAP-22"], "medium",
  "Walmart engineers call inaccurate, inconsistent product data a major issue; they use a multi-agent LLM pipeline (extraction then a separate quality-check LLM trained on human-validated data) across billions of data points.")
R("ST-124", "https://tech.walmart.com/content/walmart-global-tech/en_us/blog/post/the-ai-behind-cross-lingual-search-at-walmart.html", "2025-12-16", "Walmart Global Tech", "engineering blog", "walmart_primary", "capability_claim", "cross_lingual",
  ["product", "marketing_crm"], ["shopper"], ["CAP-05"], "medium",
  "Cross-lingual search combines catalog knowledge, language detection and models to answer within 50ms; an LLM translation cache covers up to 95% of query traffic in some markets.")
R("ST-125", "https://tech.walmart.com/content/walmart-global-tech/en_us/blog/post/driving-faster-experimentation-through-interleaving-in-walmart-search.html", "2025-12-30", "Garima Choudhary", "Senior Data Scientist, Walmart Global Tech", "walmart_primary", "metric", "experimentation",
  ["product"], ["shopper"], [], "medium",
  "Walmart search uses interleaving to compare ranking algorithms within one session, learning from real interactions faster than separate A/B cycles.")
R("ST-126", "https://public.walmart.com/content/walmart-global-tech/en_us/blog/post/wibey-announcement.html", "2025-10-01", "Sravana Karnati", "EVP, Global Technology Platforms", "walmart_primary", "capability_claim", "agent_platform",
  ["product"], ["walmart_team"], ["CAP-07", "CAP-26"], "medium",
  "Karnati describes the platform for agents: stateful memory, agent-aware pipelines, tool calling, standardized communication protocols between agents, API orchestration and governance balancing agency and control.")
R("ST-127", "https://www.itbrew.com/stories/2025/12/04/inside-walmart-s-ai-strategy", "2025-12-04", "Sravana Karnati", "EVP, Global Technology Platforms (via IT Brew)", "press", "desire", "agent_evals",
  ["trust_safety", "product", "partnerships"], ["agent_builder"], ["CAP-26"], "high",
  "Karnati said there needs to be a way to verify an agent is doing what it is doing and nothing more, and that an evaluation framework is part of that. This is the conformance-suite need in Walmart's words.",
  "the agent is actually doing what it's doing, and nothing more")
R("ST-128", "https://www.eweek.com/news/walmart-ai-super-agents/", "2025-07-25", "Suresh Kumar", "Global CTO & CDO (to WSJ, via eWeek)", "press", "problem", "agent_sprawl",
  ["product"], ["walmart_team"], ["CAP-07"], "medium",
  "Kumar said early agents predated widespread MCP and Walmart is retrofitting older agents to the standard; multiple separate agents had become confusing, hence four super agents.",
  "making sure older agents conform with the standard")
