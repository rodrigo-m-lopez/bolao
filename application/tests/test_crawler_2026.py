# coding: utf-8
"""Tests for crawler_2026 — seed and result update logic."""
import os
import pytest
import mongomock

import application.crawler_2026 as crawler


def _make_db():
    client = mongomock.MongoClient()
    return client['test']


_UNSET = object()  # sentinel to distinguish "omitted" from explicit None


def _make_match(home_tla, home_short, away_tla, away_short, gols_m=None, gols_v=None,
                home_name=_UNSET, away_name=_UNSET):
    """Build a minimal match dict as returned by football-data.org API.

    home_name/away_name default to home_short/away_short when omitted.
    Pass explicit None to simulate API responses where the key exists but is null.
    """
    return {
        'homeTeam': {'tla': home_tla, 'shortName': home_short,
                     'name': home_name if home_name is not _UNSET else (home_short or 'Team A')},
        'awayTeam': {'tla': away_tla, 'shortName': away_short,
                     'name': away_name if away_name is not _UNSET else (away_short or 'Team B')},
        'utcDate': '2026-06-11T18:00:00Z',
        'group': 'GROUP_A',
        'matchday': 1,
        'venue': 'Stadium',
        'score': {
            'fullTime': {'home': gols_m, 'away': gols_v},
        },
    }


def _insert_selecoes(db, *siglas):
    """Pre-insert seleção docs so _upsert_jogo can resolve references."""
    for sigla in siglas:
        db.selecao.insert_one({'sigla': sigla, 'nome': sigla, 'grupo': ''})


class TestUpsertJogoNullFields:
    """_upsert_jogo must not crash when API returns None for tla/shortName."""

    def test_null_tla_and_null_short_name_raises_type_error_before_fix(self):
        """Reproduces the bug: away team has tla=None and shortName=None (key present, value null)."""
        db = _make_db()
        # Teams exist but API returned null for both tla and shortName
        match = _make_match(
            home_tla='BRA', home_short='Brazil',
            away_tla=None, away_short=None,   # <-- bug trigger
        )
        # Pre-insert home selecao; the away one is missing on purpose to hit the
        # None shortName branch before we even reach the DB lookup.
        _insert_selecoes(db, 'BRA')

        # This should NOT raise TypeError — if it does, the bug is present.
        # After the fix it should just skip the jogo (log a warning) gracefully.
        try:
            crawler._upsert_jogo(db, match)
        except TypeError as exc:
            pytest.fail(f"_upsert_jogo raised TypeError with null shortName: {exc}")

    def test_null_tla_with_valid_short_name_uses_first_three_chars(self):
        """When tla is None but shortName is valid, uses shortName[:3] as sigla."""
        db = _make_db()
        match = _make_match(
            home_tla=None, home_short='Germany',
            away_tla=None, away_short='France',
        )
        _insert_selecoes(db, 'GER', 'FRA')
        crawler._upsert_jogo(db, match)
        assert db.jogo.count_documents({'nome': 'GER x FRA'}) == 1

    def test_both_tbd_teams_inserts_jogo_with_placeholder(self):
        """Both teams TBD → jogo is inserted using the ??? placeholder selecao."""
        db = _make_db()
        match = _make_match(
            home_tla=None, home_short=None,
            away_tla=None, away_short=None,
        )
        crawler._upsert_jogo(db, match)
        assert db.jogo.count_documents({}) == 1, \
            "Jogo com ambos os times TBD deve ser inserido com placeholder"
        assert db.selecao.count_documents({'sigla': '???'}) == 1, \
            "Selecao placeholder ??? deve ser criada"

    def test_confirmed_vs_tbd_inserts_jogo_with_placeholder(self):
        """Confirmed team vs TBD slot → jogo is inserted; TBD side uses ??? placeholder."""
        db = _make_db()
        match = _make_match(
            home_tla='KOR', home_short='Korea Republic',
            away_tla=None,  away_short=None, away_name=None,
        )
        _insert_selecoes(db, 'KOR')
        crawler._upsert_jogo(db, match)
        assert db.jogo.count_documents({}) == 1, \
            "Jogo KOR vs TBD deve ser inserido"
        jogo = db.jogo.find_one({})
        tbd_sel = db.selecao.find_one({'sigla': '???'})
        assert tbd_sel is not None, "Selecao placeholder ??? deve ser criada"
        assert jogo['visitante'] == tbd_sel['_id'], \
            "O visitante TBD deve referenciar a selecao placeholder"

    def test_all_three_fields_null_does_not_crash(self):
        """tla=None, shortName=None, name=None (all keys present with null value) → no crash."""
        db = _make_db()
        match = _make_match(
            home_tla=None, home_short=None, home_name=None,
            away_tla=None, away_short=None, away_name=None,
        )
        try:
            crawler._upsert_jogo(db, match)
        except TypeError as exc:
            pytest.fail(f"_upsert_jogo crashed when all name fields are null: {exc}")

    def test_tbd_placeholder_reutilizado_em_multiplos_jogos(self):
        """Múltiplos jogos TBD compartilham a mesma selecao placeholder ???."""
        db = _make_db()
        _insert_selecoes(db, 'BRA', 'ARG')
        m1 = _make_match('BRA', 'Brazil', None, None, away_name=None)
        m2 = _make_match(None, None, 'ARG', 'Argentina', home_name=None)
        crawler._upsert_jogo(db, m1)
        crawler._upsert_jogo(db, m2)
        assert db.jogo.count_documents({}) == 2
        assert db.selecao.count_documents({'sigla': '???'}) == 1, \
            "Deve existir apenas UM documento placeholder ???"


class TestSeedSelecoes:
    """_seed_selecoes must handle API teams with null tla gracefully."""

    def test_null_tla_uses_short_name_prefix(self):
        """Team with tla=None falls back to shortName[:3].upper()."""
        db = _make_db()
        teams_payload = {
            'teams': [
                {'tla': None, 'shortName': 'Germany', 'name': 'Germany', 'crest': ''},
                {'tla': 'BRA', 'shortName': 'Brazil',  'name': 'Brazil',  'crest': ''},
            ]
        }
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(crawler, '_get', lambda *a, **kw: teams_payload)
            crawler._seed_selecoes(db)

        siglas = {d['sigla'] for d in db.selecao.find()}
        assert 'BRA' in siglas
        assert 'GER' in siglas  # Germany[:3].upper()

    def test_null_tla_and_null_short_name_uses_name_prefix(self):
        """Team with both tla=None and shortName=None uses name[:3].upper()."""
        db = _make_db()
        teams_payload = {
            'teams': [
                {'tla': None, 'shortName': None, 'name': 'France', 'crest': ''},
            ]
        }
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(crawler, '_get', lambda *a, **kw: teams_payload)
            crawler._seed_selecoes(db)

        siglas = {d['sigla'] for d in db.selecao.find()}
        assert 'FRA' in siglas

    def test_all_fields_null_does_not_crash(self):
        """Team with tla=None, shortName=None, name=None → no crash, falls back to '???'."""
        db = _make_db()
        teams_payload = {
            'teams': [
                {'tla': None, 'shortName': None, 'name': None, 'crest': ''},
            ]
        }
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(crawler, '_get', lambda *a, **kw: teams_payload)
            try:
                crawler._seed_selecoes(db)
            except TypeError as exc:
                pytest.fail(f"_seed_selecoes crashed when all name fields are null: {exc}")
