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

    agent_names: list[str] = field(default_factory=list)
    prd_panel_names: list[str] = field(default_factory=list)

    artifact_schedule: dict = field(default_factory=lambda: {
        20: ("C-Level Verdicts", 1),
        40: ("Product Concepts Proposed and Killed", 2),
        55: ("Architectural Decisions", 3),
        65: ("Physics and Logic Engine Constraints", 4),
        75: ("Design Constraints and Rejections", 5),
    })

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
        if self.max_rounds <= 30:
            self.artifact_schedule = {
                10: ("C-Level Verdicts", 1),
                20: ("Key Decisions", 2),
            }
        elif self.max_rounds <= 60:
            self.artifact_schedule = {
                15: ("C-Level Verdicts", 1),
                30: ("Product Concepts Proposed and Killed", 2),
                45: ("Architectural Decisions", 3),
            }
