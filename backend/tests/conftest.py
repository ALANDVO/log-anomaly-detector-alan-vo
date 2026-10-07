import pytest
from app.core.database import init_db

@pytest.fixture(autouse=True)
def setup_test_database():
    init_db()
