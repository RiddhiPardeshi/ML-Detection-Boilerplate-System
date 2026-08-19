#!/usr/bin/env python
"""Create a simple trained model for demo purposes."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from backend.app.ml.models.sklearn_wrapper import SklearnModelWrapper
from backend.app.ml.preprocessing.tabular import TabularPreprocessor


def create_demo_model():
    """Generate synthetic data, train a model, and save it."""
    
    # Create synthetic tabular data
    np.random.seed(42)
    n_samples = 100
    
    features = pd.DataFrame({
        'age': np.random.randint(20, 80, n_samples),
        'income': np.random.randint(20000, 150000, n_samples),
        'score': np.random.uniform(0, 100, n_samples),
        'category': np.random.choice(['A', 'B', 'C'], n_samples),
    })
    
    # Create binary target (0 or 1)
    target = np.random.binomial(1, 0.5, n_samples)
    
    print(f"✓ Generated synthetic data: {features.shape[0]} samples, {features.shape[1]} features")
    print(f"  Features: {list(features.columns)}")
    
    # Create and fit preprocessor
    numeric_features = ['age', 'income', 'score']
    categorical_features = ['category']
    
    preprocessor = TabularPreprocessor(
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )
    
    X_processed = preprocessor.fit_transform(features)
    print(f"✓ Fitted preprocessor: {X_processed.shape[1]} output features")
    
    # Train a simple classifier
    sklearn_model = RandomForestClassifier(
        n_estimators=10,
        max_depth=5,
        random_state=42,
    )
    sklearn_model.fit(X_processed, target)
    
    # Wrap it in our TabularModel interface
    model = SklearnModelWrapper(sklearn_model)
    print(f"✓ Trained RandomForestClassifier: {sklearn_model.n_estimators} trees")
    
    # Create artifacts directory
    artifacts_dir = project_root / "backend" / "app" / "ml" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    # Save model and preprocessor together in one joblib file
    model_path = artifacts_dir / "model.joblib"
    artifact = {
        "model": model,
        "preprocessor": preprocessor,
    }
    joblib.dump(artifact, model_path)
    print(f"✓ Saved model and preprocessor to: {model_path}")
    
    print("\n✓ Demo model creation complete!")
    print(f"\nTo use this model with the app, no env vars needed (default path: {model_path})")


if __name__ == "__main__":
    create_demo_model()
