from app.services.intent_compiler import compile_intent


def test_negated_refurbished_condition_does_not_expand_authority() -> None:
    draft = compile_intent(
        "Buy headphones under INR 20,000. Nothing refurbished.",
        merchant_id="merchant_real",
    )

    assert draft.hard_constraints is not None
    assert draft.hard_constraints.allowed_conditions == ["new"]


def test_explicit_refurbished_condition_is_preserved() -> None:
    draft = compile_intent(
        "Buy refurbished headphones under INR 20,000.",
        merchant_id="merchant_real",
    )

    assert draft.hard_constraints is not None
    assert draft.hard_constraints.allowed_conditions == ["refurbished"]
