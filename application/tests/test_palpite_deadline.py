"""Tests for per-game palpite saving with server-side deadline enforcement."""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from bson import ObjectId

import application.app as app_module

# ── Helpers ───────────────────────────────────────────────────────────────────

FUTURE = datetime(2099, 6, 15, 18, 0, 0)
PAST   = datetime(2000, 6, 15, 18, 0, 0)


def _insert_selecao(nome, sigla, grupo='A'):
    return app_module.tbl_selecao.insert_one({
        'nome': nome, 'sigla': sigla, 'escudo': '', 'grupo': grupo
    }).inserted_id


def _insert_jogo(data, nome=None, selecao_m=None, selecao_v=None, rodada=1):
    if selecao_m is None:
        selecao_m = _insert_selecao('Brasil', 'BRA')
    if selecao_v is None:
        selecao_v = _insert_selecao('Argentina', 'ARG')
    if nome is None:
        nome = 'BRA x ARG'
    return app_module.tbl_jogo.insert_one({
        'nome': nome,
        'grupo': 'A',
        'rodada': rodada,
        'data': data,
        'local': 'Estadio',
        'mandante': selecao_m,
        'visitante': selecao_v,
        'gols_mandante': None,
        'gols_visitante': None,
    }).inserted_id


def _insert_bolao(nome='testbolao'):
    uid = app_module.tbl_usuario.insert_one({
        'nome': 'Test User', 'email': 'test@test.com',
        'primeiro_nome': 'Test', 'sobrenome': 'User',
        'foto': '', 'sexo': 'm'
    }).inserted_id
    bid = app_module.tbl_bolao.insert_one({
        'nome': nome, 'usuario': uid, 'valor': 10,
        'premiacao': 'Premio', 'descricao': ''
    }).inserted_id
    return bid, uid


def _insert_aposta(bolao_id, usuario_id, nome='minha aposta'):
    return app_module.tbl_aposta.insert_one({
        'nome': nome, 'usuario': usuario_id, 'bolao': bolao_id, 'pago': False
    }).inserted_id


def _login(client, email='test@test.com'):
    """Authenticate the test client as the given user."""
    with client.session_transaction() as sess:
        sess['_user_id'] = email
        sess['_fresh'] = True


# ── Unit tests for jogo_ja_iniciou ────────────────────────────────────────────

class TestJogoJaIniciou:
    def test_future_date_returns_false(self):
        assert app_module.jogo_ja_iniciou(FUTURE) is False

    def test_past_date_returns_true(self):
        assert app_module.jogo_ja_iniciou(PAST) is True

    def test_exact_start_time_returns_true(self):
        now = datetime.utcnow()
        with patch('application.app.datetime') as mock_dt:
            mock_dt.utcnow.return_value = now
            assert app_module.jogo_ja_iniciou(now) is True

    def test_one_second_before_start_returns_false(self):
        near_future = datetime.utcnow() + timedelta(seconds=10)
        assert app_module.jogo_ja_iniciou(near_future) is False


# ── Unit tests for insere_palpites ────────────────────────────────────────────

class TestInserePalpites:
    def test_skips_empty_fields(self, flask_app):
        bid, uid = _insert_bolao()
        jid = _insert_jogo(FUTURE)
        aid = _insert_aposta(bid, uid)
        _, todos_jogos = app_module.monta_dto_grupos()
        app_module.insere_palpites(aid, {}, todos_jogos)
        assert app_module.tbl_palpite.find_one({'aposta': aid}) is None

    def test_saves_provided_palpite(self, flask_app):
        bid, uid = _insert_bolao()
        jid = _insert_jogo(FUTURE)
        aid = _insert_aposta(bid, uid)
        _, todos_jogos = app_module.monta_dto_grupos()
        app_module.insere_palpites(aid, {'m' + str(jid): '2', 'v' + str(jid): '1'}, todos_jogos)
        p = app_module.tbl_palpite.find_one({'aposta': aid, 'jogo': jid})
        assert p is not None
        assert p['gols_mandante'] == 2
        assert p['gols_visitante'] == 1

    def test_skips_games_already_started(self, flask_app):
        bid, uid = _insert_bolao()
        jid = _insert_jogo(PAST)
        aid = _insert_aposta(bid, uid)
        _, todos_jogos = app_module.monta_dto_grupos()
        app_module.insere_palpites(aid, {'m' + str(jid): '3', 'v' + str(jid): '0'}, todos_jogos)
        assert app_module.tbl_palpite.find_one({'aposta': aid, 'jogo': jid}) is None

    def test_saves_only_unlocked_games_in_mixed_list(self, flask_app):
        bid, uid = _insert_bolao()
        sm = _insert_selecao('Brasil', 'BRA')
        sv = _insert_selecao('Argentina', 'ARG')
        jid_future = _insert_jogo(FUTURE, nome='BRA x ARG', selecao_m=sm, selecao_v=sv, rodada=1)
        jid_past   = _insert_jogo(PAST,   nome='ARG x BRA', selecao_m=sv, selecao_v=sm, rodada=2)
        aid = _insert_aposta(bid, uid)
        _, todos_jogos = app_module.monta_dto_grupos()
        form = {
            'm' + str(jid_future): '1', 'v' + str(jid_future): '0',
            'm' + str(jid_past):   '2', 'v' + str(jid_past):   '1',
        }
        app_module.insere_palpites(aid, form, todos_jogos)
        assert app_module.tbl_palpite.find_one({'aposta': aid, 'jogo': jid_future}) is not None
        assert app_module.tbl_palpite.find_one({'aposta': aid, 'jogo': jid_past})   is None


# ── Integration tests for salvar_palpite endpoint ─────────────────────────────

class TestSalvarPalpiteEndpoint:

    def test_save_before_start_returns_ok(self, client):
        bid, uid = _insert_bolao()
        jid = _insert_jogo(FUTURE)
        aid = _insert_aposta(bid, uid)
        _login(client)

        rv = client.post('/testbolao/salvar_palpite/minha aposta',
                         data={'id_jogo': str(jid), 'gols_mandante': '2', 'gols_visitante': '1'})

        assert rv.status_code == 200
        data = rv.get_json()
        assert data['ok'] is True
        p = app_module.tbl_palpite.find_one({'aposta': aid, 'jogo': jid})
        assert p['gols_mandante'] == 2
        assert p['gols_visitante'] == 1

    def test_save_after_start_returns_403(self, client):
        bid, uid = _insert_bolao()
        jid = _insert_jogo(PAST)
        aid = _insert_aposta(bid, uid)
        _login(client)

        rv = client.post('/testbolao/salvar_palpite/minha aposta',
                         data={'id_jogo': str(jid), 'gols_mandante': '2', 'gols_visitante': '1'})

        assert rv.status_code == 403
        assert rv.get_json()['ok'] is False
        assert app_module.tbl_palpite.find_one({'aposta': aid, 'jogo': jid}) is None

    def test_save_unauthenticated_redirects(self, client):
        rv = client.post('/testbolao/salvar_palpite/qualquer',
                         data={'id_jogo': str(ObjectId()), 'gols_mandante': '1', 'gols_visitante': '0'})
        assert rv.status_code == 302

    def test_save_invalid_score_string_returns_400(self, client):
        bid, uid = _insert_bolao()
        jid = _insert_jogo(FUTURE)
        _insert_aposta(bid, uid)
        _login(client)

        rv = client.post('/testbolao/salvar_palpite/minha aposta',
                         data={'id_jogo': str(jid), 'gols_mandante': 'abc', 'gols_visitante': '1'})
        assert rv.status_code == 400
        assert rv.get_json()['ok'] is False

    def test_save_negative_score_returns_400(self, client):
        bid, uid = _insert_bolao()
        jid = _insert_jogo(FUTURE)
        _insert_aposta(bid, uid)
        _login(client)

        rv = client.post('/testbolao/salvar_palpite/minha aposta',
                         data={'id_jogo': str(jid), 'gols_mandante': '-1', 'gols_visitante': '0'})
        assert rv.status_code == 400

    def test_save_invalid_jogo_id_returns_400(self, client):
        bid, uid = _insert_bolao()
        _insert_aposta(bid, uid)
        _login(client)

        rv = client.post('/testbolao/salvar_palpite/minha aposta',
                         data={'id_jogo': 'not-an-objectid', 'gols_mandante': '1', 'gols_visitante': '0'})
        assert rv.status_code == 400

    def test_update_existing_palpite_before_start(self, client):
        bid, uid = _insert_bolao()
        jid = _insert_jogo(FUTURE)
        aid = _insert_aposta(bid, uid)
        app_module.tbl_palpite.insert_one(
            {'aposta': aid, 'jogo': jid, 'gols_mandante': 0, 'gols_visitante': 0}
        )
        _login(client)

        rv = client.post('/testbolao/salvar_palpite/minha aposta',
                         data={'id_jogo': str(jid), 'gols_mandante': '3', 'gols_visitante': '2'})

        assert rv.status_code == 200
        p = app_module.tbl_palpite.find_one({'aposta': aid, 'jogo': jid})
        assert p['gols_mandante'] == 3
        assert p['gols_visitante'] == 2
        # No duplicate records
        assert app_module.tbl_palpite.count_documents({'aposta': aid, 'jogo': jid}) == 1

    def test_uses_server_time_not_client(self, client):
        """Patching server datetime to be after game start must block the save."""
        bid, uid = _insert_bolao()
        near_future = datetime.utcnow() + timedelta(seconds=30)
        jid = _insert_jogo(near_future)
        _insert_aposta(bid, uid)
        _login(client)

        with patch('application.app.datetime') as mock_dt:
            mock_dt.utcnow.return_value = near_future + timedelta(seconds=1)
            rv = client.post('/testbolao/salvar_palpite/minha aposta',
                             data={'id_jogo': str(jid), 'gols_mandante': '1', 'gols_visitante': '0'})

        assert rv.status_code == 403

    def test_nonexistent_jogo_returns_404(self, client):
        bid, uid = _insert_bolao()
        _insert_aposta(bid, uid)
        _login(client)

        rv = client.post('/testbolao/salvar_palpite/minha aposta',
                         data={'id_jogo': str(ObjectId()), 'gols_mandante': '1', 'gols_visitante': '0'})
        assert rv.status_code == 404


# ── Integration tests for salvar_palpites (bulk endpoint) ────────────────────

class TestSalvarPalpitesBulk:
    """Testa o endpoint POST /<bolao>/salvar_palpites/<nome_aposta>."""

    def _post(self, client, bolao, nome_aposta, payload):
        import json
        return client.post(
            '/{}/salvar_palpites/{}'.format(bolao, nome_aposta),
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_salva_todos_jogos_desbloqueados(self, client):
        bid, uid = _insert_bolao()
        sm = _insert_selecao('Brasil', 'BRA')
        sv = _insert_selecao('Argentina', 'ARG')
        jid1 = _insert_jogo(FUTURE, nome='BRA x ARG', selecao_m=sm, selecao_v=sv, rodada=1)
        jid2 = _insert_jogo(FUTURE, nome='ARG x BRA', selecao_m=sv, selecao_v=sm, rodada=2)
        aid = _insert_aposta(bid, uid)
        _login(client)

        rv = self._post(client, 'testbolao', 'minha aposta', [
            {'id_jogo': str(jid1), 'gols_mandante': '2', 'gols_visitante': '1'},
            {'id_jogo': str(jid2), 'gols_mandante': '0', 'gols_visitante': '0'},
        ])

        assert rv.status_code == 200
        data = rv.get_json()
        assert len(data['salvos']) == 2
        assert len(data['bloqueados']) == 0
        assert len(data['erros']) == 0
        assert app_module.tbl_palpite.count_documents({'aposta': aid}) == 2

    def test_bloqueia_jogo_iniciado_salva_restantes(self, client):
        bid, uid = _insert_bolao()
        sm = _insert_selecao('Brasil', 'BRA')
        sv = _insert_selecao('Argentina', 'ARG')
        jid_ok   = _insert_jogo(FUTURE, nome='BRA x ARG', selecao_m=sm, selecao_v=sv, rodada=1)
        jid_late = _insert_jogo(PAST,   nome='ARG x BRA', selecao_m=sv, selecao_v=sm, rodada=2)
        aid = _insert_aposta(bid, uid)
        _login(client)

        rv = self._post(client, 'testbolao', 'minha aposta', [
            {'id_jogo': str(jid_ok),   'gols_mandante': '2', 'gols_visitante': '1'},
            {'id_jogo': str(jid_late), 'gols_mandante': '3', 'gols_visitante': '0'},
        ])

        assert rv.status_code == 200
        data = rv.get_json()
        assert str(jid_ok) in data['salvos']
        assert len(data['bloqueados']) == 1
        assert data['bloqueados'][0]['id_jogo'] == str(jid_late)
        assert app_module.tbl_palpite.find_one({'aposta': aid, 'jogo': jid_ok})   is not None
        assert app_module.tbl_palpite.find_one({'aposta': aid, 'jogo': jid_late}) is None

    def test_todos_bloqueados_retorna_lista_vazia_de_salvos(self, client):
        bid, uid = _insert_bolao()
        jid = _insert_jogo(PAST)
        _insert_aposta(bid, uid)
        _login(client)

        rv = self._post(client, 'testbolao', 'minha aposta', [
            {'id_jogo': str(jid), 'gols_mandante': '1', 'gols_visitante': '0'},
        ])

        assert rv.status_code == 200
        data = rv.get_json()
        assert data['salvos'] == []
        assert len(data['bloqueados']) == 1

    def test_placar_invalido_reportado_em_erros(self, client):
        bid, uid = _insert_bolao()
        sm = _insert_selecao('Brasil', 'BRA')
        sv = _insert_selecao('Argentina', 'ARG')
        jid_ok  = _insert_jogo(FUTURE, nome='BRA x ARG', selecao_m=sm, selecao_v=sv, rodada=1)
        jid_err = _insert_jogo(FUTURE, nome='ARG x BRA', selecao_m=sv, selecao_v=sm, rodada=2)
        _insert_aposta(bid, uid)
        _login(client)

        rv = self._post(client, 'testbolao', 'minha aposta', [
            {'id_jogo': str(jid_ok),  'gols_mandante': '1', 'gols_visitante': '0'},
            {'id_jogo': str(jid_err), 'gols_mandante': 'abc', 'gols_visitante': '0'},
        ])

        data = rv.get_json()
        assert len(data['salvos']) == 1
        assert len(data['erros']) == 1

    def test_placar_negativo_reportado_em_erros(self, client):
        bid, uid = _insert_bolao()
        jid = _insert_jogo(FUTURE)
        _insert_aposta(bid, uid)
        _login(client)

        rv = self._post(client, 'testbolao', 'minha aposta', [
            {'id_jogo': str(jid), 'gols_mandante': '-1', 'gols_visitante': '0'},
        ])

        data = rv.get_json()
        assert data['salvos'] == []
        assert len(data['erros']) == 1

    def test_upsert_palpite_existente(self, client):
        bid, uid = _insert_bolao()
        jid = _insert_jogo(FUTURE)
        aid = _insert_aposta(bid, uid)
        app_module.tbl_palpite.insert_one(
            {'aposta': aid, 'jogo': jid, 'gols_mandante': 0, 'gols_visitante': 0}
        )
        _login(client)

        rv = self._post(client, 'testbolao', 'minha aposta', [
            {'id_jogo': str(jid), 'gols_mandante': '3', 'gols_visitante': '2'},
        ])

        assert rv.get_json()['salvos'] == [str(jid)]
        p = app_module.tbl_palpite.find_one({'aposta': aid, 'jogo': jid})
        assert p['gols_mandante'] == 3
        assert app_module.tbl_palpite.count_documents({'aposta': aid, 'jogo': jid}) == 1

    def test_sem_autenticacao_redireciona(self, client):
        rv = self._post(client, 'testbolao', 'qualquer', [])
        assert rv.status_code == 302

    def test_payload_invalido_retorna_400(self, client):
        bid, uid = _insert_bolao()
        _insert_aposta(bid, uid)
        _login(client)

        rv = client.post('/testbolao/salvar_palpites/minha aposta',
                         data='nao-e-json', content_type='application/json')
        assert rv.status_code == 400

    def test_usa_hora_do_servidor_para_bloquear(self, client):
        """Jogo aparentemente futuro fica bloqueado se o relógio do servidor avança."""
        bid, uid = _insert_bolao()
        near_future = datetime.utcnow() + timedelta(seconds=30)
        jid = _insert_jogo(near_future)
        _insert_aposta(bid, uid)
        _login(client)

        with patch('application.app.datetime') as mock_dt:
            mock_dt.utcnow.return_value = near_future + timedelta(seconds=1)
            rv = self._post(client, 'testbolao', 'minha aposta', [
                {'id_jogo': str(jid), 'gols_mandante': '1', 'gols_visitante': '0'},
            ])

        data = rv.get_json()
        assert data['salvos'] == []
        assert len(data['bloqueados']) == 1


# ── Integration tests for nova_aposta with partial palpites ───────────────────

class TestNovaApostaPartialPalpites:

    def test_aposta_criada_sem_palpites(self, client):
        bid, uid = _insert_bolao()
        _insert_jogo(FUTURE)
        _login(client)

        rv = client.post('/testbolao/nova_aposta', data={'inputNome': 'minha aposta'})

        assert rv.status_code == 302
        assert 'editar_palpites' in rv.headers['Location']
        assert app_module.tbl_aposta.find_one({'nome': 'minha aposta', 'bolao': bid}) is not None

    def test_palpite_parcial_salvo_e_jogo_iniciado_ignorado(self, client):
        bid, uid = _insert_bolao()
        sm = _insert_selecao('Brasil', 'BRA')
        sv = _insert_selecao('Argentina', 'ARG')
        jid_ok   = _insert_jogo(FUTURE, nome='BRA x ARG', selecao_m=sm, selecao_v=sv, rodada=1)
        jid_late = _insert_jogo(PAST,   nome='ARG x BRA', selecao_m=sv, selecao_v=sm, rodada=2)
        _login(client)

        rv = client.post('/testbolao/nova_aposta', data={
            'inputNome': 'minha aposta',
            'm' + str(jid_ok):   '2', 'v' + str(jid_ok):   '1',
            'm' + str(jid_late): '3', 'v' + str(jid_late): '0',
        })

        assert rv.status_code == 302
        aposta = app_module.tbl_aposta.find_one({'nome': 'minha aposta', 'bolao': bid})
        assert app_module.tbl_palpite.find_one({'aposta': aposta['_id'], 'jogo': jid_ok}) is not None
        assert app_module.tbl_palpite.find_one({'aposta': aposta['_id'], 'jogo': jid_late}) is None

    def test_redirect_destination_is_editar_palpites(self, client):
        bid, uid = _insert_bolao()
        _insert_jogo(FUTURE)
        _login(client)

        rv = client.post('/testbolao/nova_aposta', data={'inputNome': 'minha aposta'})

        assert rv.status_code == 302
        location = rv.headers['Location']
        assert 'editar_palpites' in location
        assert 'minha%20aposta' in location or 'minha+aposta' in location or 'minha aposta' in location
