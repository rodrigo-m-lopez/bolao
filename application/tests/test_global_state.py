"""Tests verifying there is no shared global state in app.py."""
import pytest
from bson import ObjectId
from datetime import datetime
import application.app as app_module


def _seed_jogo(nome='BRA x GER', grupo='Grupo A', rodada=1):
    """Insert a minimal jogo document for testing."""
    mandante_id = app_module.tbl_selecao.insert_one(
        {'sigla': 'BRA', 'nome': 'Brasil', 'escudo': 'bra.png', 'grupo': grupo}
    ).inserted_id
    visitante_id = app_module.tbl_selecao.insert_one(
        {'sigla': 'GER', 'nome': 'Alemanha', 'escudo': 'ger.png', 'grupo': grupo}
    ).inserted_id
    app_module.tbl_jogo.insert_one({
        'nome': nome,
        'data': datetime(2026, 6, 12, 18, 0),
        'local': 'MetLife Stadium',
        'mandante': mandante_id,
        'visitante': visitante_id,
        'gols_mandante': None,
        'gols_visitante': None,
        'grupo': grupo,
        'rodada': rodada,
        'url_rodada': '/rodada/1',
    })


class TestNoGlobalState:
    def test_monta_dto_grupos_returns_fresh_list_each_call(self):
        _seed_jogo()
        _, jogos1 = app_module.monta_dto_grupos()
        _, jogos2 = app_module.monta_dto_grupos()
        # Must be different list objects, not a shared global
        assert jogos1 is not jogos2

    def test_todos_jogos_not_duplicated_on_second_call(self):
        _seed_jogo()
        _, jogos1 = app_module.monta_dto_grupos()
        _, jogos2 = app_module.monta_dto_grupos()
        # Second call should return same count, not doubled
        assert len(jogos1) == len(jogos2)

    def test_monta_dto_grupos_returns_tuple(self):
        result = app_module.monta_dto_grupos()
        assert isinstance(result, tuple)
        assert len(result) == 2
        grupos, todos_jogos = result
        assert isinstance(grupos, list)
        assert isinstance(todos_jogos, list)

    def test_todos_jogos_count_matches_db(self):
        _seed_jogo('BRA x GER')
        _seed_jogo('ARG x FRA', 'Grupo B', 1)
        _, todos_jogos = app_module.monta_dto_grupos()
        assert len(todos_jogos) == 2

    def test_no_grupos_global_variable(self):
        """app.py must not have a module-level mutable 'grupos' dict."""
        import inspect
        source = inspect.getsource(app_module)
        # The old pattern was: grupos = {} at module level
        # After refactor there should be no module-level 'grupos = {}'
        assert 'grupos = {}' not in source

    def test_no_todos_jogos_global_variable(self):
        """app.py must not have a module-level mutable 'todos_jogos' list."""
        import inspect
        source = inspect.getsource(app_module)
        assert 'todos_jogos = []' not in source
