# Batch 7: daily sweep, Nov 19 2026 (Fork E). Agent Profiles timing, Visa acceptance programme, Amazon ads in agent replies.
from registry import R

R("ST-193", "https://finance.yahoo.com/technology/ai/articles/walmart-ceo-launching-ai-agent-194059829.html", "2026-11-16",
  "John Furner", "President & CEO (Masters of Scale Rapid Response, Nov 12; via TIKR on Yahoo Finance)", "press",
  "capability_claim", "agent_profiles_timing",
  ["product", "trust_safety"], ["shopper", "agent_builder", "caregiver"], ["CAP-02"], "medium",
  "On a Nov 12 podcast Furner said Walmart is launching Agent Profiles over the next few weeks, later than the Oct 21 'within a month'; the article says Walmart has not said which integrations support profiles at launch. Not confirmed live as of Nov 19. The podcast page itself did not load for us.",
  "over the next few weeks", as_of="2026-11-19")
R("ST-194", "https://usa.visa.com/about-visa/newsroom/press-releases.releaseId.22986.html", "2026-11-17",
  "Rubail Birwadker", "SVP, Growth Products & Partnerships, Visa (press release)", "partner",
  "capability_claim", "agentic_acceptance",
  ["partnerships", "finance", "trust_safety"], ["agent_builder"], ["CAP-40"], "high",
  "Visa extended its Agentic Ready programme (part of Visa Intelligent Commerce) to the acceptance side: 140+ PSPs, acquirers and enablers (e.g. Adyen, Stripe, PayPal, Checkout.com, Fiserv, Worldline) testing agent-initiated transactions, on top of 175+ issuers in 45 markets; Airwallex embeds Trusted Agent Protocol. No retailer is named; UCP and AP2 are not mentioned.",
  "Agentic Ready brings the ecosystem together to test real-world transactions", as_of="2026-11-19")
R("ST-195", "https://digiday.com/media-buying/amazons-shopping-agent-now-takes-orders-by-text-with-sponsored-product-ads-in-the-replies/", "2026-11-06",
  "Digiday (Krystal Scanlon); Rajiv Mehta, VP Conversational Shopping, Amazon", "press", "press",
  "capability_claim", "sponsored_in_agent",
  ["connect_ads", "product"], ["shopper", "supplier_brand"], ["CAP-34"], "medium",
  "Amazon's Alexa for Shopping now takes orders by text (invite-only, wider rollout over coming weeks), with opt-in auto-buy at a price target. Sponsored Products ads appear in the options it texts back at discovery, free to advertisers for now; purchases the agent completes on its own stay ad-free. No label wording is described. A competitor answer to how sponsored items show up in an agent channel.",
  as_of="2026-11-19")
