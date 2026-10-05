"""Commit message classifier using TF-IDF vectorization and Multinomial Naive Bayes.

Categorizes Git commit messages into engineering intent types (Feature, Bug Fix, Refactor,
Performance, Testing, Documentation, Configuration, Other).
Includes confidence threshold fallback to 'Other' and documents model limitations.
"""

from typing import Dict, List, Optional, Sequence, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

from config.settings import DEFAULT_CONFIG, DevPulseConfig
from models.commit import Commit
from models.exceptions import ClassificationError


# Curated seed training corpus representing common engineering commit phrasing
SEED_TRAINING_DATA: List[Tuple[str, str]] = [
    # Feature
    ("feat: add user authentication and jwt tokens", "Feature"),
    ("implement checkout workflow and payment gateway", "Feature"),
    ("add support for oauth2 google login", "Feature"),
    ("introduce dark mode ui toggle in settings", "Feature"),
    ("new rest api endpoint for customer orders", "Feature"),
    ("create export to csv button in dashboard", "Feature"),
    ("allow users to upload profile pictures", "Feature"),
    ("add webhook notification for failed payments", "Feature"),
    ("feat(api): support pagination in list users", "Feature"),
    ("implemented redis caching for catalog search", "Feature"),

    # Bug Fix
    ("fix: resolve null pointer exception in auth service", "Bug Fix"),
    ("bugfix: correct calculation of sales tax on checkout", "Bug Fix"),
    ("fixed crash when user profile image is missing", "Bug Fix"),
    ("patch security vulnerability in token parsing", "Bug Fix"),
    ("resolve broken link in navigation bar", "Bug Fix"),
    ("fix memory leak in background stream handler", "Bug Fix"),
    ("fix: prevent duplicate form submissions", "Bug Fix"),
    ("fixed race condition during order confirmation", "Bug Fix"),
    ("fix timezone conversion bug on report generation", "Bug Fix"),
    ("hotfix: resolve 500 error on checkout endpoint", "Bug Fix"),

    # Refactor
    ("refactor: simplify database query layer", "Refactor"),
    ("clean up unused imports and dead legacy code", "Refactor"),
    ("restructure service modules and decouple controllers", "Refactor"),
    ("extract helper functions from main request router", "Refactor"),
    ("reorganize folder structure and rename models", "Refactor"),
    ("modernize legacy class hierarchy to use protocol", "Refactor"),
    ("refactor repository abstraction for cleaner testing", "Refactor"),
    ("simplify nested conditionals in validation engine", "Refactor"),

    # Performance
    ("perf: optimize sql query using composite indexes", "Performance"),
    ("improve page load time by caching redis responses", "Performance"),
    ("reduce bundle size by tree shaking dependencies", "Performance"),
    ("speed up matrix multiplication calculation loop", "Performance"),
    ("optimize image compression and thumbnail generation", "Performance"),
    ("perf: batch database write operations to reduce io", "Performance"),
    ("decrease latency in api response headers", "Performance"),

    # Testing
    ("test: add unit tests for billing calculation service", "Testing"),
    ("add integration tests for complete checkout flow", "Testing"),
    ("increase test coverage for input validators", "Testing"),
    ("add e2e cypress test suite for login page", "Testing"),
    ("mock external stripe payment gateway in tests", "Testing"),
    ("fix flaky test in user registration suite", "Testing"),
    ("test: add parameterized test cases for date parsing", "Testing"),

    # Documentation
    ("docs: update readme with local installation instructions", "Documentation"),
    ("docs: update readme guide with installation instructions", "Documentation"),
    ("document rest api endpoints with swagger openapi", "Documentation"),
    ("fix typos in contributing guide and license", "Documentation"),
    ("add inline docstrings to domain model classes", "Documentation"),
    ("update changelog and release notes for version 2", "Documentation"),
    ("clarify architecture decision in design document", "Documentation"),
    ("documentation: update user manual and architecture diagrams", "Documentation"),
    ("docs(readme): add installation guide and dependencies", "Documentation"),

    # Configuration
    ("chore: update dependencies in pyproject.toml", "Configuration"),
    ("configure github actions continuous integration workflow", "Configuration"),
    ("bump docker base image version to python 3.12", "Configuration"),
    ("add pre-commit hooks for black and ruff linting", "Configuration"),
    ("setup eslint and prettier configuration rules", "Configuration"),
    ("chore(deps): update urllib3 security patch", "Configuration"),

    # Other
    ("sync repository with upstream master", "Other"),
    ("merge branch release-2.0 into main", "Other"),
    ("wip: temporary checkpoint save", "Other"),
    ("misc edits before team standup", "Other"),
    ("initial empty commit", "Other"),
]


class CommitClassifier:
    """Classifies commit messages using TF-IDF and Multinomial Naive Bayes.
    
    LIMITATION NOTE:
    This classifier operates on statistical word frequencies and n-grams. While effective
    at discerning conventional commit prefixes (feat:, fix:, docs:) and strong intent words
    (resolve, benchmark, mock), it does not perform semantic reasoning or parse commit diffs.
    Unusual or vague messages are conservatively classified as 'Other'.
    """

    def __init__(self, config: Optional[DevPulseConfig] = None) -> None:
        self.config = config or DEFAULT_CONFIG
        self.settings = self.config.classifier
        
        # Pipeline composed of TF-IDF Vectorizer and Multinomial Naive Bayes
        self.pipeline: Pipeline = Pipeline(
            [
                (
                    "tfidf",
                    TfidfVectorizer(
                        ngram_range=self.settings.ngram_range,
                        max_features=self.settings.max_features,
                        lowercase=True,
                        stop_words="english",
                    ),
                ),
                (
                    "nb",
                    MultinomialNB(alpha=0.5),
                ),
            ]
        )
        self._is_trained = False
        self._train_seed_model()

    def _train_seed_model(self) -> None:
        """Fit the pipeline on the seed corpus."""
        texts = [item[0] for item in SEED_TRAINING_DATA]
        labels = [item[1] for item in SEED_TRAINING_DATA]
        self.train(texts, labels)

    def train(self, texts: Sequence[str], labels: Sequence[str]) -> None:
        """Train or retrain classifier with labeled commit messages.
        
        Args:
            texts: List of commit messages.
            labels: List of matching intent categories.
        """
        if not texts or not labels or len(texts) != len(labels):
            raise ClassificationError("Training requires matching non-empty texts and labels.")

        try:
            self.pipeline.fit(texts, labels)
            self._is_trained = True
        except Exception as err:
            raise ClassificationError(f"Failed to train commit classifier: {err}") from err

    def predict(self, message: str) -> Tuple[str, float]:
        """Predict the engineering category for a commit message.
        
        Args:
            message: Commit subject or message string.
            
        Returns:
            Tuple of (predicted_category, confidence_score).
            Falls back to 'Other' if confidence < min_confidence.
        """
        if not message or not message.strip():
            return self.settings.default_label, 0.0

        if not self._is_trained:
            raise ClassificationError("Classifier is not trained.")

        cleaned = message.strip()

        try:
            probabilities = self.pipeline.predict_proba([cleaned])[0]
            classes = self.pipeline.classes_
            best_idx = int(np.argmax(probabilities))
            best_class = str(classes[best_idx])
            best_prob = float(probabilities[best_idx])

            if best_prob < self.settings.min_confidence:
                return self.settings.default_label, round(best_prob, 2)

            return best_class, round(best_prob, 2)
        except Exception:
            return self.settings.default_label, 0.0

    def classify_commits(self, commits: Sequence[Commit]) -> Dict[str, int]:
        """Classify each commit in the sequence and return category distribution.
        
        Mutates each Commit object by setting `commit.classification`.
        
        Returns:
            Dictionary mapping category names to counts.
        """
        distribution: Dict[str, int] = {cat: 0 for cat in self.settings.categories}

        for commit in commits:
            pred_class, _ = self.predict(commit.message)
            commit.classification = pred_class
            distribution[pred_class] = distribution.get(pred_class, 0) + 1

        return distribution
