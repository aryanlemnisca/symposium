"""Session configuration — replaces hardcoded constants from lemnisca_panel.py."""

from dataclasses import dataclass, field


@dataclass
class EngineConfig:
    """All configurable parameters for a brainstorming session."""
    gemini_api_key: str
    problem_statement: str
    agents: list[dict]
    mode: str = "product"

    max_rounds: int = 50
    temperature: float = 0.70
    main_model: str = "gemini-3.1-pro-preview"
    support_model: str = "gemini-2.5-flash"

    gate_start_round: int = 10
    overseer_interval: int = 10
    min_rounds_before_convergence: int = 45
    rolling_summary_threshold: int = 70
    prd_panel_rounds: int = 10
    stress_test_min_rounds_per_phase: int = 20

    agent_names: list[str] = field(default_factory=list)
    prd_panel_names: list[str] = field(default_factory=list)

    artifact_schedule: dict = field(default_factory=dict)

    convergence_keywords: list[str] = field(default_factory=lambda: [
        "i agree", "exactly right", "well said", "nothing to add",
        "session complete", "spec is locked", "build it", "we are done",
        "meeting adjourned", "lock the spec", "stop brainstorming", "get this built",
    ])

    consensus_phrases: list[str] = field(default_factory=lambda: [
        "spec is locked", "session complete", "build it", "we are done here",
        "meeting adjourned", "get this built", "stop brainstorming", "start coding",
    ])

    def __post_init__(self):
        self.agent_names = [a["name"] for a in self.agents]
        if not self.prd_panel_names:
            self.prd_panel_names = self.agent_names[:4]
        if not self.artifact_schedule:
            self.artifact_schedule = self._build_artifact_schedule()

    def _build_artifact_schedule(self) -> dict:
        """Build artifact milestones as percentages of max_rounds."""
        milestones = [
            (0.25, "C-Level Verdicts"),
            (0.45, "Product Concepts Proposed and Killed"),
            (0.65, "Architectural Decisions"),
            (0.80, "Design Constraints and Rejections"),
        ]
        schedule = {}
        for i, (pct, name) in enumerate(milestones):
            round_num = max(3, round(self.max_rounds * pct))
            schedule[round_num] = (name, i + 1)
        return schedule
