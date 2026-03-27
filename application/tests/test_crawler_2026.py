# coding: utf-8
"""Tests for crawler_2026 — seed and result update logic."""
import os
import pytest
import mongomock

import application.crawler_2026 as crawler


def _make_db():
    client = mongomock.MongoClient()
    return client['test']


def _make_match(home_tla, home_short, away_tla, away_short, gols_m=None, gols_v=None):
    """Build a minimal match dict as returned by football-data.org API."""
    return {
        'homeTeam': {'tla': home_tla, 'shortName': home_short, 'name': home_short or 'Team A'},
        'awayTeam': {'tla': away_tla, 'shortName': away_short, 'name': away_short or 'Team B'},
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

    def test_both_null_tla_and_null_short_falls_back_to_unknown(self):
        """When both tla and shortName are None the jogo is skipped (no crash)."""
        db = _make_db()
        match = _make_match(
            home_tla=None, home_short=None,
            away_tla=None, away_short=None,
        )
        # No selecoes inserted — after the fix the function should log a warning
        # and return without inserting anything.
        crawler._upsert_jogo(db, match)
        assert db.jogo.count_documents({}) == 0

    def test_null_home_tla_null_short_with_away_valid(self):
        """Home team with both null, away team valid → skipped gracefully."""
        db = _make_db()
        match = _make_match(
            home_tla=None, home_short=None,
            away_tla='ARG', away_short='Argentina',
        )
        _insert_selecoes(db, 'ARG')
        crawler._upsert_jogo(db, match)
        assert db.jogo.count_documents({}) == 0


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
