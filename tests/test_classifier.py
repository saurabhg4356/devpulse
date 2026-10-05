"""Unit tests for CommitClassifier using TF-IDF and Multinomial Naive Bayes."""

import pytest
from models.commit import Commit
from models.exceptions import ClassificationError
from services.commit_classifier import CommitClassifier


class TestCommitClassifier:
    """Verify TF-IDF and Naive Bayes commit intent classification."""

    @pytest.fixture(scope="class")
    def classifier(self) -> CommitClassifier:
        return CommitClassifier()

    def test_feature_classification(self, classifier: CommitClassifier) -> None:
        cat, conf = classifier.predict("feat: implement oauth2 login with google")
        assert cat == "Feature"
        assert conf > 0.3

    def test_bugfix_classification(self, classifier: CommitClassifier) -> None:
        cat, conf = classifier.predict("fix: resolve null pointer exception in database query")
        assert cat == "Bug Fix"
        assert conf > 0.3

    def test_refactor_classification(self, classifier: CommitClassifier) -> None:
        cat, conf = classifier.predict("refactor: extract helper functions and simplify class hierarchy")
        assert cat == "Refactor"
        assert conf > 0.3

    def test_testing_classification(self, classifier: CommitClassifier) -> None:
        cat, conf = classifier.predict("test: add integration test suite for payment workflow")
        assert cat == "Testing"
        assert conf > 0.3

    def test_documentation_classification(self, classifier: CommitClassifier) -> None:
        cat, conf = classifier.predict("docs: update readme guide with installation instructions")
        assert cat == "Documentation"
        assert conf > 0.3

    def test_empty_or_vague_message_defaults_to_other(self, classifier: CommitClassifier) -> None:
        cat_empty, _ = classifier.predict("")
        assert cat_empty == "Other"

        cat_vague, _ = classifier.predict("asdkjhasd random word xyz123")
        assert cat_vague in ("Other", "Configuration")

    def test_classify_commits_batch(self, classifier: CommitClassifier, sample_commits: list[Commit]) -> None:
        distribution = classifier.classify_commits(sample_commits)
        assert isinstance(distribution, dict)
        # Verify that all commits received a classification
        for c in sample_commits:
            assert c.classification is not None
            assert len(c.classification) > 0

    def test_train_mismatched_raises(self, classifier: CommitClassifier) -> None:
        with pytest.raises(ClassificationError):
            classifier.train(["text1", "text2"], ["label1"])
