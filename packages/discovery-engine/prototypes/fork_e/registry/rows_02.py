# Batch 2: earnings/10-K/investor, OpenAI/Google/ChatGPT pivot, Connect, Marty, Scintilla, jobs, event page.
from registry import R

R("ST-040", "https://www.nasdaq.com/articles/walmart-q2-earnings-call-highlights", "2026-08-20", "John Furner", "President & CEO (via MarketBeat)", "press", "metric", "sparky_metrics",
  ["product", "finance", "marketing_crm"], ["shopper"], ["CAP-05"], "medium",
  "On the Q2 FY27 call Furner said Sparky usage rose 70% year over year and customers who use it spend about 40% more per order.")
R("ST-041", "https://www.nasdaq.com/articles/walmart-q2-earnings-call-highlights", "2026-08-20", "John David Rainey / John Furner", "CFO / CEO (via MarketBeat)", "press", "metric", "growth_engines",
  ["finance", "marketplace", "connect_ads", "supply_chain"], ["marketplace_seller", "supplier_brand"], ["CAP-35"], "medium",
  "Q2 FY27: global e-commerce +23%, U.S. Marketplace +52%, global ads +38% (Walmart Connect +43%), membership income ~+17%; nearly half of Marketplace volume via Walmart Fulfillment Services; sub-30-minute delivery in 38 U.S. markets; Walmart+ members spend ~4x non-members.")
R("ST-042", "https://www.nasdaq.com/articles/walmart-q2-earnings-call-highlights", "2026-08-20", "John David Rainey", "EVP & CFO", "press", "goal", "price_investment",
  ["finance", "merchandising"], ["shopper"], ["CAP-04"], "medium",
  "Rainey said Walmart is investing tariff refunds into price for cumulative share gains on a multiyear view; rollbacks rose above 11,000; fuel over $4 pressured customers into more trade-offs.",
  "We are not managing our business for one quarter")
R("ST-043", "https://admiralmarkets.com/analytics/traders-blog/walmart-earnings-preview-q3-fiscal-2027", "2026-11-18", "Admiral Markets", "analyst preview", "analyst", "metric", "calendar",
  ["finance"], [], [], "high",
  "Walmart reports Q3 FY27 on Thursday Nov 19 2026 before the open, call at 7am CST hosted by Furner and Rainey. Not yet reviewed in this registry; flagged for the daily sweep.")
R("ST-044", "https://stock.walmart.com/sec-filings/all-sec-filings/content/0000104169-26-000091/0000104169-26-000091.pdf", "2026-03-31", "Walmart, corporate", "Form 10-K FY2026, Risk Factors", "walmart_primary", "risk", "agentic_competition",
  ["finance", "product", "partnerships"], ["ai_platform"], ["CAP-01", "CAP-32"], "high",
  "The 10-K says customers use emerging agentic platforms to shop with Walmart and competitors, and that AI-enabled platforms for search, discovery, advertising and purchasing could reduce store traffic.",
  "emerging agentic platforms to shop with us and our competitors")
R("ST-045", "https://stock.walmart.com/sec-filings/all-sec-filings/content/0000104169-26-000091/0000104169-26-000091.pdf", "2026-03-31", "Walmart, corporate", "Form 10-K FY2026, Risk Factors", "walmart_primary", "risk", "ai_quality",
  ["trust_safety", "product"], ["shopper"], ["CON-09"], "high",
  "Risk factors name ineffective use or misuse of AI and search results that are inaccurate, biased or otherwise flawed, plus elevated government scrutiny and a conflicting AI regulatory environment.",
  "inaccurate, biased or otherwise flawed")
R("ST-046", "https://stock.walmart.com/sec-filings/all-sec-filings/content/0000104169-26-000091/0000104169-26-000091.pdf", "2026-03-31", "Walmart, corporate", "Form 10-K FY2026, Risk Factors", "walmart_primary", "risk", "competitor_speed",
  ["product", "finance"], [], [], "high",
  "Competitors' faster development of AI and agentic tools could raise competitive pressure; newer or smaller businesses may innovate faster in e-commerce; scaling AI search and discovery is necessary to compete.",
  "more rapid development of AI capabilities and agentic tools")
R("ST-047", "https://stock.walmart.com/sec-filings/all-sec-filings/content/0000104169-26-000091/0000104169-26-000091.pdf", "2026-03-31", "Walmart, corporate", "Form 10-K FY2026, Risk Factors", "walmart_primary", "risk", "ai_security",
  ["trust_safety"], ["shopper", "agent_builder"], ["CON-02", "CON-16"], "high",
  "AI has intensified cybersecurity risk: AI-driven attacks can run reconnaissance autonomously and craft convincing social-engineering content; identity-fraud risk rises; AI or data incidents could quickly erode trust.",
  "could quickly erode trust and confidence in our business")
R("ST-048", "https://stock.walmart.com/sec-filings/all-sec-filings/content/0000104169-26-000091/0000104169-26-000091.pdf", "2026-03-31", "Walmart, corporate", "Form 10-K FY2026, Business", "walmart_primary", "goal", "workforce",
  ["store_ops"], ["store_associate"], ["CAP-09"], "high",
  "Walmart says it is developing a digitally skilled, AI-enabled workforce, reshaping roles toward human strengths and automating repetitive tasks, with company-wide AI learning pathways and certifications.")
R("ST-049", "https://stock.walmart.com/sec-filings/all-sec-filings/content/0000104169-26-000091/0000104169-26-000091.pdf", "2026-03-31", "Walmart, corporate", "Form 10-K FY2026, Business", "walmart_primary", "capability_claim", "fulfillment_footprint",
  ["supply_chain"], ["shopper"], ["CAP-10", "CAP-35"], "high",
  "Substantially all Walmart U.S. stores offer same-day pickup and delivery; Sam's Club offers curbside pickup and delivery; the U.S. network has 192 distribution facilities. Says nothing about agent access to slots.")
R("ST-050", "https://stock.walmart.com/_assets/_5bb4b0137bcb7c329b4b74e982c643dd/walmart/db/950/9988/annual_report/Walmart+2026+Annual+Report.pdf", "2026-03-31", "John Furner", "President & CEO, annual report letter", "walmart_primary", "goal", "ai_era",
  ["finance", "product"], ["shopper", "store_associate"], [], "high",
  "Furner's letter calls this a pivotal moment as AI reshapes how customers shop and associates work; FY26 e-commerce sales $150.4B, advertising +46%, membership fee revenue +15.5%.",
  "artificial intelligence fundamentally reshapes how customers shop")
R("ST-051", "https://www.investing.com/news/transcripts/earnings-call-transcript-walmart-q4-2026-beats-eps-forecast-stock-rises-93CH-4513893", "2026-02-19", "John Furner", "President & CEO (Q4 FY26 call)", "press", "goal", "agentic_commerce",
  ["product", "finance"], ["shopper"], [], "medium",
  "On his first call as CEO Furner said agentic commerce is going to be great for customers; CFO Rainey cited double-digit incremental e-commerce margins; ads $6.4B (+46%).",
  "Agentic Commerce is gonna be great for our customers.")
R("ST-052", "https://www.enca.com/business/walmart-outlines-big-ai-ambitions-it-reports-mixed-results", "2026-02-19", "John Furner", "President & CEO (via AFP)", "press", "goal", "trust",
  ["product", "trust_safety", "supply_chain"], ["shopper"], [], "medium",
  "Furner said Walmart uses technology and AI to reduce friction, simplify decisions and pinpoint inventory while keeping the trust it has earned.",
  "all while maintaining the trust we've earned")
R("ST-053", "https://finance.yahoo.com/markets/stocks/articles/walmart-cfo-says-strategy-intact-000207190.html", "2026-04-08", "John David Rainey", "EVP & CFO (conference, via MarketBeat)", "press", "metric", "sparky_ads_runway",
  ["finance", "connect_ads", "product"], ["shopper", "supplier_brand"], ["CAP-05", "CAP-34"], "medium",
  "Rainey said Sparky engages about half of app users with roughly 35% larger baskets, ads are in the early-to-mid innings, and best-in-class ad spend as a share of GMV is easily twice Walmart's level; Walmart is shaping agentic commerce rather than reacting.")
R("ST-054", "https://www.businesswire.com/news/home/20250409678207/en", "2025-04-09", "Doug McMillon", "then President & CEO, Investment Community Meeting", "walmart_primary", "goal", "customer_wants",
  ["marketing_crm", "merchandising", "finance"], ["shopper"], ["CAP-04"], "high",
  "McMillon said customers want four things: everyday low prices, broad assortment, a convenient and enjoyable experience, and a company they trust. Profits to grow faster than sales via membership, ads, data and fintech. Note: pre-dates the CEO change.")
R("ST-055", "https://secure.businesswire.com/news/home/20251014984151/en/Walmart-Partners-with-OpenAI-to-Create-AI-First-Shopping-Experiences", "2025-10-14", "Doug McMillon", "then President & CEO", "walmart_primary", "goal", "search_bar",
  ["product", "marketing_crm"], ["shopper", "ai_platform"], ["CAP-32"], "high",
  "Announcing Instant Checkout in ChatGPT, McMillon said e-commerce has long been a search bar and a list of results and that is about to change; Walmart framed agentic commerce as shifting from reactive to proactive.",
  "That is about to change")
R("ST-056", "https://secure.businesswire.com/news/home/20251014984151/en/Walmart-Partners-with-OpenAI-to-Create-AI-First-Shopping-Experiences", "2025-10-14", "Walmart, corporate", "press release", "walmart_primary", "metric", "ai_ops_metrics",
  ["care_returns", "merchandising"], ["shopper"], [], "high",
  "Walmart cited AI cutting fashion production timelines by up to 18 weeks and customer-care resolution times by up to 40%.")
R("ST-057", "https://www.axios.com/2026/03/24/ai-shopping-walmart-gap-chatgpt-gemini-checkout", "2026-03-24", "Daniel Danker", "EVP AI Acceleration, Product & Design (to WIRED, via Axios)", "press", "metric", "instant_checkout",
  ["product", "partnerships", "finance"], ["ai_platform"], ["CAP-32"], "high",
  "Danker said conversion for Walmart purchases completed inside ChatGPT was three times lower than for those redirected to Walmart's site, after about 200,000 items were offered via Instant Checkout since November 2025.")
R("ST-058", "https://ppc.land/walmarts-chatgpt-checkout-flopped-heres-what-comes-next/", "2026-03-23", "Daniel Danker", "EVP AI Acceleration, Product & Design (via PPC Land / WIRED)", "press", "capability_claim", "sparky_everywhere",
  ["product", "partnerships"], ["ai_platform", "shopper"], ["CAP-32"], "high",
  "Walmart replaced Instant Checkout with Sparky operating inside ChatGPT (week of Mar 25 2026) and Gemini (the month after): shoppers log in once, baskets sync across ChatGPT, Walmart.com and the app, and checkout runs on Walmart's systems.",
  "make it feel like a natural part of other environments")
R("ST-059", "https://www.searchengineland.com/walmart-chatgpt-checkout-converted-worse-472071", "2026-03-23", "Search Engine Land", "press", "press", "problem", "instant_checkout",
  ["product", "partnerships"], ["ai_platform"], ["CAP-32"], "medium",
  "Press framing: in-chat checkout without Walmart's account, membership and basket context underperformed; Walmart chose an integrated experience inside the assistant over a thin checkout API.")
R("ST-060", "https://www.retaildive.com/news/walmart-ai-shopping-strategy-tinkering-transformation/809556/", "2026-01-13", "Daniel Danker", "EVP AI Acceleration, Product & Design (ICR Conference)", "press", "goal", "pace",
  ["product"], ["shopper"], ["CAP-05"], "high",
  "At ICR Danker said Walmart had been tinkering with AI for a year or two and this is the year tinkering becomes transformation; Sparky already fields service questions and nudges regular orders.",
  "This is the year where tinkering becomes transformation.")
R("ST-061", "https://www.constellationr.com/node/41226", "2026-01-13", "Daniel Danker", "EVP AI Acceleration, Product & Design (ICR, via Constellation)", "analyst", "desire", "practical",
  ["product", "marketing_crm"], ["shopper"], [], "medium",
  "Danker said the customer problems Walmart needs to solve are very practical and the roadmap is built around them; shoppers will do much less scrolling and experiences will feel more human and connected.",
  "We're going to be doing a lot less scrolling.")
R("ST-062", "https://www.axios.com/2026/01/11/walmart-google-gemini-ai-shopping", "2026-01-11", "John Furner", "then incoming CEO (NRF, via Axios)", "press", "goal", "agent_led_commerce",
  ["partnerships", "product"], ["ai_platform"], ["CAP-32"], "high",
  "At NRF 2026 Walmart and Google announced a Walmart-built shopping experience inside Gemini using Google's Universal Commerce Protocol; Furner called agent-led commerce the next great evolution in retail.",
  "the next great evolution in retail")
R("ST-063", "https://www.modernretail.co/technology/walmart-says-open-partnerships-are-central-to-its-ai-strategy-while-amazon-goes-it-alone/", "2026-01-13", "Modern Retail", "press", "press", "capability_claim", "open_partnerships",
  ["partnerships"], ["ai_platform"], ["CAP-32"], "medium",
  "Walmart describes open partnerships as central to its AI strategy; UCP launched with two dozen-plus partners including Shopify, Target and Etsy, with Amazon absent.")
R("ST-064", "https://digiday.com/marketing/inside-walmart-connects-push-to-make-agentic-ai-the-next-battleground-in-retail-media/", "2026-01-09", "Khurrum Malik", "VP Business & Product Marketing, Walmart Connect", "press", "goal", "agentic_ads",
  ["connect_ads"], ["supplier_brand", "marketplace_seller"], ["CAP-34", "CAP-08"], "high",
  "Walmart Connect said it will put ads in Sparky (including sponsored prompts), add gen-AI insights and creative, and run a Marty advertising assistant in beta for Sponsored Search billing and bidding.",
  "delivering real advertiser value at every level")
R("ST-065", "https://digiday.com/marketing/inside-walmart-connects-push-to-make-agentic-ai-the-next-battleground-in-retail-media/", "2026-01-09", "Mike O'Donnell", "SVP Innovation, Flywheel (agency)", "partner", "problem", "ad_visibility",
  ["connect_ads"], ["supplier_brand"], ["CAP-34"], "medium",
  "Agency view: missing new AI ad formats is costly, but limited visibility and immature agentic tools make advertisers hesitant to commit; brands are reluctant to hand agents control of creative.",
  "lack of visibility and limited agentic tools")
R("ST-066", "https://digiday.com/marketing/inside-walmart-connects-push-to-make-agentic-ai-the-next-battleground-in-retail-media/", "2026-01-09", "Mike Feldman", "SVP Commerce, Flywheel (agency)", "partner", "capability_claim", "closed_loop",
  ["connect_ads"], ["supplier_brand"], ["CAP-34"], "medium",
  "Agency credits Walmart's advantage to its scale of first-party retail data and closed-loop measurement.",
  "closed-loop measurement")
R("ST-067", "https://consumergoods.com/walmart-builds-infrastructure-agentic-commerce-implications-brands", "2026-10-22", "Ryan Mayward", "SVP & GM, Walmart Connect U.S. (LinkedIn, via Consumer Goods Technology)", "press", "desire", "intent_relevance",
  ["connect_ads", "marketing_crm"], ["supplier_brand"], ["CAP-34"], "high",
  "Mayward wrote that keywords say what someone searches for while a conversation says what they are trying to accomplish; brands will earn attention by being relevant to the goal.",
  "what they're trying to accomplish")
R("ST-068", "https://consumergoods.com/walmart-builds-infrastructure-agentic-commerce-implications-brands", "2026-10-22", "Rich Lehrfeld", "SVP, Walmart Connect International & Sam's Club Connect (paraphrased)", "press", "desire", "long_tail_discovery",
  ["connect_ads", "marketplace"], ["marketplace_seller", "supplier_brand"], ["CAP-34", "CAP-20"], "medium",
  "Lehrfeld described an agent recommending a traditional Mexican cooking tool from a smaller seller to a shopper who loves cooking, arguing agents can connect advertisers with shoppers who never heard of their brands.")
R("ST-069", "https://consumergoods.com/walmart-builds-infrastructure-agentic-commerce-implications-brands", "2026-11-03", "Consumer Goods Technology", "press analysis", "press", "risk", "ad_measurement",
  ["connect_ads"], ["supplier_brand"], ["CAP-34", "CON-01"], "medium",
  "Open questions for brands: how products surface in agent experiences, how sponsored recommendations work, and how ad influence on agent-initiated purchases is measured; Walmart has not said how the Gateway affects ads or attribution.")
R("ST-070", "https://www.digitalcommerce360.com/2026/01/09/walmart-marty-agent-ai-retail-media-network-advertisers/", "2026-01-09", "Khurrum Malik", "VP, Walmart Connect (via Digital Commerce 360)", "press", "capability_claim", "marty_ads",
  ["connect_ads"], ["supplier_brand", "marketplace_seller"], ["CAP-08"], "medium",
  "The Marty advertising assistant was to reach all Sponsored Search advertisers later in H1 2026; Marty is the partner super agent for advertisers, sellers and suppliers.")
R("ST-071", "https://theshelbyreport.com/2026/09/24/walmart-evolves-scintilla-into-commerce-intelligence-platform/", "2026-09-24", "Walmart Data Ventures", "Inspire 2026 (via The Shelby Report)", "press", "capability_claim", "scintilla",
  ["merchandising", "connect_ads"], ["supplier_brand"], ["CAP-38"], "high",
  "Walmart Data Ventures is turning Scintilla (renamed from Luminate in 2024) into a commerce intelligence platform; 2,000+ suppliers and merchants attended Inspire 2026; Marty for Scintilla helps suppliers understand metrics. Correction to brief: 'Luminate' is now Scintilla.")
R("ST-072", "https://careers.walmart.com/us/en/jobs/R-2573755", "2026-07-17", "Walmart, corporate", "job posting: Sr Distinguished PM, Agentic Commerce", "walmart_primary", "desire", "a2a_platform",
  ["product", "partnerships"], ["agent_builder", "ai_platform"], ["CAP-07", "CAP-10", "CAP-26"], "high",
  "Walmart is hiring to define the core capabilities of an agent-to-agent architecture for discovery, basket building, product questions, cart changes and checkout handoff, with requirements for fulfillment context and post-purchase support.",
  "core capabilities required for an agent-to-agent architecture")
R("ST-073", "https://careers.walmart.com/us/en/jobs/R-2573755", "2026-07-17", "Walmart, corporate", "job posting: Sr Distinguished PM, Agentic Commerce", "walmart_primary", "metric", "partner_metrics",
  ["product", "partnerships"], ["agent_builder", "ai_platform"], ["CAP-26"], "high",
  "Metrics named for external agent experiences: adoption, conversion, failure rates, latency, satisfaction and partner performance; plus reusable playbooks so partner integrations launch faster and more safely.")
R("ST-074", "https://careers.walmart.com/us/en/jobs/R-2573755", "2026-07-17", "Walmart, corporate", "job posting: Sr Distinguished PM, Agentic Commerce", "walmart_primary", "constraint", "guardrails",
  ["product", "trust_safety"], ["agent_builder"], ["CAP-29", "CAP-03"], "high",
  "The role builds guardrails for what assistants may do for customers (cart edits, payment, order management, consent), plus account linking and membership recognition, working with payments, fraud, identity, legal, privacy and security.",
  "governance models for automated or semi-automated customer actions")
R("ST-075", "https://careers.walmart.com/us/en/jobs/R-2532510", "2026-11-19", "Walmart, corporate", "job posting: Principal PM, Supplier One AI", "walmart_primary", "desire", "supplier_a2a",
  ["merchandising", "partnerships"], ["supplier_brand"], ["CAP-08", "CAP-39"], "medium",
  "Walmart is hiring to scale supplier AI and agentic experiences across Supplier One, including agent-to-agent workflows and partner applications, beyond traditional UIs and APIs.",
  "agent-to-agent workflows")
R("ST-076", "https://careers.walmart.com/us/jobs/WD2250702-director-data-science-quality-llm-judging-systems-for-conversational-commerce", "2025-07-22", "Walmart, corporate", "job posting: Director DS, Quality & LLM Judging", "walmart_primary", "desire", "evals",
  ["product", "trust_safety"], ["shopper"], ["CAP-05"], "medium",
  "Walmart hires for evaluation strategy and success metrics for its conversational shopping agent and its tool outputs, combining human-labeled benchmarks, LLM-as-a-judge and automated pipelines.")
R("ST-077", "https://jobs.anitab.org/companies/walmart/jobs/99556141-staff-data-scientist-ai-agent-platform", "2026-11-11", "Walmart, corporate", "job posting: Staff DS, AI Agent Platform", "walmart_primary", "capability_claim", "sparky_orchestrator",
  ["product", "supply_chain"], ["shopper"], ["CAP-05", "CAP-07"], "medium",
  "Posting describes Sparky as an orchestrator over specialized application agents spanning intent-driven discovery, context-aware recommendations, checkout, smart substitutions and end-to-end order tracking.")
R("ST-078", "https://careers.walmart.com/us/en/jobs/R-2350824", "2026-11-19", "Walmart, corporate", "job posting: Distinguished PM, Payments Platform", "walmart_primary", "desire", "agentic_payments",
  ["finance", "trust_safety"], ["agent_builder"], ["CON-02", "CAP-03"], "medium",
  "Walmart's payments platform role covers payment acceptance and intelligence for agentic commerce, with goals of approval rates, routing efficiency and cost-to-serve.")
R("ST-079", "https://dallas-fort-worth.aitinkerers.org/p/ai-tinkerers-x-walmart-dallas-fort-worth-december-demo-night", "2026-11-19", "AI Tinkerers DFW", "event page (Walmart marquee sponsor)", "partner", "desire", "event_prompts",
  ["partnerships", "product"], ["agent_builder"], ["CAP-01", "CAP-29", "CAP-10"], "high",
  "The Dec 2 event page (Walmart keynote, speaker unnamed) suggests builders try: a constrained multi-item cart with budget and substitution policies; logging tool calls and receipts as supervision; a planning agent plus store availability data plus a reviewer workflow.")
R("ST-080", "https://dallas-fort-worth.aitinkerers.org/p/ai-tinkerers-x-walmart-dallas-fort-worth-december-demo-night", "2026-11-19", "AI Tinkerers DFW", "event page", "partner", "capability_claim", "event_competition",
  ["partnerships"], ["agent_builder"], [], "medium",
  "One confirmed demo so far: a fault-injection proxy that catches a payment agent double-charging and fixes it with idempotency (AWS engineer). Signals the room values reliability and backend-state evals.")
