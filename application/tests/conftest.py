import os
from unittest.mock import patch

import mongomock
import pytest

# Set required environment variables BEFORE any application code is imported.
os.environ.setdefault('GOOGLE_OAUTH_CREDENTIAL_ID', 'test_google_client_id')
os.environ.setdefault('GOOGLE_OAUTH_CREDENTIAL_SECRET', 'test_google_client_secret')
os.environ.setdefault('FLASK_SECRET_KEY', 'test_flask_secret_key_for_testing_only!')

# Import db_config first so the MongoClient name exists in its namespace,
# then patch it before app.py is imported (app.py calls get_db_client() at
# module level).
import application.db_config  # noqa: E402

_patcher = patch('application.db_config.MongoClient', mongomock.MongoClient)
_patcher.start()

# Now import the application — DB calls will use mongomock.
import application.app as app_module  # noqa: E402


@pytest.fixture(scope='session')
def flask_app():
    app_module.app.config['TESTING'] = True
    app_module.app.config['WTF_CSRF_ENABLED'] = False
    return app_module.app


@pytest.fixture
def client(flask_app):
    with flask_app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def clear_db():
    """Drop all collections before each test to ensure isolation."""
    db = app_module.client.dev
    for name in db.list_collection_names():
        db.drop_collection(name)
    yield
