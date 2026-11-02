"""Hand-labelled cases for the requirements agent.

BUDGETS    - (message, (min, max)) for `parse_budget`, the deterministic safety net. Includes look-alikes that are NOT money.
CASES      - one agent turn each: the message, the state it arrives in, and what a correct plan must satisfy.

Case fields
  decision   set of acceptable decisions (the agent may reasonably ask OR search on a vague message, so labels are sets)
  product    any of these words must appear in the product the agent names
  budget_max / budget_min   exact rupee values the plan or profile must carry
  restart    True if the agent must treat this as a new purchase
  skip       True if the shopper asked for results now
  fact       {topic: substring} a fact the plan must record
  attrs      True if a first-time product must come back with a 4-6 attribute question plan
  remember   substring that must appear in a memory the agent proposes (None = must propose nothing about the purchase)
  mode       expected search mode
"""

BUDGETS = [
    ("under ₹5,000", (None, 5000)), ("around 1 lakh", (None, 100000)), ("budget is 80k", (None, 80000)),
    ("between 50k and 80k", (50000, 80000)), ("₹20,000 to ₹30,000", (20000, 30000)), ("max 2.5 lakh", (None, 250000)),
    ("upto Rs 1500", (None, 1500)), ("I can spend 3000 rupees", (None, 3000)), ("at least ₹10,000", (10000, None)),
    ("below 45,000", (None, 45000)), ("within 1.5 lakhs", (None, 150000)),
    # not money
    ("16GB RAM and 512GB SSD laptop", (None, None)), ("a 4K TV", (None, None)), ("55 inch OLED", (None, None)),
    ("5000mAh battery phone", (None, None)), ("I need 2 of them", (None, None)), ("size 9 shoes", (None, None)),
    ("1TB hard disk", (None, None)), ("120Hz display", (None, None)),
]

OFFERS = [
    {"number": i + 1, "title": t, "price_display": f"₹{p:,}", "rating": r, "rating_count": c}
    for i, (t, p, r, c) in enumerate([
        ("Strideway Glide 4 Women's Running Shoes Cushioned", 3999, 4.5, 1400),
        ("Pacer Flex Women Running Shoes Lightweight Road", 2999, 4.3, 2200),
        ("Dashline Aero Women's Running Shoes Breathable Mesh", 3499, 4.4, 1100),
    ])
]
SHOES = {"product": "running shoes", "facts": {"gender": "women"}, "budget_max": 5000, "pick": 1}

CASES = [
    # first mention of a product: build the question plan
    {"id": "vague-jeans", "message": "I need jeans", "decision": {"ask"}, "product": ["jean"], "attrs": True},
    {"id": "vague-laptop", "message": "looking for a laptop", "decision": {"ask"}, "product": ["laptop"], "attrs": True},
    {"id": "vague-headphones", "message": "get me some headphones", "decision": {"ask"}, "product": ["headphone"], "attrs": True},
    {"id": "gift", "message": "I want to buy a gift for my sister", "decision": {"ask"}, "product": ["gift"], "attrs": True},
    # enough detail: search, with budget and skip captured
    {"id": "jeans-detailed", "message": "women's straight fit high rise blue jeans under ₹2,000, just show me options",
     "decision": {"search"}, "product": ["jean"], "budget_max": 2000, "skip": True},
    {"id": "earbuds-budget", "message": "wireless earbuds under 3000, you decide", "decision": {"search"},
     "product": ["earbud", "earphone", "headphone"], "budget_max": 3000, "skip": True},
    {"id": "laptop-lakh", "message": "laptop for Docker and VMs around 1 lakh, surprise me", "decision": {"search"},
     "product": ["laptop"], "budget_max": 100000, "skip": True, "fact": {"recency": "current"}},
    {"id": "refurb", "message": "refurbished laptop for college under 30k, just show me", "decision": {"search"},
     "product": ["laptop"], "budget_max": 30000, "fact": {"condition": "refurb"}},
    {"id": "brand-named", "message": "Nike running shoes for men up to 6000, show me what you have", "decision": {"search"},
     "product": ["shoe"], "budget_max": 6000, "queries_contain": "nike"},
    {"id": "range", "message": "phone between 15k and 25k with a good camera, just pick for me", "decision": {"search"},
     "product": ["phone"], "budget_min": 15000, "budget_max": 25000, "skip": True},
    # small talk and personal facts
    {"id": "greeting", "message": "hey barney", "decision": {"chat"}},
    {"id": "thanks", "message": "thanks, that was helpful!", "decision": {"chat"}},
    {"id": "name", "message": "by the way my name is Priya", "decision": {"chat"}, "remember": "priya"},
    {"id": "size-memory", "message": "I wear size 7 in women's shoes, just so you know", "decision": {"chat", "ask"}, "remember": "7"},
    # follow-ups once results exist
    {"id": "more", "message": "show me more options", "state": {"profile": SHOES, "offers": OFFERS, "shown": [1, 2, 3]},
     "decision": {"alternatives"}},
    {"id": "compare", "message": "compare them side by side", "state": {"profile": SHOES, "offers": OFFERS, "shown": [1, 2, 3]},
     "decision": {"compare"}},
    {"id": "cheaper", "message": "something cheaper please", "state": {"profile": SHOES, "offers": OFFERS, "shown": [1, 2, 3]},
     "decision": {"search"}, "mode": "refine", "keep_product": ["shoe"]},
    {"id": "question-about-listing", "message": "which of these is the lightest?",
     "state": {"profile": SHOES, "offers": OFFERS, "shown": [1, 2, 3]}, "decision": {"chat"}},
    {"id": "brand-switch", "message": "only Nike please", "state": {"profile": SHOES, "offers": OFFERS, "shown": [1, 2, 3]},
     "decision": {"search"}, "mode": "refine", "queries_contain": "nike"},
    # a different product must reset the profile
    {"id": "switch-product", "message": "actually I need a laptop backpack now", "state": {"profile": SHOES, "offers": OFFERS, "shown": [1, 2, 3]},
     "decision": {"ask", "search"}, "restart": True, "product": ["backpack", "bag"]},
]
