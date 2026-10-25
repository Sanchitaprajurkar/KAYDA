from backend.agents.thor.agent import ThorAgent
from backend.agents.thor.memory import ThorPersistentMemory
from backend.agents.thor.prompts import (
    THOR_SYSTEM_PROMPT,
    INITIAL_ANALYSIS_INSTRUCTION,
    CROSS_EXAM_ATTACK_INSTRUCTION,
    CROSS_EXAM_DEFENCE_INSTRUCTION,
)

__all__ = [
    "ThorAgent",
    "ThorPersistentMemory",
    "THOR_SYSTEM_PROMPT",
    "INITIAL_ANALYSIS_INSTRUCTION",
    "CROSS_EXAM_ATTACK_INSTRUCTION",
    "CROSS_EXAM_DEFENCE_INSTRUCTION",
]
