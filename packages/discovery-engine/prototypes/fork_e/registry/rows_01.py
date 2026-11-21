# Registry rows, batch 1: Oct 21 2026 agent launch, Agentic Access Terms, beta page, Danker/Furner, earnings.
# R(id, url, published, speaker, role, source_type, kind, theme, functions, actors, org_rows, confidence, paraphrase, short_quote=None)
from registry import R

NEWS_OCT21 = "https://corporate.walmart.com/news/2026/10/Making-It-Possible-for-Agents-to-Shop-on-Behalf-of-Customers"
TERMS = "https://www.walmart.com/help/article/walmart-agentic-access-terms/d048fc229d7549738d7c05a4317e24d7"
BETA = "https://www.walmart.com/agents"
TC = "https://techcrunch.com/2026/10/21/while-amazon-blocks-ai-agents-walmart-rolls-out-the-welcome-mat/"
MS_TMT = "https://corporate.walmart.com/content/dam/corporate/documents/newsroom/events/2026-morgan-stanley-technology-media-telecom-conference/Walmart_MorganStanley_TMT_Conference_2026_Transcript.pdf"
TECHPAGE = "https://corporate.walmart.com/about/technology"

R("ST-001", NEWS_OCT21, "2026-10-21", "Walmart, corporate", "newsroom", "walmart_primary", "capability_claim", "agent_access",
  ["product", "partnerships"], ["shopper", "agent_builder"], ["CAP-01", "CAP-02", "CON-02"], "high",
  "Walmart announced three linked pieces for outside AI agents: Agent Profiles, the Walmart Agent Gateway and terms for AI agents, covering Walmart and Sam's Club.")
R("ST-002", NEWS_OCT21, "2026-10-21", "Walmart, corporate", "newsroom", "walmart_primary", "problem", "agent_access",
  ["product"], ["agent_builder", "shopper"], ["CAP-01"], "high",
  "Walmart says agents today shop its site through a browser following steps designed for people, which it calls slow and error-prone; the Gateway is the fix.",
  "slow and error-prone")
R("ST-003", NEWS_OCT21, "2026-10-21", "Walmart, corporate", "newsroom", "walmart_primary", "problem", "agent_identity",
  ["trust_safety", "product", "care_returns"], ["shopper"], ["CAP-02"], "high",
  "Today an agent signs in with the customer's own account, so agent and customer purchases are mixed together; Agent Profiles exist to separate them.")
R("ST-004", NEWS_OCT21, "2026-10-21", "Walmart, corporate", "newsroom", "walmart_primary", "goal", "trust",
  ["marketing_crm", "trust_safety"], ["shopper"], ["CAP-02"], "high",
  "Walmart says agent shopping won't be for everyone; its goal is to make its experience the most trusted for customers who choose it.",
  "make our experience the most trusted")
R("ST-005", NEWS_OCT21, "2026-10-21", "Walmart, corporate", "newsroom", "walmart_primary", "capability_claim", "agent_identity",
  ["product", "trust_safety"], ["shopper", "caregiver"], ["CAP-02"], "high",
  "Agent Profiles launch within a month: each authorized agent gets its own profile; customers approve every purchase or set a spending limit (examples $50, $100, $200); likened to an authorized user on a credit card; deletable any time.")
R("ST-006", NEWS_OCT21, "2026-10-21", "Walmart, corporate", "newsroom", "walmart_primary", "capability_claim", "agent_identity",
  ["product"], ["shopper", "agent_builder"], ["CAP-02", "CAP-01"], "high",
  "A profile is created automatically the first time a customer shops through the Gateway from the agent's app; the customer connects by signing in to Walmart.",
  "Only Walmart sees this.")
R("ST-007", NEWS_OCT21, "2026-10-21", "Walmart, corporate", "newsroom", "walmart_primary", "capability_claim", "usuals_privacy",
  ["product", "trust_safety", "marketing_crm"], ["shopper", "agent_builder"], ["CAP-31"], "high",
  "Walmart will help agents find a customer's usual items (its examples: sourdough bread, a particular milk brand) without sharing the customer's broader shopping history or personal information.")
R("ST-008", NEWS_OCT21, "2026-10-21", "Walmart, corporate", "newsroom", "walmart_primary", "constraint", "pricing",
  ["finance", "trust_safety", "marketing_crm"], ["shopper", "agent_builder"], ["CAP-04", "CON-05"], "high",
  "Every Day Low Price is unchanged for agent shoppers: agents see the same prices a person sees on Walmart.com, with offers and fees shown before purchase.",
  "We price products, not people")
R("ST-009", NEWS_OCT21, "2026-10-21", "Walmart, corporate", "newsroom", "walmart_primary", "constraint", "consent",
  ["trust_safety", "product"], ["shopper", "agent_builder"], ["CAP-03", "CON-15"], "high",
  "Customers must approve agent purchases by default, and Walmart may require extra approval even for purchases within an agent's spending limit.",
  "Customers must approve agent purchases by default")
R("ST-010", NEWS_OCT21, "2026-10-21", "Walmart, corporate", "newsroom", "walmart_primary", "constraint", "returns",
  ["care_returns", "trust_safety"], ["shopper"], ["CAP-18"], "high",
  "Walmart's returns process applies to agent orders, including when an agent does not act as the customer intended.")
R("ST-011", NEWS_OCT21, "2026-10-21", "Walmart, corporate", "newsroom", "walmart_primary", "constraint", "enforcement",
  ["trust_safety", "partnerships"], ["agent_builder"], ["CON-02", "CON-18"], "high",
  "Agents may not act beyond the shopper's intent, never receive card data or change payment methods, see only information needed and allowed; non-compliant agents are blocked.",
  "Agents that do not follow these terms will be blocked")
R("ST-012", NEWS_OCT21, "2026-10-21", "Walmart, corporate", "newsroom", "walmart_primary", "capability_claim", "ecosystem",
  ["partnerships"], ["ai_platform"], ["CAP-32"], "high",
  "Walmart lists its existing agent-era channels as stores, clubs, online, pickup and delivery, Sparky, and integrations with Muse, ChatGPT, Gemini and others.")
R("ST-013", TERMS, "2026-10-21", "Walmart, corporate", "Agentic Access Terms, Addendum 1", "walmart_primary", "capability_claim", "a2a_sparky",
  ["product", "partnerships"], ["agent_builder"], ["CAP-07", "CAP-01"], "high",
  "Addendum 1 defines the Walmart Agent Gateway as an MCP or similar protocol for agent-to-agent shopping with Walmart's agent, Sparky. This is the published basis for CAP-07.",
  "agent-to-agent shopping with Walmart's agent, Sparky")
R("ST-014", TERMS, "2026-10-21", "Walmart, corporate", "Agentic Access Terms", "walmart_primary", "constraint", "data_use",
  ["trust_safety", "partnerships", "connect_ads"], ["agent_builder"], ["CON-01"], "high",
  "Data obtained through agents may not be used to generate content, target advertising, create synthetic data, train models, or produce commercial analytics; this extends to deployers' product improvement.")
R("ST-015", TERMS, "2026-10-21", "Walmart, corporate", "Agentic Access Terms", "walmart_primary", "constraint", "consent",
  ["trust_safety", "product"], ["agent_builder", "shopper"], ["CON-15", "CAP-03"], "high",
  "Outside the Gateway Walmart requires a Human Consent Gate before every checkout; agents may not check out autonomously unless they meet Gateway requirements; deployer configuration cannot waive a gate.",
  "Agents may not check out autonomously unless they comply")
R("ST-016", TERMS, "2026-10-21", "Walmart, corporate", "Agentic Access Terms, Addendum 1 s.5", "walmart_primary", "capability_claim", "autonomy",
  ["product", "trust_safety"], ["agent_builder", "shopper", "caregiver"], ["CAP-29", "CAP-30"], "high",
  "Through the Gateway Walmart may allow autonomous checkout without a separate gate if the Agent Mandate stays within the User-Defined Guardrail; it may still gate a transaction it judges misaligned with intent.")
R("ST-017", TERMS, "2026-10-21", "Walmart, corporate", "Agentic Access Terms, Addendum 1 s.4", "walmart_primary", "capability_claim", "tokens",
  ["product", "trust_safety"], ["agent_builder"], ["CAP-03"], "high",
  "Each Gateway session needs a separate Scoped Access Token bound to merchant, cart, amount and session, short-lived, consumed at checkout; no reuse, replay or transfer.",
  "a separate Scoped Access Token")
R("ST-018", TERMS, "2026-10-21", "Walmart, corporate", "Agentic Access Terms, Addendum 1", "walmart_primary", "capability_claim", "guardrails",
  ["product", "trust_safety", "b2b"], ["shopper", "caregiver", "agent_builder"], ["CAP-29", "CAP-21"], "high",
  "A User-Defined Guardrail is a standing customer limit set in Account Settings or with Walmart; it may include spend limits, transaction frequency and category or department restrictions.")
R("ST-019", TERMS, "2026-10-21", "Walmart, corporate", "Agentic Access Terms, Addendum 1 s.6", "walmart_primary", "capability_claim", "mandate_audit",
  ["trust_safety", "care_returns"], ["agent_builder"], ["CAP-30", "CAP-25"], "high",
  "Hashes, signed mandates and consent records must be sent to Walmart and become part of an immutable transaction record; the Agent Mandate is a signed record of the customer's instructions and consent.")
R("ST-020", TERMS, "2026-10-21", "Walmart, corporate", "Agentic Access Terms", "walmart_primary", "constraint", "identity",
  ["trust_safety"], ["agent_builder"], ["CON-02", "CON-16"], "high",
  "Agents must identify themselves when asked (deployer, product, contact), must not mask origin, mimic human timing or evade human-detection checks, and must answer honestly if asked whether they are automated.")
R("ST-021", TERMS, "2026-10-21", "Walmart, corporate", "Agentic Access Terms", "walmart_primary", "constraint", "accuracy",
  ["trust_safety", "merchandising"], ["agent_builder"], ["CON-03", "CON-06"], "high",
  "Agents must honor customer-set brand, price-ceiling and category constraints, label substitutes and recommendations, and not misstate prices, fees or discounts or present stale data as current. The terms do not address sponsored-item labeling.")
R("ST-022", TERMS, "2026-10-21", "Walmart, corporate", "Agentic Access Terms", "walmart_primary", "constraint", "fulfillment",
  ["supply_chain", "trust_safety"], ["agent_builder"], ["CAP-10", "CON-19"], "high",
  "Agents must not misrepresent availability, delivery speed or fulfillment options; Walmart is not liable for an agent's delivery choices; fulfillment data is Walmart Proprietary Data. No slots or delivery windows are named.",
  "misrepresent availability, delivery speed, or fulfillment options")
R("ST-023", TERMS, "2026-10-21", "Walmart, corporate", "Agentic Access Terms", "walmart_primary", "risk", "liability",
  ["trust_safety", "partnerships", "finance"], ["agent_builder"], ["CON-17"], "high",
  "Walmart may throttle, suspend or permanently block agents, may hold deployers directly responsible for unauthorized transactions or ignored consent gates, and caps its own aggregate liability at $50.")
R("ST-024", TERMS, "2026-10-21", "Walmart, corporate", "Agentic Access Terms", "walmart_primary", "constraint", "terms_versioning",
  ["partnerships", "trust_safety"], ["agent_builder"], ["CON-18"], "medium",
  "Walmart may change the terms at any time and an agent must retrieve the current version before starting a session; Walmart may log authorization events such as timestamp, device and consent version.")
R("ST-025", BETA, "2026-10-21", "Walmart, corporate", "Agent Gateway beta page", "walmart_primary", "capability_claim", "a2a_sparky",
  ["product", "partnerships"], ["agent_builder"], ["CAP-07", "CAP-01"], "high",
  "The beta page says the Gateway connects AI agents through Sparky for shopping, and promises agents data directly rather than by scraping.",
  "connects AI agents through Sparky")
R("ST-026", BETA, "2026-10-21", "Walmart, corporate", "Agent Gateway beta page FAQ", "walmart_primary", "capability_claim", "gateway_scope",
  ["product", "supply_chain", "b2b"], ["agent_builder", "small_business"], ["CAP-10", "CAP-31", "CAP-17"], "medium",
  "The FAQ lists finding and shopping usual items, searching and selecting products, managing purchases, checking availability and stock, monitoring order status and bulk orders. It does not name slot selection or cart management.")
R("ST-027", BETA, "2026-10-21", "Walmart, corporate", "Agent Gateway beta page", "walmart_primary", "capability_claim", "safeguards",
  ["trust_safety"], ["agent_builder"], ["CAP-29", "CAP-02"], "medium",
  "Safeguards named: verified identities, controlled permissions and observable actions, plus category restrictions, rate limits and compliance guardrails.",
  "verified identities, controlled permissions & observable actions")
R("ST-028", BETA, "2026-10-21", "Walmart, corporate", "Agent Gateway beta page", "walmart_primary", "constraint", "beta_access",
  ["partnerships"], ["agent_builder"], ["CAP-01", "CAP-26"], "high",
  "The Gateway is an early, invitation-only beta; access is limited and may be suspended at any time; features may change and may not be available to all participants. No sandbox or public API reference is published.",
  "available by invitation only, and may be suspended")
R("ST-029", TC, "2026-10-21", "TechCrunch (Sarah Perez)", "press", "press", "capability_claim", "ecosystem",
  ["partnerships"], ["shopper"], ["CAP-01", "CAP-02"], "high",
  "TechCrunch reports CEO John Furner discussed the launch at Masters of Scale (Oct 21) as preparation for agents going mainstream, and that agent support needs no Walmart+ membership; Amazon had begun blocking agents.")
R("ST-030", MS_TMT, "2026-03-04", "Daniel Danker", "EVP AI Acceleration, Product & Design", "walmart_primary", "non_goal", "agentic_definition",
  ["product", "marketing_crm"], ["shopper"], ["COV-01"], "high",
  "Danker rejects the idea that agentic commerce means fully automatic shopping; he would call that robotic commerce and says he does not see that future at all.",
  "I don't see that future at all.")
R("ST-031", MS_TMT, "2026-03-04", "Daniel Danker", "EVP AI Acceleration, Product & Design", "walmart_primary", "desire", "chores",
  ["product", "marketing_crm", "supply_chain"], ["shopper"], ["CAP-06"], "high",
  "He frames automation as for routine purchases he calls chores, and wants to make them stop feeling like chores, while adding more personalized product discovery.",
  "Those are the things that I call the chores.")
R("ST-032", MS_TMT, "2026-03-04", "Daniel Danker", "EVP AI Acceleration, Product & Design", "walmart_primary", "goal", "growth",
  ["finance", "product"], ["shopper"], [], "high",
  "Danker says growth, not efficiency, is the more interesting vector for agentic commerce, while still serving the best prices possible.",
  "growth is much more interesting as a vector here")
R("ST-033", MS_TMT, "2026-03-04", "Daniel Danker", "EVP AI Acceleration, Product & Design", "walmart_primary", "desire", "intermediation",
  ["partnerships", "product"], ["ai_platform"], ["CAP-32"], "high",
  "He says the Sparky experience will travel into ChatGPT and Gemini, calls native in-chat checkout a temporary moment, and recasts third-party LLMs as intermediation rather than disintermediation.",
  "I would argue it's intermediation")
R("ST-034", MS_TMT, "2026-03-04", "Daniel Danker", "EVP AI Acceleration, Product & Design", "walmart_primary", "capability_claim", "why_walmart",
  ["merchandising", "supply_chain", "trust_safety"], ["ai_platform", "shopper"], ["CAP-04", "CAP-35"], "high",
  "Why an LLM should pick Walmart: half a billion items across stores and marketplace, price, speed and trust.",
  "I think we win on our merits.")
R("ST-035", MS_TMT, "2026-03-04", "Daniel Danker", "EVP AI Acceleration, Product & Design", "walmart_primary", "metric", "ads_model",
  ["connect_ads", "finance"], ["supplier_brand"], ["CAP-34"], "high",
  "On ads in agents: Walmart gets paid when it generates sales, advertisers pay for conversion, and Walmart keeps the same role in ranking inside Sparky.",
  "the advertiser pays us for conversion")
R("ST-036", MS_TMT, "2026-03-04", "Daniel Danker", "EVP AI Acceleration, Product & Design", "walmart_primary", "risk", "adoption",
  ["product", "marketing_crm"], ["shopper"], [], "medium",
  "Customers need to be taken on a journey to adopt new technology; he wants everything built to work well before scaling, and says of robotic agents that Walmart needs to learn.",
  "Customers need to be taken on a journey")
R("ST-037", MS_TMT, "2026-03-04", "Daniel Danker", "EVP AI Acceleration, Product & Design", "walmart_primary", "metric", "search_box",
  ["product", "merchandising"], ["shopper"], ["COV-01"], "medium",
  "The search box still drives the vast majority of cart adds; Sparky lives at the bottom of the app; top ChatGPT purchases were vitamin and protein supplements.")
R("ST-038", TECHPAGE, "2026-11-19", "Walmart, corporate", "technology page", "walmart_primary", "goal", "multi_agent_ecosystem",
  ["product", "partnerships"], ["shopper", "agent_builder"], ["CAP-05", "CAP-37"], "medium",
  "Walmart describes its goal as a customer-first multi-agent ecosystem where retailers keep control of their experiences, with AI as a trusted layer connecting inspiration to fulfillment.",
  "customer-first, multi-agent ecosystem")
R("ST-039", TECHPAGE, "2026-11-19", "Walmart, corporate", "technology page", "walmart_primary", "capability_claim", "supply_chain_agents",
  ["supply_chain", "store_ops"], ["store_associate"], ["CAP-37", "CAP-09"], "medium",
  "An Agentic End-to-End Workflow decides where inventory lives and coordinates delivery; associate tools embed agents for routine tasks; customer-support agents increasingly resolve tasks end to end.")
