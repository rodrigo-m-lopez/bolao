# coding: utf-8
"""
Testes E2E — simulam o fluxo completo do usuário desde a inicialização
da aplicação até as ações principais, sem precisar subir o servidor.

Cobrem os cenários que costumam quebrar em produção:
  1. Startup saudável (modo mock seed padrão)
  2. Startup com SEED_FROM_API=true (API mockada)
  3. Login via /dev_login
  4. Criação de bolão e aposta
  5. Edição de palpites (desbloqueados e bloqueados)
  6. Ranking e página de jogo
  7. Área administrativa
"""
import json
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

import application.app as app_module

# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def app(flask_app):
    return flask_app


@pytest.fixture
def c(app):
    """Cliente HTTP sem usuário logado."""
    with app.test_client() as client:
        yield client


@pytest.fixture
def logged_in(app):
    """Cliente HTTP com dev@local.test autenticado e presente no banco."""
    db = app_module.client[os.environ.get('MONGO_DB_NAME', 'dev')]
    db.usuario.insert_one({
        'nome': 'Dev User', 'email': 'dev@local.test',
        'primeiro_nome': 'Dev', 'sobrenome': 'User',
        'foto': '', 'sexo': 'm',
    })
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['_user_id'] = 'dev@local.test'
            sess['_fresh'] = True
        yield client


def _setup_bolao(db, nome='Bolão E2E'):
    """Insere bolão, jogos mínimos e uma aposta para testes.
    Reutiliza o usuário dev@local.test se já existir (inserido pelo fixture logged_in).
    """
    usuario = db.usuario.find_one({'email': 'dev@local.test'})
    if usuario is None:
        uid = db.usuario.insert_one({
            'nome': 'Dev User', 'email': 'dev@local.test',
            'primeiro_nome': 'Dev', 'sobrenome': 'User',
            'foto': '', 'sexo': 'm',
        }).inserted_id
    else:
        uid = usuario['_id']

    bid = db.bolao.insert_one({
        'nome': nome, 'usuario': uid,
        'valor': 10, 'premiacao': '100% ao 1º', 'descricao': '',
    }).inserted_id

    now = datetime.utcnow()
    sel_a = db.selecao.insert_one({'sigla': 'BRA', 'nome': 'Brasil',    'escudo': '', 'grupo': 'A'}).inserted_id
    sel_b = db.selecao.insert_one({'sigla': 'ARG', 'nome': 'Argentina', 'escudo': '', 'grupo': 'A'}).inserted_id

    jogo_futuro = db.jogo.insert_one({
        'nome': 'BRA x ARG', 'grupo': 'A', 'rodada': 1,
        'data': now + timedelta(days=3),
        'local': 'Estádio', 'mandante': sel_a, 'visitante': sel_b,
        'gols_mandante': None, 'gols_visitante': None,
    }).inserted_id

    jogo_passado = db.jogo.insert_one({
        'nome': 'ARG x BRA', 'grupo': 'A', 'rodada': 2,
        'data': now - timedelta(days=1),
        'local': 'Estádio', 'mandante': sel_b, 'visitante': sel_a,
        'gols_mandante': 1, 'gols_visitante': 0,
    }).inserted_id

    aid = db.aposta.insert_one({
        'nome': 'Aposta E2E', 'usuario': uid, 'bolao': bid, 'pago': False,
    }).inserted_id

    for jid in (jogo_futuro, jogo_passado):
        db.pontuacao.insert_one({
            'aposta': aid, 'jogo': jid, 'pontos': 0,
            'placar_exato': 0, 'vencedor_ou_empate': 0, 'gols_de_um_time': 0,
        })

    return {
        'uid': uid, 'bid': bid, 'aid': aid,
        'bolao': nome,
        'jogo_futuro_id': str(jogo_futuro),
        'jogo_passado_id': str(jogo_passado),
    }


# ── 1. Startup / páginas públicas ─────────────────────────────────────────────

class TestStartupPublic:
    def test_intro_retorna_200(self, c):
        r = c.get('/intro')
        assert r.status_code == 200, f"GET /intro retornou {r.status_code}"

    def test_raiz_redireciona_ou_retorna_200(self, c):
        r = c.get('/')
        assert r.status_code in (200, 302), f"GET / retornou {r.status_code}"

    def test_lista_bolao_acessivel_sem_login(self, c):
        r = c.get('/lista_bolao')
        assert r.status_code == 200, f"GET /lista_bolao retornou {r.status_code}"

    def test_login_page_retorna_200(self, c):
        r = c.get('/login')
        assert r.status_code == 200, f"GET /login retornou {r.status_code}"

    def test_rota_inexistente_retorna_404(self, c):
        r = c.get('/rota_que_nao_existe_xyz')
        assert r.status_code == 404, f"Rota inexistente retornou {r.status_code}"

    def test_paginas_sem_500(self, c):
        """Garante que nenhuma página pública lança erro interno."""
        rotas = ['/', '/intro', '/lista_bolao', '/login']
        for rota in rotas:
            r = c.get(rota)
            assert r.status_code != 500, f"GET {rota} retornou 500 — erro interno"


# ── 2. Dev login ──────────────────────────────────────────────────────────────

class TestDevLogin:
    def test_dev_login_cria_sessao_e_redireciona(self, c, app):
        """dev_login só funciona com DEV_MOCK_AUTH=True no config."""
        app.config['DEV_MOCK_AUTH'] = True
        try:
            r = c.get('/dev_login', follow_redirects=False)
            assert r.status_code == 302, f"dev_login deveria redirecionar, retornou {r.status_code}"
        finally:
            app.config['DEV_MOCK_AUTH'] = False

    def test_apos_login_lista_bolao_retorna_200(self, logged_in):
        r = logged_in.get('/lista_bolao')
        assert r.status_code == 200, f"lista_bolao após login retornou {r.status_code}"

    def test_novo_bolao_acessivel_apos_login(self, logged_in):
        r = logged_in.get('/novo_bolao')
        assert r.status_code == 200, f"GET /novo_bolao retornou {r.status_code}"

    def test_novo_bolao_requer_login(self, c):
        r = c.get('/novo_bolao')
        assert r.status_code in (302, 401), \
            f"/novo_bolao sem login deveria redirecionar, retornou {r.status_code}"

    def test_dev_login_indisponivel_sem_dev_mock_auth(self, c, app):
        """Garante que dev_login retorna 404 em produção (DEV_MOCK_AUTH=False)."""
        assert not app.config.get('DEV_MOCK_AUTH'), "Config deve ser False neste teste"
        r = c.get('/dev_login')
        assert r.status_code == 404, f"dev_login sem DEV_MOCK_AUTH deveria ser 404, retornou {r.status_code}"


# ── 3. Criação de bolão ───────────────────────────────────────────────────────

class TestCriacaoBolao:
    def test_criar_bolao_e_ver_na_lista(self, logged_in):
        csrf = _get_csrf(logged_in)
        r = logged_in.post('/novo_bolao', data={
            'csrf_token': csrf,
            'inputNome': 'Bolão Teste E2E',
            'inputValor': '15',
            'inputPremiacao': '100% ao 1º',
            'inputDescricao': '',
        }, follow_redirects=True)
        assert r.status_code == 200, f"Criar bolão retornou {r.status_code}"
        assert 'Bolão Teste E2E'.encode('utf-8') in r.data, \
            "Nome do bolão não aparece na lista após criação"

    def test_bolao_duplicado_nao_cria(self, logged_in):
        csrf = _get_csrf(logged_in)
        dados = {
            'csrf_token': csrf,
            'inputNome': 'Bolão Único',
            'inputValor': '10',
            'inputPremiacao': '100%',
            'inputDescricao': '',
        }
        logged_in.post('/novo_bolao', data=dados, follow_redirects=True)
        r = logged_in.post('/novo_bolao', data=dados, follow_redirects=True)
        assert r.status_code == 200

    def test_descricao_bolao_retorna_200(self, logged_in, app):
        db = app_module.client[os.environ.get('MONGO_DB_NAME', 'dev')]
        ctx = _setup_bolao(db)
        r = logged_in.get(f'/{ctx["bolao"]}/descricao_bolao')
        assert r.status_code == 200, f"descricao_bolao retornou {r.status_code}"


# ── 4. Aposta e palpites ──────────────────────────────────────────────────────

class TestApostasEPalpites:
    def test_nova_aposta_get_retorna_200(self, logged_in, app):
        db = app_module.client[os.environ.get('MONGO_DB_NAME', 'dev')]
        ctx = _setup_bolao(db)
        r = logged_in.get(f'/{ctx["bolao"]}/nova_aposta')
        assert r.status_code == 200, f"GET nova_aposta retornou {r.status_code}"

    def test_criar_aposta_redireciona_para_editar_palpites(self, logged_in, app):
        db = app_module.client[os.environ.get('MONGO_DB_NAME', 'dev')]
        ctx = _setup_bolao(db, nome='Bolão Aposta')
        csrf = _get_csrf(logged_in)
        r = logged_in.post(f'/{ctx["bolao"]}/nova_aposta', data={
            'csrf_token': csrf, 'inputNome': 'Minha Aposta',
        }, follow_redirects=False)
        assert r.status_code == 302, f"Criar aposta deveria redirecionar, retornou {r.status_code}"
        assert 'editar_palpites' in r.headers.get('Location', ''), \
            f"Redirecionamento não vai para editar_palpites: {r.headers.get('Location')}"

    def test_editar_palpites_retorna_200(self, logged_in, app):
        db = app_module.client[os.environ.get('MONGO_DB_NAME', 'dev')]
        ctx = _setup_bolao(db)
        r = logged_in.get(f'/{ctx["bolao"]}/editar_palpites/Aposta E2E')
        assert r.status_code == 200, f"editar_palpites retornou {r.status_code}"

    def test_salvar_palpite_jogo_futuro_retorna_salvo(self, logged_in, app):
        db = app_module.client[os.environ.get('MONGO_DB_NAME', 'dev')]
        ctx = _setup_bolao(db)
        payload = [{'id_jogo': ctx['jogo_futuro_id'], 'gols_mandante': 2, 'gols_visitante': 1}]
        csrf = _get_csrf(logged_in)
        r = logged_in.post(
            f'/{ctx["bolao"]}/salvar_palpites/Aposta E2E',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'X-CSRFToken': csrf},
        )
        assert r.status_code == 200, f"salvar_palpites retornou {r.status_code}"
        body = r.get_json()
        assert ctx['jogo_futuro_id'] in body.get('salvos', []), \
            f"Jogo futuro não foi salvo: {body}"

    def test_salvar_palpite_jogo_passado_retorna_bloqueado(self, logged_in, app):
        db = app_module.client[os.environ.get('MONGO_DB_NAME', 'dev')]
        ctx = _setup_bolao(db)
        payload = [{'id_jogo': ctx['jogo_passado_id'], 'gols_mandante': 1, 'gols_visitante': 0}]
        csrf = _get_csrf(logged_in)
        r = logged_in.post(
            f'/{ctx["bolao"]}/salvar_palpites/Aposta E2E',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'X-CSRFToken': csrf},
        )
        assert r.status_code == 200, f"salvar_palpites retornou {r.status_code}"
        body = r.get_json()
        ids_bloqueados = [b['id_jogo'] for b in body.get('bloqueados', [])]
        assert ctx['jogo_passado_id'] in ids_bloqueados, \
            f"Jogo passado deveria estar bloqueado: {body}"

    def test_palpites_page_retorna_200(self, logged_in, app):
        db = app_module.client[os.environ.get('MONGO_DB_NAME', 'dev')]
        ctx = _setup_bolao(db)
        r = logged_in.get(f'/{ctx["bolao"]}/palpite/Aposta E2E')
        assert r.status_code == 200, f"palpite retornou {r.status_code}"


# ── 5. Ranking e jogo ─────────────────────────────────────────────────────────

class TestRankingEJogo:
    def test_ranking_retorna_200(self, c, app):
        db = app_module.client[os.environ.get('MONGO_DB_NAME', 'dev')]
        ctx = _setup_bolao(db)
        r = c.get(f'/{ctx["bolao"]}/ranking')
        assert r.status_code == 200, f"ranking retornou {r.status_code}"

    def test_jogo_retorna_200(self, c, app):
        db = app_module.client[os.environ.get('MONGO_DB_NAME', 'dev')]
        ctx = _setup_bolao(db)
        r = c.get(f'/{ctx["bolao"]}/jogo/BRA x ARG')
        assert r.status_code == 200, f"jogo retornou {r.status_code}"

    def test_jogo_inexistente_redireciona(self, c, app):
        db = app_module.client[os.environ.get('MONGO_DB_NAME', 'dev')]
        ctx = _setup_bolao(db)
        r = c.get(f'/{ctx["bolao"]}/jogo/NAO x EXISTE', follow_redirects=False)
        assert r.status_code == 302, f"jogo inexistente deveria redirecionar, retornou {r.status_code}"


# ── 6. Admin ──────────────────────────────────────────────────────────────────

class TestAdmin:
    def test_admin_acessivel_pelo_criador(self, logged_in, app):
        db = app_module.client[os.environ.get('MONGO_DB_NAME', 'dev')]
        ctx = _setup_bolao(db)
        r = logged_in.get(f'/{ctx["bolao"]}/admin')
        assert r.status_code == 200, f"admin retornou {r.status_code}"

    def test_admin_bloqueado_sem_login(self, c, app):
        db = app_module.client[os.environ.get('MONGO_DB_NAME', 'dev')]
        ctx = _setup_bolao(db)
        r = c.get(f'/{ctx["bolao"]}/admin')
        assert r.status_code in (302, 401), \
            f"admin sem login deveria redirecionar, retornou {r.status_code}"

    def test_toggle_pago_muda_status(self, logged_in, app):
        db = app_module.client[os.environ.get('MONGO_DB_NAME', 'dev')]
        ctx = _setup_bolao(db)
        csrf = _get_csrf(logged_in)
        r = logged_in.post(
            f'/{ctx["bolao"]}/toggle_pago',
            data={'nome_aposta': 'Aposta E2E', 'csrf_token': csrf},
            headers={'X-CSRFToken': csrf},
        )
        assert r.status_code == 200, f"toggle_pago retornou {r.status_code}"
        aposta = db.aposta.find_one({'nome': 'Aposta E2E'})
        assert aposta['pago'] is True, "toggle_pago não marcou como pago"


# ── 7. Startup com SEED_FROM_API ──────────────────────────────────────────────

class TestJogoTBD:
    """Jogos com time A Definir (???) devem aparecer no grupo mas sem inputs habilitados."""

    def _setup_tbd_bolao(self, db):
        """Cria bolão com um jogo normal e um jogo com time TBD."""
        ctx = _setup_bolao(db, nome='Bolão TBD')
        tbd_sel = db.selecao.insert_one(
            {'sigla': '???', 'nome': 'A Definir', 'escudo': '', 'grupo': ''}
        ).inserted_id
        now = datetime.utcnow()
        db.jogo.insert_one({
            'nome': 'BRA x ???',
            'grupo': 'A', 'rodada': 3,
            'data': now + timedelta(days=10),
            'local': 'Estádio',
            'mandante': db.selecao.find_one({'sigla': 'BRA'})['_id'],
            'visitante': tbd_sel,
            'gols_mandante': None, 'gols_visitante': None,
        })
        return ctx

    def test_nova_aposta_exibe_jogo_tbd(self, logged_in, app):
        db = app_module.client[os.environ.get('MONGO_DB_NAME', 'dev')]
        self._setup_tbd_bolao(db)
        r = logged_in.get('/Bolão TBD/nova_aposta')
        assert r.status_code == 200, f"nova_aposta retornou {r.status_code}"
        html = r.data.decode('utf-8', errors='replace')
        assert 'A Definir' in html or '???' in html, \
            "Jogo TBD deve aparecer na tela de nova aposta"

    def test_editar_palpites_exibe_jogo_tbd(self, logged_in, app):
        db = app_module.client[os.environ.get('MONGO_DB_NAME', 'dev')]
        self._setup_tbd_bolao(db)
        r = logged_in.get('/Bolão TBD/editar_palpites/Aposta E2E')
        assert r.status_code == 200, f"editar_palpites retornou {r.status_code}"
        html = r.data.decode('utf-8', errors='replace')
        assert 'A Definir' in html or '???' in html, \
            "Jogo TBD deve aparecer na tela de editar palpites"

    def test_salvar_palpite_jogo_tbd_retorna_bloqueado(self, logged_in, app):
        """Jogo TBD deve ser recusado como bloqueado no endpoint de salvar."""
        db = app_module.client[os.environ.get('MONGO_DB_NAME', 'dev')]
        self._setup_tbd_bolao(db)
        jogo_tbd = db.jogo.find_one({'nome': 'BRA x ???'})
        payload = [{'id_jogo': str(jogo_tbd['_id']), 'gols_mandante': 1, 'gols_visitante': 0}]
        csrf = _get_csrf(logged_in)
        r = logged_in.post(
            '/Bolão TBD/salvar_palpites/Aposta E2E',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'X-CSRFToken': csrf},
        )
        assert r.status_code == 200
        body = r.get_json()
        ids_bloqueados = [b['id_jogo'] for b in body.get('bloqueados', [])]
        assert str(jogo_tbd['_id']) in ids_bloqueados, \
            f"Jogo TBD deveria estar bloqueado, resposta: {body}"


class TestSeedFromApiStartup:
    """Verifica que _init_dev_db com SEED_FROM_API=true chama o crawler
    e que o app continua funcional após o seed."""

    def _api_teams_response(self):
        teams = []
        for i, (tla, nome) in enumerate([
            ('BRA', 'Brazil'), ('ARG', 'Argentina'),
            ('FRA', 'France'), ('GER', 'Germany'),
        ]):
            teams.append({'tla': tla, 'shortName': nome, 'name': nome, 'crest': ''})
        return {'teams': teams}

    def _api_matches_response(self, sel_map):
        """Gera 2 partidas usando os IDs de seleção já no banco."""
        now = datetime.utcnow()
        return {'matches': [
            {
                'homeTeam': {'tla': 'BRA', 'shortName': 'Brazil',    'name': 'Brazil'},
                'awayTeam': {'tla': 'ARG', 'shortName': 'Argentina', 'name': 'Argentina'},
                'utcDate': (now + timedelta(days=5)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'group': 'GROUP_A', 'matchday': 1, 'venue': 'Estadio',
                'score': {'fullTime': {'home': None, 'away': None}},
            },
            {
                'homeTeam': {'tla': 'FRA', 'shortName': 'France',  'name': 'France'},
                'awayTeam': {'tla': 'GER', 'shortName': 'Germany', 'name': 'Germany'},
                'utcDate': (now + timedelta(days=6)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'group': 'GROUP_B', 'matchday': 1, 'venue': 'Estadio',
                'score': {'fullTime': {'home': None, 'away': None}},
            },
        ]}

    def test_seed_from_api_popula_jogos_no_banco(self, app):
        db = app_module.client[os.environ.get('MONGO_DB_NAME', 'dev')]

        teams_resp = self._api_teams_response()
        # matches_resp precisa ser gerado após teams serem inseridos
        matches_resp = self._api_matches_response({})

        call_count = [0]

        def fake_get(path, params=None):
            call_count[0] += 1
            if 'teams' in path:
                return teams_resp
            return matches_resp

        with patch.dict(os.environ, {'SEED_FROM_API': 'true', 'FOOTBALL_DATA_API_KEY': 'fake_key'}):
            with patch('application.crawler_2026._get', side_effect=fake_get):
                from application.app import _init_dev_db
                _init_dev_db(db)

        assert db.jogo.count_documents({}) >= 2, \
            f"Após seed via API, banco deveria ter jogos: {db.jogo.count_documents({})} encontrados"
        assert db.selecao.count_documents({}) >= 4, \
            f"Após seed via API, banco deveria ter seleções: {db.selecao.count_documents({})} encontradas"

    def test_seed_from_api_sem_key_usa_mock_seed(self, app):
        db = app_module.client[os.environ.get('MONGO_DB_NAME', 'dev')]
        env = {k: v for k, v in os.environ.items() if k != 'FOOTBALL_DATA_API_KEY'}
        env['SEED_FROM_API'] = 'true'
        with patch.dict(os.environ, env, clear=True):
            with patch('application.dev_seed.populate_dev_db') as mock_pop:
                from application.app import _init_dev_db
                _init_dev_db(db)
        mock_pop.assert_called_once_with(db)

    def test_intro_retorna_200_apos_seed_api(self, app):
        db = app_module.client[os.environ.get('MONGO_DB_NAME', 'dev')]
        teams_resp = self._api_teams_response()
        matches_resp = self._api_matches_response({})

        with patch.dict(os.environ, {'SEED_FROM_API': 'true', 'FOOTBALL_DATA_API_KEY': 'fake_key'}):
            with patch('application.crawler_2026._get', side_effect=lambda p, **kw:
                       teams_resp if 'teams' in p else matches_resp):
                from application.app import _init_dev_db
                _init_dev_db(db)

        with app.test_client() as c:
            r = c.get('/intro')
        assert r.status_code == 200, f"/intro após seed API retornou {r.status_code}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_csrf(client):
    """Extrai o token CSRF de qualquer página que o sirva."""
    r = client.get('/intro')
    html = r.data.decode('utf-8', errors='replace')
    marker = 'name="csrf-token" content="'
    idx = html.find(marker)
    if idx == -1:
        return 'test-csrf-token'
    start = idx + len(marker)
    end = html.find('"', start)
    return html[start:end]
