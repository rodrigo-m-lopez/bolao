# coding: utf-8
"""Tests for _init_dev_db — startup DB seeding dispatch."""
import os
from unittest.mock import patch, call
import mongomock
import pytest


def _make_db():
    return mongomock.MongoClient()['test']


# Import after conftest has patched MongoClient
from application.app import _init_dev_db  # noqa: E402


class TestInitDevDb:
    def test_calls_populate_dev_db_when_no_seed_from_api_flag(self):
        """Default DEV_MOCK_AUTH mode uses the mock seed (no API key required)."""
        db = _make_db()
        env = {k: v for k, v in os.environ.items()
               if k not in ('SEED_FROM_API', 'FOOTBALL_DATA_API_KEY')}
        with patch.dict(os.environ, env, clear=True):
            with patch('application.dev_seed.populate_dev_db') as mock_pop:
                _init_dev_db(db)
        mock_pop.assert_called_once_with(db)

    def test_calls_populate_dev_db_when_seed_from_api_but_no_key(self):
        """SEED_FROM_API=true without an API key falls back to mock seed."""
        db = _make_db()
        env = {k: v for k, v in os.environ.items()
               if k != 'FOOTBALL_DATA_API_KEY'}
        env['SEED_FROM_API'] = 'true'
        with patch.dict(os.environ, env, clear=True):
            with patch('application.dev_seed.populate_dev_db') as mock_pop:
                _init_dev_db(db)
        mock_pop.assert_called_once_with(db)

    def test_calls_seed_database_when_seed_from_api_and_key_set(self):
        """SEED_FROM_API=true + FOOTBALL_DATA_API_KEY → real API seed (todas as competições)."""
        db = _make_db()
        with patch.dict(os.environ,
                        {'SEED_FROM_API': 'true', 'FOOTBALL_DATA_API_KEY': 'test_key_123'}):
            with patch('application.crawler_2026.seed_database') as mock_copa:
                with patch('application.crawler_brasileirao.seed_brasileirao') as mock_br:
                    with patch('application.crawler_libertadores.seed_libertadores') as mock_lib:
                        with patch('application.crawler_copa_brasil.seed_copa_brasil') as mock_cbr:
                            _init_dev_db(db)
        mock_copa.assert_called_once_with(db)
        mock_br.assert_called_once_with(db)
        mock_lib.assert_called_once_with(db)
        mock_cbr.assert_called_once_with(db)

    def test_does_not_call_populate_dev_db_when_using_api_seed(self):
        """When API seed is selected, mock seed must NOT be called."""
        db = _make_db()
        with patch.dict(os.environ,
                        {'SEED_FROM_API': 'true', 'FOOTBALL_DATA_API_KEY': 'test_key_123'}):
            with patch('application.crawler_2026.seed_database'):
                with patch('application.crawler_brasileirao.seed_brasileirao'):
                    with patch('application.crawler_libertadores.seed_libertadores'):
                        with patch('application.crawler_copa_brasil.seed_copa_brasil'):
                            with patch('application.dev_seed.populate_dev_db') as mock_pop:
                                _init_dev_db(db)
        mock_pop.assert_not_called()
