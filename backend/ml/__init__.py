"""Machine Learning module for chess move quality prediction.

This module provides ML-based move quality prediction as a complement
to the rule-based analysis in the explain module.
"""
from .predictor import MoveQualityPredictor, predict_move_quality
from .feature_engineering import extract_ml_features

__all__ = [
    "MoveQualityPredictor",
    "predict_move_quality",
    "extract_ml_features",
]
