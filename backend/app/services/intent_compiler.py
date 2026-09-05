import re

from app.domain.models import HardConstraints, MandateDraft, SemanticConstraint, UnresolvedField


AMOUNT_PATTERN = re.compile(r"(?:₹|INR\s*)\s*([\d,]+)(?:\s*(k|thousand))?", re.IGNORECASE)


def compile_intent(instruction: str, merchant_id: str = "merchant_demo") -> MandateDraft:
    match = AMOUNT_PATTERN.search(instruction)
    unresolved: list[UnresolvedField] = []
    hard = None
    if match:
        rupees = int(match.group(1).replace(",", ""))
        if match.group(2):
            rupees *= 1000
        hard = HardConstraints(max_amount_paise=rupees * 100, allowed_currencies=["INR"], allowed_merchants=[merchant_id], allowed_categories=["headphones"], allowed_conditions=["new"], max_quantity=1, max_executions=1)
    else:
        unresolved.append(UnresolvedField(field="max_amount", reason="No explicit numerical amount was provided."))
    semantic = []
    lower = instruction.lower()
    for key, phrase in (("travel", "good for travel"), ("not_flashy", "nothing flashy"), ("minimal", "minimal"), ("comfortable", "comfortable")):
        if phrase in lower:
            semantic.append(SemanticConstraint(id=key, text=phrase))
    return MandateDraft(instruction_text=instruction, hard_constraints=hard, semantic_constraints=semantic, unresolved=unresolved)

