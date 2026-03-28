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
                home_name=_UNSET, away_name=_UNSET,
                stage='GROUP_STAGE', group='GROUP_A', matchday=1, status='SCHEDULED'):
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
        'stage': stage,
        'group': group,
        'matchday': matchday,
        'venue': 'Stadium',
        'status': status,
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


class TestUpsertJogoKnockout:
    """_upsert_jogo deve tratar corretamente jogos de fases eliminatórias."""

    def test_last_16_match_uses_fase_as_grupo(self):
        """Jogo de LAST_16 (group=None) deve ter grupo='Oitavas de Final'."""
        db = _make_db()
        _insert_selecoes(db, 'BRA', 'ARG')
        match = _make_match('BRA', 'Brazil', 'ARG', 'Argentina',
                            stage='LAST_16', group=None, matchday=1)
        crawler._upsert_jogo(db, match)
        jogo = db.jogo.find_one({'nome': 'BRA x ARG'})
        assert jogo is not None
        assert jogo['grupo'] == 'Oitavas de Final'

    def test_quarter_finals_match(self):
        """Jogo de QUARTER_FINALS deve ter grupo='Quartas de Final'."""
        db = _make_db()
        _insert_selecoes(db, 'FRA', 'GER')
        match = _make_match('FRA', 'France', 'GER', 'Germany',
                            stage='QUARTER_FINALS', group=None, matchday=1)
        crawler._upsert_jogo(db, match)
        jogo = db.jogo.find_one({'nome': 'FRA x GER'})
        assert jogo is not None
        assert jogo['grupo'] == 'Quartas de Final'

    def test_semi_finals_match(self):
        """Jogo de SEMI_FINALS deve ter grupo='Semifinal'."""
        db = _make_db()
        _insert_selecoes(db, 'BRA', 'FRA')
        match = _make_match('BRA', 'Brazil', 'FRA', 'France',
                            stage='SEMI_FINALS', group=None, matchday=1)
        crawler._upsert_jogo(db, match)
        jogo = db.jogo.find_one({'nome': 'BRA x FRA'})
        assert jogo is not None
        assert jogo['grupo'] == 'Semifinal'

    def test_third_place_match(self):
        """Jogo de THIRD_PLACE deve ter grupo='Disputa de 3º Lugar'."""
        db = _make_db()
        _insert_selecoes(db, 'GER', 'ARG')
        match = _make_match('GER', 'Germany', 'ARG', 'Argentina',
                            stage='THIRD_PLACE', group=None, matchday=1)
        crawler._upsert_jogo(db, match)
        jogo = db.jogo.find_one({'nome': 'GER x ARG'})
        assert jogo is not None
        assert jogo['grupo'] == 'Disputa de 3º Lugar'

    def test_final_match(self):
        """Jogo de FINAL deve ter grupo='Final'."""
        db = _make_db()
        _insert_selecoes(db, 'BRA', 'FRA')
        match = _make_match('BRA', 'Brazil', 'FRA', 'France',
                            stage='FINAL', group=None, matchday=1)
        crawler._upsert_jogo(db, match)
        jogo = db.jogo.find_one({'nome': 'BRA x FRA'})
        assert jogo is not None
        assert jogo['grupo'] == 'Final'

    def test_group_stage_still_uses_grupo(self):
        """Jogo de GROUP_STAGE continua usando _GRUPOS normalmente."""
        db = _make_db()
        _insert_selecoes(db, 'BRA', 'ARG')
        match = _make_match('BRA', 'Brazil', 'ARG', 'Argentina',
                            stage='GROUP_STAGE', group='GROUP_A', matchday=1)
        crawler._upsert_jogo(db, match)
        jogo = db.jogo.find_one({'nome': 'BRA x ARG'})
        assert jogo is not None
        assert jogo['grupo'] == 'Grupo A'

    def test_unknown_stage_is_ignored(self):
        """Stage desconhecido (ex: QUALIFICATION) não insere jogo."""
        db = _make_db()
        _insert_selecoes(db, 'BRA', 'ARG')
        match = _make_match('BRA', 'Brazil', 'ARG', 'Argentina',
                            stage='QUALIFICATION', group=None, matchday=1)
        crawler._upsert_jogo(db, match)
        assert db.jogo.count_documents({}) == 0

    def test_last_32_match(self):
        """Jogo de LAST_32 deve ter grupo='32 Avos de Final'."""
        db = _make_db()
        _insert_selecoes(db, 'BRA', 'ARG')
        match = _make_match('BRA', 'Brazil', 'ARG', 'Argentina',
                            stage='LAST_32', group=None, matchday=1)
        crawler._upsert_jogo(db, match)
        jogo = db.jogo.find_one({'nome': 'BRA x ARG'})
        assert jogo is not None
        assert jogo['grupo'] == '32 Avos de Final'


class TestSeedJogosSemFiltroStage:
    """_seed_jogos deve buscar jogos de todas as fases, não só GROUP_STAGE."""

    def test_seed_jogos_nao_filtra_por_stage(self):
        """Verifica que _seed_jogos não passa stage como parâmetro da API."""
        db = _make_db()
        _insert_selecoes(db, 'BRA', 'ARG')
        chamadas = []

        def fake_get(endpoint, params=None):
            chamadas.append(params or {})
            return {'matches': [
                _make_match('BRA', 'Brazil', 'ARG', 'Argentina',
                            stage='LAST_16', group=None),
            ]}

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(crawler, '_get', fake_get)
            crawler._seed_jogos(db)

        assert 'stage' not in chamadas[0], \
            "_seed_jogos não deve filtrar por stage — deve buscar todos os jogos"
        assert db.jogo.count_documents({}) == 1


class TestAtualizaResultadosSemFiltroStage:
    """atualiza_resultados deve buscar jogos encerrados de todas as fases."""

    def test_atualiza_resultados_nao_filtra_por_stage(self):
        """Verifica que atualiza_resultados não passa stage como parâmetro."""
        db = _make_db()
        # Pré-inserir jogo de oitavas no banco
        sel_bra = db.selecao.insert_one({'sigla': 'BRA', 'nome': 'Brasil', 'grupo': ''}).inserted_id
        sel_arg = db.selecao.insert_one({'sigla': 'ARG', 'nome': 'Argentina', 'grupo': ''}).inserted_id
        db.jogo.insert_one({
            'nome': 'BRA x ARG', 'competicao': 'Copa do Mundo 2026',
            'grupo': 'Oitavas de Final', 'rodada': 1,
            'mandante': sel_bra, 'visitante': sel_arg,
            'gols_mandante': None, 'gols_visitante': None,
        })

        chamadas = []

        def fake_get(endpoint, params=None):
            chamadas.append(params or {})
            return {'matches': [
                _make_match('BRA', 'Brazil', 'ARG', 'Argentina',
                            gols_m=2, gols_v=1, stage='LAST_16', group=None,
                            status='FINISHED'),
            ]}

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(crawler, '_get', fake_get)
            crawler.atualiza_resultados(db)

        assert 'stage' not in chamadas[0], \
            "atualiza_resultados não deve filtrar por stage"
        jogo = db.jogo.find_one({'nome': 'BRA x ARG'})
        assert jogo['gols_mandante'] == 2
        assert jogo['gols_visitante'] == 1
