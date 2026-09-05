from __future__ import annotations

import re
from typing import Any

from app.domain.models import HardConstraints, MandateDraft, SemanticConstraint, UnresolvedField

# Currency and numerical amount patterns
AMOUNT_PATTERNS = [
    re.compile(r"(?:₹|INR\s*|Rs\.?\s*)\s*([\d,]+)(?:\s*(k|thousand|lakh))?", re.IGNORECASE),
    re.compile(r"under\s+(?:₹|INR\s*|Rs\.?\s*)?\s*([\d,]+)(?:\s*(k|thousand|lakh))?", re.IGNORECASE),
    re.compile(r"\b([\d,]+)\s*(?:k|thousand)\s*(?:INR|rupees|₹)", re.IGNORECASE),
    re.compile(r"\$\s*([\d,]+)(?:\s*(k|thousand))?", re.IGNORECASE),
]

KNOWN_CATEGORIES = {
    "headphones": ["headphone", "headphones", "earphone", "earphones", "earbuds", "earbud", "audio"],
    "laptops": ["laptop", "laptops", "notebook", "ultrabook", "macbook"],
    "smartphones": ["smartphone", "smartphones", "phone", "phones", "mobile"],
    "monitors": ["monitor", "monitors", "display", "screen"],
    "keyboards": ["keyboard", "keyboards"],
    "furniture": ["chair", "desk", "table", "furniture"],
    "books": ["book", "books", "textbook"],
    "footwear": ["shoes", "shoe", "sneakers", "boots", "footwear"],
    "apparel": ["jacket", "shirt", "t-shirt", "pants", "hoodie", "apparel", "clothing"],
    "wearables": ["watch", "smartwatch", "wearables", "band"],
}

KNOWN_SEMANTIC_PHRASES = [
    ("not_flashy", re.compile(r"\b(nothing flashy|not flashy|understated|subtle|no loud branding|minimal branding)\b", re.IGNORECASE)),
    ("travel", re.compile(r"\b(good for travel|suitable for travel|travel friendly|portable|compact|flight friendly)\b", re.IGNORECASE)),
    ("minimal", re.compile(r"\b(minimal|minimalist|clean look|discreet)\b", re.IGNORECASE)),
    ("comfortable", re.compile(r"\b(comfortable|comfy|ergonomic|soft pads|lightweight)\b", re.IGNORECASE)),
    ("noise_cancelling", re.compile(r"\b(noise[- ]cancelling|noise cancelling|anc|quiet)\b", re.IGNORECASE)),
    ("water_resistant", re.compile(r"\b(water[- ]resistant|waterproof|weather resistant)\b", re.IGNORECASE)),
    ("durable", re.compile(r"\b(durable|rugged|sturdy|heavy duty)\b", re.IGNORECASE)),
    ("eco_friendly", re.compile(r"\b(eco[- ]friendly|sustainable|recycled|biodegradable)\b", re.IGNORECASE)),
    ("office_use", re.compile(r"\b(for office|office use|work from home|for meetings)\b", re.IGNORECASE)),
    ("gaming", re.compile(r"\b(for gaming|gaming|low latency)\b", re.IGNORECASE)),
]


def _extract_amount(instruction: str) -> tuple[int | None, str]:
    """Extract explicit amount in paise and currency. Returns (paise, currency)."""
    for pattern in AMOUNT_PATTERNS:
        match = pattern.search(instruction)
        if match:
            raw_num = match.group(1).replace(",", "")
            if not raw_num.isdigit():
                continue
            val = int(raw_num)
            mult = match.group(2).lower() if match.lastindex and match.lastindex >= 2 and match.group(2) else ""
            if mult in ("k", "thousand"):
                val *= 1000
            elif mult == "lakh":
                val *= 100000

            currency = "USD" if "$" in match.group(0) else "INR"
            return val * 100, currency
    return None, "INR"


def _extract_categories(instruction: str) -> list[str]:
    """Detect product categories mentioned in the instruction.
    
    Returns only categories that are explicitly mentioned in the instruction.
    No fallback defaults - if no category is detected, returns empty list.
    """
    lower = instruction.lower()
    matched = []
    for cat, keywords in KNOWN_CATEGORIES.items():
        if any(re.search(rf"\b{re.escape(kw)}\b", lower) for kw in keywords):
            matched.append(cat)
    return matched  # No fallback - return empty if no categories detected


def _extract_conditions(instruction: str) -> list[str]:
    lower = instruction.lower()
    if "refurbished" in lower or "renewed" in lower:
        return ["refurbished"]
    if "used" in lower or "pre-owned" in lower:
        return ["used"]
    if "open box" in lower:
        return ["open_box"]
    return ["new"]


def compile_intent(instruction: str, merchant_id: str = "merchant_demo") -> MandateDraft:
    """Compiles natural-language delegation into hard and semantic constraints.

    Core Invariant:
    - Never invent numerical spending authority. If no numeric ceiling is stated,
      return unresolved: max_amount.
    - Never convert vague phrases ('cheap', 'reasonable') into money limits.
    """
    unresolved: list[UnresolvedField] = []
    amount_paise, currency = _extract_amount(instruction)

    if amount_paise is None:
        unresolved.append(
            UnresolvedField(
                field="max_amount",
                reason="No explicit numerical spending ceiling was stated in delegation instruction.",
            )
        )
        hard = None
    else:
        categories = _extract_categories(instruction)
        conditions = _extract_conditions(instruction)
        hard = HardConstraints(
            max_amount_paise=amount_paise,
            allowed_currencies=[currency],
            allowed_merchants=[merchant_id],
            allowed_categories=categories,
            allowed_conditions=conditions,
            max_quantity=1,
            max_executions=1,
        )

    # Extract fuzzy semantic constraints
    semantic: list[SemanticConstraint] = []
    seen_ids: set[str] = set()
    for key, pattern in KNOWN_SEMANTIC_PHRASES:
        m = pattern.search(instruction)
        if m and key not in seen_ids:
            seen_ids.add(key)
            semantic.append(SemanticConstraint(id=key, text=m.group(0)))

    return MandateDraft(
        instruction_text=instruction,
        hard_constraints=hard,
        semantic_constraints=semantic,
        unresolved=unresolved,
    )
