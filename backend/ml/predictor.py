"""Move quality prediction using ML or heuristic models.

This module provides move quality prediction that complements the
rule-based analysis. It can use either a trained ML model (if available)
or fall back to a heuristic-based prediction.
"""

import logging
from pathlib import Path
from typing import TypedDict

import chess

from .feature_engineering import extract_ml_features

logger = logging.getLogger(__name__)

# Quality labels in order from best to worst
QUALITY_LABELS = ["excellent", "good", "inaccuracy", "mistake", "blunder"]


class MoveQualityPrediction(TypedDict):
    """Prediction result for move quality."""

    prediction: str
    confidence: float
    probabilities: dict[str, float]
    method: str  # "ml" or "heuristic"


class MoveQualityPredictor:
    """Predicts move quality using ML model or heuristics.

    This class tries to load a trained scikit-learn model from disk.
    If no model is available, it falls back to heuristic-based prediction.
    """

    _instance: "MoveQualityPredictor | None" = None
    _model = None
    _model_loaded = False

    def __init__(self, model_path: Path | None = None):
        """Initialize the predictor.

        Args:
            model_path: Optional path to a joblib model file.
        """
        self._model_path = model_path or self._default_model_path()
        self._try_load_model()

    @staticmethod
    def _default_model_path() -> Path:
        """Get the default model path."""
        return Path(__file__).parent / "models" / "move_quality_model.joblib"

    def _try_load_model(self) -> None:
        """Attempt to load the ML model."""
        if self._model_path.exists():
            try:
                import joblib

                self._model = joblib.load(self._model_path)
                self._model_loaded = True
                logger.info(f"Loaded ML model from {self._model_path}")
            except Exception as e:
                logger.warning(f"Failed to load ML model: {e}")
                self._model_loaded = False
        else:
            logger.info("No ML model found, using heuristic prediction")
            self._model_loaded = False

    @classmethod
    def get_instance(cls) -> "MoveQualityPredictor":
        """Get or create the singleton predictor instance.

        Returns:
            The MoveQualityPredictor singleton.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def is_ml_available(self) -> bool:
        """Check if ML model is loaded."""
        return self._model_loaded

    def predict(self, board: chess.Board, move: chess.Move) -> MoveQualityPrediction:
        """Predict move quality.

        Uses the ML model if available, otherwise falls back to heuristics.

        Args:
            board: The chess position before the move.
            move: The move to evaluate.

        Returns:
            MoveQualityPrediction with prediction, confidence, and probabilities.
        """
        if self._model_loaded and self._model is not None:
            return self._predict_ml(board, move)
        return self._predict_heuristic(board, move)

    def _predict_ml(self, board: chess.Board, move: chess.Move) -> MoveQualityPrediction:
        """Predict using the ML model."""
        features = extract_ml_features(board, move)

        try:
            import numpy as np

            features_array = np.array(features).reshape(1, -1)
            proba = self._model.predict_proba(features_array)[0]
            predicted_idx = np.argmax(proba)

            return {
                "prediction": QUALITY_LABELS[predicted_idx],
                "confidence": float(proba[predicted_idx]),
                "probabilities": dict(zip(QUALITY_LABELS, [float(p) for p in proba], strict=False)),
                "method": "ml",
            }
        except Exception as e:
            logger.warning(f"ML prediction failed, falling back to heuristic: {e}")
            return self._predict_heuristic(board, move)

    def _predict_heuristic(self, board: chess.Board, move: chess.Move) -> MoveQualityPrediction:
        """Predict using heuristics based on feature values.

        This provides a reasonable baseline prediction without needing
        a trained model.
        """
        features = extract_ml_features(board, move)

        # Extract key features by index
        is_capture = features[16] > 0.5
        is_check = features[17] > 0.5
        is_promotion = features[18] > 0.5
        piece_value_moved = features[19]
        piece_value_captured = features[20]
        to_square_attacked = features[21] > 0.5

        # Simple scoring heuristic
        score = 0.5  # Start neutral

        # Positive signals
        if is_check:
            score += 0.15
        if is_promotion:
            score += 0.25
        if is_capture and piece_value_captured > piece_value_moved:
            score += 0.2  # Winning capture
        elif is_capture and piece_value_captured == piece_value_moved:
            score += 0.05  # Even trade

        # Negative signals
        if to_square_attacked and piece_value_moved >= 5:
            score -= 0.2  # Moving valuable piece to attacked square
        if is_capture and piece_value_captured < piece_value_moved:
            score -= 0.15  # Losing capture

        # Clamp score to [0, 1]
        score = max(0.0, min(1.0, score))

        # Convert score to quality label
        if score >= 0.7:
            prediction = "excellent"
        elif score >= 0.55:
            prediction = "good"
        elif score >= 0.4:
            prediction = "inaccuracy"
        elif score >= 0.25:
            prediction = "mistake"
        else:
            prediction = "blunder"

        # Create probability distribution centered on prediction
        proba = dict.fromkeys(QUALITY_LABELS, 0.1)
        proba[prediction] = 0.6

        return {
            "prediction": prediction,
            "confidence": proba[prediction],
            "probabilities": proba,
            "method": "heuristic",
        }


def predict_move_quality(board: chess.Board, move: chess.Move) -> MoveQualityPrediction:
    """Convenience function to predict move quality.

    Args:
        board: The chess position before the move.
        move: The move to evaluate.

    Returns:
        MoveQualityPrediction with prediction details.
    """
    predictor = MoveQualityPredictor.get_instance()
    return predictor.predict(board, move)
