# Batch 4: pricing pledge, Gemini release, Danker ICR/CES, patents, drones/InHome, benchmarks, analysts, agent builders, Sam's, Instacart.
from registry import R

LETTER = "https://corporate.walmart.com/about/everyday-affordability/letter-from-our-ceo"
R("ST-129", LETTER, "2026-09-25", "John Furner", "President & CEO, letter to customers", "walmart_primary", "constraint", "pricing_pledge",
  ["finance", "trust_safety", "marketing_crm"], ["shopper"], ["CON-05", "CAP-04"], "high",
  "Commitment 1: prices will not depend on who the customer is or the time of day; income, shopping history, urgency or perceived willingness to pay will not change the price.",
  "We price the product, not the person.")
R("ST-130", LETTER, "2026-09-25", "John Furner", "President & CEO, letter to customers", "walmart_primary", "constraint", "ranking_honesty",
  ["trust_safety", "connect_ads", "product"], ["shopper", "agent_builder"], ["CON-21", "CON-05"], "high",
  "Commitment 2: shopping tools including Sparky will not use what customers share to raise prices or hide lower-priced options that meet their needs. This bears directly on sponsored placement and on what an agent-facing Sparky may rank.")
R("ST-131", LETTER, "2026-09-25", "John Furner", "President & CEO, letter to customers", "walmart_primary", "constraint", "data_choice",
  ["trust_safety", "marketing_crm"], ["shopper"], ["CON-07", "CAP-31"], "high",
  "Commitment 3: customers decide whether to share more for more personalized help; Walmart will be clear how it uses and protects that information and focus it on serving the customer.")
R("ST-132", "https://www.techspot.com/news/111752-walmart-secures-two-ai-pricing-patents-raising-dynamic.html", "2026-03-20", "Walmart spokesperson (via FT / TechSpot)", "statement", "press", "non_goal", "surge_pricing",
  ["finance", "trust_safety"], ["shopper"], ["CON-05"], "medium",
  "After two ML pricing patents (automated e-commerce markdowns; demand forecasting and price recommendation, US-12572954-B2) drew criticism, Walmart said the markdown patent is unrelated to dynamic pricing and the other supports merchant decisions.",
  "We don't participate in surge pricing")
R("ST-133", "https://www.ufcw.org/press-releases/ufcw-slams-walmarts-decision-to-roll-out-electronic-shelf-labels-chainwide-urges-lawmakers-to-act-quickly/", "2026-03-06", "UFCW", "union statement", "partner", "risk", "surveillance_pricing",
  ["trust_safety", "store_ops"], ["store_associate", "shopper"], ["CON-05"], "medium",
  "UFCW (which does not represent Walmart workers) argues electronic shelf labels enable predatory pricing such as raising prices before a snowstorm and urges lawmakers to ban them; several states have bills and New Jersey imposed a moratorium.")
R("ST-134", "https://corporate.walmart.com/news/2026/01/11/walmart-and-google-turn-ai-discovery-into-effortless-shopping-experiences", "2026-01-11", "Walmart, corporate", "press release", "walmart_primary", "capability_claim", "gemini_experience",
  ["partnerships", "supply_chain", "marketing_crm"], ["ai_platform", "shopper"], ["CAP-32", "CAP-35", "CAP-10"], "high",
  "The Walmart-built Gemini experience uses UCP; linked accounts get complementary recommendations from past online and in-store purchases, merge with the existing cart, and carry membership benefits; local items arrive in under three hours, some in 30 minutes, to the customer's chosen location and time.")
R("ST-135", "https://corporate.walmart.com/news/2026/01/11/walmart-and-google-turn-ai-discovery-into-effortless-shopping-experiences", "2026-01-11", "John Furner", "then CEO Walmart U.S.", "walmart_primary", "goal", "customer_need",
  ["product"], ["shopper"], [], "high",
  "Furner framed the Google work around helping customers get what they need and want, calling agent-led commerce the next great evolution in retail.",
  "We want to help customers get what they need and want")
R("ST-136", "https://www.constellationr.com/blog-news/insights/walmarts-agentic-commerce-vision-practical-personalized-immersive-and-less", "2026-01-13", "Daniel Danker", "EVP AI Acceleration, Product & Design (ICR)", "analyst", "desire", "a2a_with_sparky",
  ["partnerships", "product"], ["ai_platform", "agent_builder"], ["CAP-07"], "high",
  "Asked about disintermediation, Danker pointed to assortment, price and speed, and to having partners' agents work together with Walmart's agent to build a Walmart-powered experience, so Walmart is not invisible on the customer's journey.",
  "having their agents work together with our agent")
R("ST-137", "https://www.constellationr.com/blog-news/insights/walmarts-agentic-commerce-vision-practical-personalized-immersive-and-less", "2026-01-13", "Daniel Danker", "EVP AI Acceleration, Product & Design (ICR)", "analyst", "desire", "household_personalization",
  ["marketing_crm", "product"], ["shopper", "caregiver"], ["CAP-06", "CAP-21"], "medium",
  "Danker said Walmart has barely scratched the surface on personalization; future systems would understand households, behaviors, dietary and health needs and local communities, e.g. reordering detergent before it runs out.",
  "barely scratched the surface on personalization")
R("ST-138", "https://www.wing.vc/content/inside-walmarts-ai-playbook-stores-sparky-and-the-rise-of-agentic-commerce", "2026-01-08", "Daniel Danker", "EVP (CES 2026 session, as reported by Wing VC)", "analyst", "constraint", "data_sharing",
  ["trust_safety", "partnerships"], ["ai_platform"], ["CON-01", "CAP-31"], "medium",
  "Reported from CES: Walmart will not share user data with OpenAI, particularly without consent; Danker described hybrid journeys where one party discovers and another transacts, and said search and agentic will merge into one journey.")
R("ST-139", "https://www.wing.vc/content/inside-walmarts-ai-playbook-stores-sparky-and-the-rise-of-agentic-commerce", "2026-01-08", "Daniel Danker", "EVP (CES 2026, as reported by Wing VC)", "analyst", "capability_claim", "associate_agents",
  ["store_ops"], ["store_associate"], ["CAP-09"], "medium",
  "Associate agents autonomously guide associates to out-of-stocks and floor spills in real time; Walmart spends more time on AI growth than on cost opportunities.")

# --- Patents (signals of intent, not proof of product)
R("ST-140", "https://patentsgazette.uspto.gov/week12/OG/html/1532-4/US12260443-20250325.html", "2025-03-25", "Walmart Apollo, LLC", "US patent 12,260,443", "walmart_primary", "capability_claim", "substitution_rejection",
  ["supply_chain", "merchandising", "care_returns"], ["shopper", "store_associate"], ["CAP-42"], "medium",
  "Granted patent: models the likelihood that a customer will reject a substitution, using add-to-cart, user, transaction and substitution data for a recently added anchor item. Signal that substitution regret is a measured problem.")
R("ST-141", "https://insights.ipauthor.com/18757090.html", "2024-06-27", "Walmart Apollo, LLC", "US application 18/757,090 (non-final OA)", "walmart_primary", "capability_claim", "list_building",
  ["product"], ["shopper"], ["CAP-41"], "low",
  "Application on interactive list building: NLP turns voice, text or camera input into requests that modify a shopping list. Consistent with the shipped lists-to-cart feature; status pending.")
R("ST-142", "https://trademarkdir.com/trademark/trademark-99230516", "2025-06-12", "Walmart Apollo, LLC", "USPTO trademark serial 99230516", "walmart_primary", "capability_claim", "sparky_mark",
  ["product"], [], ["CAP-05"], "low",
  "Trademark filing (first use June 3 2025) covers conversational-interface software that retrieves context-sensitive, user-specific information and converts voice and text into machine-executable commands.")

# --- Fulfillment footprint
R("ST-143", "https://www.retailtouchpoints.com/news/walmart-to-expand-drone-delivery-to-150-more-stores-in-2026-will-fly-coast-to-coast-from-270-sites-by-2027/156369/", "2026-01-11", "Walmart / Wing", "announcement (via Retail TouchPoints)", "press", "capability_claim", "drone",
  ["supply_chain"], ["shopper"], ["CAP-36"], "high",
  "Drone delivery with Wing expands to 150 more stores in 2026 toward 270 sites by 2027 (about 40M people); Wing's top quartile in DFW and Atlanta order three times a week.")
R("ST-144", "https://www.retaildive.com/news/walmart-expands-inhome-delivery-grocery-ecommerce/717781/", "2024-06-06", "Walmart, corporate (via Retail Dive)", "announcement", "press", "capability_claim", "inhome",
  ["supply_chain", "store_ops"], ["shopper", "store_associate"], ["CAP-13"], "medium",
  "InHome reaches 45M households across 50+ markets; vetted associates enter homes with wearable cameras and smart entry; InHome added Replenishment. Note: 2024 figure; not re-verified for 2026.")

# --- Benchmarks and analysts
R("ST-145", "https://investor.visa.com/news/news-details/2026/Visa-Releases-First-of-Its-Kind-Industry-Benchmark-for-AI-Shopping-Almost-Half-of-Test-Runs-Fail/default.aspx", "2026-11-05", "Visa", "press release (Agentic Commerce Benchmark)", "partner", "metric", "agent_reliability",
  ["trust_safety", "partnerships", "product"], ["agent_builder", "ai_platform"], ["CAP-26"], "high",
  "Visa's benchmark ran 22 models from 12 labs through 15 shopping scenarios: 42.8% of runs failed, and in about 54% of failed runs the agent still bought something; models often failed scenarios they had passed before.",
  "models failed 42.8% of test runs")
R("ST-146", "https://rallies.ai/news/walmarts-sparky-delivers-transaction-ready-precision-but-lacks-assortment-breadth", "2026-02-01", "Bernstein (via Rallies)", "analyst test", "analyst", "metric", "native_vs_general",
  ["product", "partnerships"], ["ai_platform"], ["CAP-05", "CAP-07"], "low",
  "Reported Bernstein test of ChatGPT, Gemini, Claude, Alexa and Sparky: none completed unsupervised purchases; retail-native Sparky gave precise, current SKUs and prices within its assortment while general models lacked live catalog and pricing. Secondary report.")
R("ST-147", "https://morganstanley.com/insights/articles/agentic-commerce-market-impact-outlook", "2025-12-08", "Morgan Stanley Research", "analyst", "analyst", "metric", "market_size",
  ["finance"], ["shopper"], [], "high",
  "Morgan Stanley sizes agentic shoppers at $190B (base) to $385B (bull) of U.S. e-commerce by 2030, 10-20% share; about 23% of Americans bought something using AI in the prior month.")
R("ST-148", "https://finance.yahoo.com/news/morgan-stanley-sees-multi-path-093502239.html", "2026-02-01", "Morgan Stanley (via Yahoo Finance)", "analyst", "analyst", "metric", "assistant_usage",
  ["product", "marketing_crm"], ["shopper"], ["CAP-05"], "medium",
  "Retailer-specific assistants (Rufus, Sparky, Target) drew 4-11% monthly usage in Morgan Stanley's survey, far below general assistants; replenishment categories are the fastest-growing agentic opportunities.")
R("ST-149", "https://finance.yahoo.com/news/morgan-stanley-maps-retail-winners-083002967.html", "2026-03-01", "Morgan Stanley (via Investing.com)", "analyst", "analyst", "risk", "margin_risk",
  ["finance", "partnerships"], ["ai_platform"], ["CAP-32"], "medium",
  "Morgan Stanley says Amazon, Walmart and eBay screen favorably for agentic commerce but Amazon, Walmart, Target and eBay face higher margin risk from third-party agentic partnerships.")
R("ST-150", "https://www.chiefmarketer.com/walmart-launches-generative-ai-shopping-chatbot", "2025-06-06", "Sucharita Kodali", "VP & Principal Analyst, Forrester (via Chief Marketer)", "analyst", "risk", "parity_race",
  ["product"], ["shopper"], ["CAP-05"], "medium",
  "Kodali said Sparky was not earth-shattering in its first form but Walmart, as Amazon's only real competitor, must keep releasing comparable features.",
  "I'm not sure it will be earth-shattering")

# --- Agent builders
R("ST-151", "https://www.usecarly.com/blog/best-ai-family-assistants/", "2026-10-15", "Carly (comparison blog)", "agent-builder roundup", "partner", "capability_claim", "family_assistants",
  ["partnerships"], ["agent_builder", "shopper"], ["CAP-01"], "low",
  "Family-assistant roundup: Ollie (SMS) does meal plans with grocery orders through Amazon, Instacart or Walmart; Fambot (Sep 2026) pitches itself as a family chief of staff; Ohai integrates Instacart. Builders already route household grocery work to retailers.")
R("ST-152", "https://www.ohai.ai/blog/ohai-integrates-instacart-ordering", "2025-08-01", "Ohai.ai", "agent builder blog", "partner", "desire", "developer_platform",
  ["partnerships"], ["agent_builder"], ["CAP-26"], "medium",
  "Ohai integrated grocery ordering via Instacart's Developer Platform so its SMS assistant can plan meals and push lists to carts: builders go where a documented developer platform exists.")
R("ST-153", "https://fortune.com/press-releases/domus-next-supernori-family-ai-agent-2026-06-30/", "2026-06-30", "Domus Next", "agent builder press release", "partner", "desire", "proactive_family",
  ["partnerships"], ["agent_builder", "caregiver"], ["CAP-29"], "low",
  "SuperNori pitches a proactive family agent that notices needs (appointments, groceries, meals) and acts after permission: the trigger-plus-consent pattern the Gateway's guardrails anticipate.")
R("ST-154", "https://company.instacart.com/blog/instacarts-ai-assistant-powered-by-14-years-of-grocery-expertise", "2026-06-18", "Instacart", "company blog", "press", "capability_claim", "competitor_grocery_agent",
  ["product"], ["shopper"], [], "medium",
  "Instacart's assistant builds carts from conversation, prompts or a photo of a list using live inventory from about 100,000 stores; orders through it are larger than the $113 average; Clementine (Sep 2026) adds 'my usuals' and connects to ChatGPT, Claude and Gemini.")
R("ST-155", "https://www.paz.ai/blog/instacarts-chatgpt-launch-how-acp-powers-the-first-embedded-grocery-checkout", "2025-12-10", "Nick Turley", "VP & Head of ChatGPT, OpenAI (via paz.ai)", "partner", "desire", "meal_to_checkout",
  ["partnerships"], ["ai_platform"], [], "medium",
  "OpenAI's Turley described Instacart in ChatGPT as going from meal planning to checkout in one conversation: platform partners want completion, not just discovery.",
  "from meal planning to checkout in a single, seamless conversation")
R("ST-156", "https://letsdatascience.com/news/amazon-blocks-meta-muse-as-shopify-enables-checkout-85276e25", "2026-09-22", "Let's Data Science (news)", "press", "press", "constraint", "permission_matters",
  ["partnerships", "trust_safety"], ["agent_builder"], ["CON-04", "CON-16"], "medium",
  "Coverage of Amazon's Muse block notes that a consumer's instruction to an agent does not settle whether a retailer permits automated browsing or checkout; identity, authorization and credential isolation are operating constraints for builders.")

# --- Sam's Club and misc Walmart
R("ST-157", "https://p2pi.com/sams-club-doubles-down-omnichannel-experience-attract-younger-shoppers", "2025-04-09", "Chris Nicholas", "President & CEO, Sam's Club", "press", "metric", "sams_frictionless",
  ["b2b", "store_ops"], ["shopper", "small_business"], ["CAP-17"], "medium",
  "Nicholas said AI removed 100 million tasks from clubs in a year; Scan & Go members are twice as likely to shop online and digitally engaged members spend three times more; Just Go exit arches are used by most members.",
  "We've taken 100 million tasks out of the club")
R("ST-158", "https://www.digitalcommerce360.com/2026/10/23/walmart-unveils-ai-agent-shopping-controls-spending-limits/", "2026-10-23", "Manish Joneja", "SVP, Walmart Marketplace (via Digital Commerce 360)", "press", "desire", "seller_opportunity",
  ["marketplace"], ["marketplace_seller"], ["CAP-20"], "high",
  "Joneja said agentic commerce could create more chances for sellers to put the right products in front of the right customers, including brands without broad awareness.",
  "brands and products that may not have broad awareness")
R("ST-159", "https://www.retailbrew.com/stories/2025/12/01/can-john-furner-lead-walmart-through-its-ai-era", "2025-12-01", "John Furner", "then incoming CEO (Q3 FY26 call, via Retail Brew)", "press", "desire", "digital_agent",
  ["product"], ["shopper"], ["CAP-01"], "medium",
  "Furner said having a digital agent working for you is going to be really powerful; agentic AI also maintains catalog accuracy and finds assortment gaps.",
  "Having a digital agent that is there working for you")
R("ST-160", "https://www.digitalcommerce360.com/2025/11/21/walmart-online-sales-q3-fy26/", "2025-11-20", "John Furner", "then CEO Walmart U.S. (Q3 FY26 call)", "press", "goal", "reorder_nudges",
  ["marketing_crm", "merchandising"], ["shopper"], ["CAP-06"], "medium",
  "Furner said agentic AI helps customers keep track of products they may want to reorder and keep on hand, and helps keep the catalog accurate and find gaps in assortment.")
R("ST-161", "https://www.shopifreaks.com/walmart-makes-a-second-attempt-at-shopping-with-openai-with-the-launch-of-a-chatgpt-app/", "2026-03-23", "Shopifreaks", "press", "press", "capability_claim", "sparky_login",
  ["product", "trust_safety"], ["ai_platform", "shopper"], ["CAP-32", "CAP-02"], "medium",
  "In the ChatGPT app users log into Sparky the first time; carts sync across ChatGPT, Walmart.com and the app. Account linking, not anonymous API calls, is Walmart's chosen pattern for third-party surfaces.")
R("ST-162", "https://www.eesel.ai/es/blog/walmart-agent-gateway-que-es-y-como-funciona", "2026-10-28", "eesel.ai", "explainer (secondary)", "press", "capability_claim", "marketplace_mcp",
  ["marketplace", "partnerships"], ["marketplace_seller", "agent_builder"], ["CAP-33"], "low",
  "Secondary explainer says Walmart separately runs a Marketplace MCP server at developer.walmart.com/mcp (from Oct 14 2026) that gives coding assistants seller API docs; not to be confused with the Gateway. Unverified: the page did not load for us.")
R("ST-163", "https://marketrealist.com/how-is-walmart-enhancing-shopper-experience-with-ai-ads", "2026-02-01", "Khurrum Malik", "VP, Walmart Connect (via Market Realist)", "press", "desire", "sparky_ads_test",
  ["connect_ads"], ["supplier_brand"], ["CAP-34"], "medium",
  "On ads in Sparky, Malik said Walmart wants to be there and experiment in the new surface even though it is early days.",
  "we want to be there and experiment in that new surface")
R("ST-164", "https://www.pymnts.com/walmart/2026/walmart-rolls-out-agentic-advertiser-assistant/", "2026-01-09", "Walmart Connect (via PYMNTS)", "announcement", "press", "capability_claim", "sparky_ad_formats",
  ["connect_ads"], ["supplier_brand"], ["CAP-34"], "medium",
  "Walmart Connect said it will keep testing ad formats inside Sparky, citing the potential for AI-first shopping to change how customers search and discover.")
R("ST-165", "https://www.supermarketnews.com/grocery-technology/walmart-enlists-artificial-intelligence-for-online-grocery-substitutions", "2021-01-01", "Srini Venkatesan", "then EVP, Walmart U.S. Omni Tech (via Supermarket News)", "press", "problem", "substitutions",
  ["supply_chain", "care_returns"], ["shopper", "store_associate"], ["CAP-42"], "medium",
  "Walmart said substitution decisions are complex and highly personal; a wrong choice hurts satisfaction and raises cost, which is why it built AI substitution logic for personal shoppers. Older source; problem still current per the 2025 patent.",
  "complex and highly personal to each customer")
