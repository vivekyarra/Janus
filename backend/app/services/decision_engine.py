from app.domain.models import DecisionType, FinalDecision, HardGateResult, ReasonCode, SemanticAssessment


def decide(hard: HardGateResult, semantic: SemanticAssessment) -> FinalDecision:
    if hard.status == "FAIL":
        return FinalDecision(decision=DecisionType.BLOCK, reason_code=hard.reason_code, hard_gate=hard)
    if semantic.service_status == "UNAVAILABLE":
        return FinalDecision(decision=DecisionType.STEP_UP, reason_code=ReasonCode.SEMANTIC_SERVICE_UNAVAILABLE, hard_gate=hard, semantic=semantic)
    statuses = {item.status for item in semantic.results}
    if "CONTRADICTED" in statuses:
        return FinalDecision(decision=DecisionType.STEP_UP, reason_code=ReasonCode.SEMANTIC_CONTRADICTED, hard_gate=hard, semantic=semantic)
    if "INSUFFICIENT_EVIDENCE" in statuses:
        return FinalDecision(decision=DecisionType.STEP_UP, reason_code=ReasonCode.SEMANTIC_INSUFFICIENT_EVIDENCE, hard_gate=hard, semantic=semantic)
    return FinalDecision(decision=DecisionType.ALLOW, reason_code=ReasonCode.SEMANTIC_SUPPORTED if semantic.results else None, hard_gate=hard, semantic=semantic)

