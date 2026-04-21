import pytest
from quinex import Quinex
from quinex.config.presets import models



@pytest.fixture(scope="session")
def quinex():
    """Single standard Quinex instance shared across the test session. Tiny models used for speed."""
    return Quinex(**models.tiny)


@pytest.fixture(scope="session")
def quinex_with_empty():
    """Single shared Quinex instance with empty dict instead of None for empty predictions enabled."""
    return Quinex(**models.tiny, empty_dict_for_empty_prediction=True)
