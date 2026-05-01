<<<<<<< HEAD
﻿"""Network Security Situational Awareness System."""

__version__ = "4.0.0"
__author__ = "SSA Team"

from .detection.hybrid_detector import HybridDetector
from .detection.ml_detector import MLDetector
from .detection.rule_engine import RuleEngine
from .explainability.attack_explainer import AttackExplainer

__all__ = ["HybridDetector", "RuleEngine", "MLDetector", "AttackExplainer"]
=======
# Package marker for test imports.
>>>>>>> e7862cd2291f87b9b6b2df0f04c4bd5cedbfdc39
