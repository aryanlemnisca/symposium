"""Convergence detection and consensus termination."""


def check_convergence(
    messages: list,
    agent_names: list[str],
    convergence_keywords: list[str],
    window: int = 3,
) -> bool:
    recent = [
        m for m in messages[-(window * 2):]
        if getattr(m, "source", "") in agent_names
    ][-window:]
    if len(recent) < window:
        return False
    return sum(
        1 for m in recent
        if any(kw in getattr(m, "content", "").lower() for kw in convergence_keywords)
    ) >= window


def check_consensus_termination(
    messages: list,
    round_num: int,
    c_coverage: dict,
    agent_names: list[str],
    consensus_phrases: list[str],
    min_rounds: int,
) -> bool:
    if round_num < min_rounds:
        return False
    if c_coverage and not all(c_coverage.values()):
        return False
    signalling = set()
    for m in messages:
        src = getattr(m, "source", "")
        content = getattr(m, "content", "").lower()
        if src in agent_names and any(p in content for p in consensus_phrases):
            signalling.add(src)
    return len(signalling) >= 3
