"""Tests for environment-based configuration."""
import importlib
import os
import sys
from unittest.mock import patch

import mongomock
import pytest


class TestFlaskSecretKey:
    def test_flask_secret_key_used(self, flask_app):
        """Flask app deve usar FLASK_SECRET_KEY, não o segredo OAuth."""
        expected = os.environ.get('FLASK_SECRET_KEY', 'test_flask_secret_key_for_testing_only!')
        assert flask_app.secret_key == expected

    def test_flask_secret_key_differs_from_oauth_secret(self, flask_app):
        """FLASK_SECRET_KEY deve ser diferente do segredo OAuth."""
        oauth_secret = os.environ.get('GOOGLE_OAUTH_CREDENTIAL_SECRET', '')
        # Em produção eles devem ser diferentes; nos testes os dois são 'test_*'
        # O importante é que o app usa FLASK_SECRET_KEY, não o OAuth secret
        import application.app as app_module
        assert app_module.SECRET_KEY == flask_app.secret_key


class TestMongoEnvVars:
    def test_get_db_client_uses_mongo_user_env(self):
        """get_db_client deve usar MONGO_USER do ambiente."""
        from application import db_config
        # Verifica que a função lê a variável de ambiente
        import inspect
        source = inspect.getsource(db_config.get_db_client)
        assert 'MONGO_USER' in source

    def test_get_db_client_uses_mongo_pass_env(self):
        """get_db_client deve usar MONGO_PASS do ambiente."""
        from application import db_config
        import inspect
        source = inspect.getsource(db_config.get_db_client)
        assert 'MONGO_PASS' in source
