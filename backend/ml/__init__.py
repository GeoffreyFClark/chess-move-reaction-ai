"""Machine Learning module for chess move quality prediction.

This module provides ML-based move quality prediction as a complement
to the rule-based analysis in the explain module.
"""

from .feature_engineering import extract_ml_features
from .predictor import MoveQualityPredictor, predict_move_quality

__all__ = [
    "MoveQualityPredictor",
    "predict_move_quality",
    "extract_ml_features",
]
