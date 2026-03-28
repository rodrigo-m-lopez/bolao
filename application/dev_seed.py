"""Seed de banco de dados para modo DEV_MOCK_AUTH.

Cria 6 jogos em estados de tempo distintos e 3 apostas com diferentes
graus de preenchimento, cobrindo os 4 estados possíveis do palpite:

  Estado A – jogo bloqueado  + palpite salvo    → "X x Y — bloqueado"
  Estado B – jogo bloqueado  + sem palpite       → "não informado — bloqueado"
  Estado C – jogo desbloqueado + palpite salvo   → inputs editáveis com valor
  Estado D – jogo desbloqueado + sem palpite     → inputs editáveis vazios

Apostas geradas
───────────────
  "Apostador Completo"  → A A A C C D  (fez palpites para quase tudo)
  "Apostador Parcial"   → B B B C D D  (perdeu o prazo nos jogos passados)
  "Apostador Zerado"    → B B B D D D  (criou a aposta mas nunca preencheu)

O usuário dev (dev@local.test) é criado caso ainda não exista, para que o
fluxo de /dev_login também funcione sem conflito.
"""
from datetime import datetime, timedelta
import logging

from application.constants import (
    PONTUACAO_PLACAR_EXATO,
    PONTUACAO_VENCEDOR_OU_EMPATE,
    PONTUACAO_GOLS_DE_UM_TIME,
)

logger = logging.getLogger(__name__)

_JOGOS = [
    # (nome,         grupo, rodada, delta_tempo,            gm,   gv,   mandante, visitante)
    # ── Encerrados (passado COM resultado) ────────────────────────────────────
    ('BRA x ARG',   'A',   1,   timedelta(days=-3),      2,    1,    'BRA', 'ARG'),  # encerrado, placar exato errado
    ('FRA x GER',   'B',   1,   timedelta(days=-2),      1,    0,    'FRA', 'GER'),  # encerrado, acertou vencedor
    # ── Em andamento (passado SEM resultado) ──────────────────────────────────
    ('ARG x BRA',   'A',   2,   timedelta(minutes=-45),  None, None, 'ARG', 'BRA'),  # em andamento com palpite
    ('GER x FRA',   'B',   2,   timedelta(minutes=-10),  None, None, 'GER', 'FRA'),  # em andamento sem palpite
    # ── Desbloqueados (futuro) ────────────────────────────────────────────────
    ('BRA x FRA',   'A',   3,   timedelta(hours=2),      None, None, 'BRA', 'FRA'),  # quase começando
    ('GER x BRA',   'B',   3,   timedelta(days=3),       None, None, 'GER', 'BRA'),  # próximos dias
    ('ARG x FRA',   'C',   1,   timedelta(days=6),       None, None, 'ARG', 'FRA'),  # semana que vem
]

_SELECOES = [
    {'nome': 'Brasil',    'sigla': 'BRA', 'escudo': '', 'grupo': 'A'},
    {'nome': 'Argentina', 'sigla': 'ARG', 'escudo': '', 'grupo': 'A'},
    {'nome': 'França',    'sigla': 'FRA', 'escudo': '', 'grupo': 'B'},
    {'nome': 'Alemanha',  'sigla': 'GER', 'escudo': '', 'grupo': 'B'},
]

# Clubes mock da Libertadores (siglas únicas)
_CLUBES_LIB = [
    {'nome': 'River Plate',  'sigla': 'RIV', 'escudo': '', 'grupo': ''},
    {'nome': 'Boca Juniors', 'sigla': 'BOC', 'escudo': '', 'grupo': ''},
    {'nome': 'Nacional',     'sigla': 'NAC', 'escudo': '', 'grupo': ''},
    {'nome': 'Peñarol',      'sigla': 'PEN', 'escudo': '', 'grupo': ''},
]

# (nome, grupo, rodada, delta, gm, gv, mandante_sigla, visitante_sigla)
_JOGOS_LIB = [
    ('RIV x BOC', 'Grupo A', 1, timedelta(days=-1),  2,    0,    'RIV', 'BOC'),
    ('NAC x PEN', 'Grupo B', 1, timedelta(hours=2),  None, None, 'NAC', 'PEN'),
    ('BOC x RIV', 'Grupo A', 2, timedelta(days=5),   None, None, 'BOC', 'RIV'),
    ('PEN x NAC', 'Grupo B', 2, timedelta(days=6),   None, None, 'PEN', 'NAC'),
]

# Clubes mock do Brasileirão (siglas únicas, sem conflito com seleções)
_CLUBES_BR = [
    {'nome': 'Flamengo',    'sigla': 'FLA', 'escudo': '', 'grupo': ''},
    {'nome': 'Palmeiras',   'sigla': 'PAL', 'escudo': '', 'grupo': ''},
    {'nome': 'São Paulo',   'sigla': 'SAO', 'escudo': '', 'grupo': ''},
    {'nome': 'Corinthians', 'sigla': 'COR', 'escudo': '', 'grupo': ''},
    {'nome': 'Fluminense',  'sigla': 'FLU', 'escudo': '', 'grupo': ''},
    {'nome': 'Atlético-MG', 'sigla': 'CAM', 'escudo': '', 'grupo': ''},
]

# (nome, rodada, delta, gm, gv, mandante_sigla, visitante_sigla)
_JOGOS_BR = [
    ('FLA x PAL', 1, timedelta(days=-2),  2,    1,    'FLA', 'PAL'),
    ('SAO x COR', 1, timedelta(days=-1),  None, None, 'SAO', 'COR'),
    ('FLU x CAM', 1, timedelta(hours=3),  None, None, 'FLU', 'CAM'),
    ('PAL x SAO', 2, timedelta(days=4),   None, None, 'PAL', 'SAO'),
    ('COR x FLA', 2, timedelta(days=5),   None, None, 'COR', 'FLA'),
    ('CAM x FLU', 2, timedelta(days=6),   None, None, 'CAM', 'FLU'),
]

# Clubes mock da Copa Sulamericana (siglas únicas, sem conflito)
_CLUBES_SUL = [
    {'nome': 'Athletico-PR',  'sigla': 'CAP', 'escudo': '', 'grupo': ''},
    {'nome': 'Fortaleza',     'sigla': 'FOR', 'escudo': '', 'grupo': ''},
    {'nome': 'Independiente', 'sigla': 'IND', 'escudo': '', 'grupo': ''},
    {'nome': 'Defensa',       'sigla': 'DEF', 'escudo': '', 'grupo': ''},
]

# (nome, rodada, delta, gm, gv, mandante_sigla, visitante_sigla)
_JOGOS_SUL = [
    ('CAP x FOR', 1, timedelta(days=-1),  2,    0,    'CAP', 'FOR'),
    ('IND x DEF', 1, timedelta(hours=4),  None, None, 'IND', 'DEF'),
    ('FOR x CAP', 2, timedelta(days=7),   None, None, 'FOR', 'CAP'),
    ('DEF x IND', 2, timedelta(days=8),   None, None, 'DEF', 'IND'),
]


def seed_sulamericana_mock(db):
    """Insere dados mock da Copa Sulamericana 2026 de forma idempotente.

    Usa upsert ($setOnInsert) — seguro chamar em modo API e em modo mock.
    """
    now = datetime.utcnow()

    for clube in _CLUBES_SUL:
        db.selecao.update_one(
            {'sigla': clube['sigla']},
            {'$setOnInsert': clube},
            upsert=True,
        )

    sel_sul = {
        s['sigla']: s['_id']
        for s in db.selecao.find({'sigla': {'$in': ['CAP', 'FOR', 'IND', 'DEF']}})
    }

    for nome, rodada, delta, gm, gv, m_sigla, v_sigla in _JOGOS_SUL:
        db.jogo.update_one(
            {'nome': nome, 'competicao': 'Copa Sulamericana 2026'},
            {'$setOnInsert': {
                'nome': nome,
                'grupo': f'Rodada {rodada}',
                'rodada': rodada,
                'data': now + delta,
                'local': 'Estádio Dev',
                'mandante': sel_sul[m_sigla],
                'visitante': sel_sul[v_sigla],
                'gols_mandante': gm,
                'gols_visitante': gv,
                'competicao': 'Copa Sulamericana 2026',
            }},
            upsert=True,
        )

    logger.info('Copa Sulamericana 2026: seed mock concluído (%d jogos)', len(_JOGOS_SUL))


def populate_dev_db(db):
    """Popula o banco com dados de seed se ainda estiver vazio."""
    if db.jogo.count_documents({}) > 0:
        return

    logger.info('DEV_MOCK_AUTH: populando banco com dados de teste...')

    now = datetime.utcnow()

    # ── Seleções ──────────────────────────────────────────────────────────────
    db.selecao.insert_many(_SELECOES)
    sel = {s['sigla']: s['_id'] for s in db.selecao.find()}

    # ── Jogos ──────────────────────────────────────────────────────────────────
    jogo_ids = {}
    for nome, grupo, rodada, delta, gm, gv, m_sigla, v_sigla in _JOGOS:
        jid = db.jogo.insert_one({
            'nome': nome,
            'grupo': grupo,
            'rodada': rodada,
            'data': now + delta,
            'local': 'Estádio Dev',
            'mandante': sel[m_sigla],
            'visitante': sel[v_sigla],
            'gols_mandante': gm,
            'gols_visitante': gv,
            'competicao': 'Copa do Mundo 2026',
        }).inserted_id
        jogo_ids[nome] = jid

    todos_jids = list(jogo_ids.values())

    # ── Jogos da Libertadores ─────────────────────────────────────────────────
    db.selecao.insert_many(_CLUBES_LIB)
    sel_lib = {s['sigla']: s['_id'] for s in db.selecao.find({'sigla': {'$in': ['RIV', 'BOC', 'NAC', 'PEN']}})}
    for nome, grupo, rodada, delta, gm, gv, m_sigla, v_sigla in _JOGOS_LIB:
        db.jogo.insert_one({
            'nome': nome,
            'grupo': grupo,
            'rodada': rodada,
            'data': now + delta,
            'local': 'Estádio Dev',
            'mandante': sel_lib[m_sigla],
            'visitante': sel_lib[v_sigla],
            'gols_mandante': gm,
            'gols_visitante': gv,
            'competicao': 'Copa Libertadores 2026',
        })

    # ── Jogos do Brasileirão ──────────────────────────────────────────────────
    db.selecao.insert_many(_CLUBES_BR)
    sel_br = {s['sigla']: s['_id'] for s in db.selecao.find({'sigla': {'$in': ['FLA', 'PAL', 'SAO', 'COR', 'FLU', 'CAM']}})}
    for nome, rodada, delta, gm, gv, m_sigla, v_sigla in _JOGOS_BR:
        db.jogo.insert_one({
            'nome': nome,
            'grupo': f'Rodada {rodada}',
            'rodada': rodada,
            'data': now + delta,
            'local': 'Estádio Dev',
            'mandante': sel_br[m_sigla],
            'visitante': sel_br[v_sigla],
            'gols_mandante': gm,
            'gols_visitante': gv,
            'competicao': 'Campeonato Brasileiro Série A 2026',
        })

    # ── Jogos da Copa Sulamericana ────────────────────────────────────────────
    db.selecao.insert_many(_CLUBES_SUL)
    sel_sul = {s['sigla']: s['_id'] for s in db.selecao.find({'sigla': {'$in': ['CAP', 'FOR', 'IND', 'DEF']}})}
    for nome, rodada, delta, gm, gv, m_sigla, v_sigla in _JOGOS_SUL:
        db.jogo.insert_one({
            'nome': nome,
            'grupo': f'Rodada {rodada}',
            'rodada': rodada,
            'data': now + delta,
            'local': 'Estádio Dev',
            'mandante': sel_sul[m_sigla],
            'visitante': sel_sul[v_sigla],
            'gols_mandante': gm,
            'gols_visitante': gv,
            'competicao': 'Copa Sulamericana 2026',
        })

    # ── Usuário dev ───────────────────────────────────────────────────────────
    dev_email = 'dev@local.test'
    usuario = db.usuario.find_one({'email': dev_email})
    if usuario is None:
        uid = db.usuario.insert_one({
            'nome': 'Dev User', 'email': dev_email,
            'primeiro_nome': 'Dev', 'sobrenome': 'User',
            'foto': '', 'sexo': 'm',
        }).inserted_id
    else:
        uid = usuario['_id']

    # ── Bolão ─────────────────────────────────────────────────────────────────
    bid = db.bolao.insert_one({
        'nome': 'Bolão Dev',
        'usuario': uid,
        'valor': 20,
        'premiacao': '70% ao 1º, 30% ao 2º',
        'descricao': (
            'Bolão criado automaticamente para testar o cadastro incremental '
            'de palpites. Cada aposta abaixo demonstra um cenário diferente.'
        ),
        'competicao': 'Copa do Mundo 2026',
    }).inserted_id

    # ── Helper ────────────────────────────────────────────────────────────────
    def _pontos(real_m, real_v, palp_m, palp_v):
        """Calcula pontuação de um palpite dado o resultado real."""
        if real_m is None or real_v is None:
            return 0, 0, 0, 0
        if real_m == palp_m and real_v == palp_v:
            return PONTUACAO_PLACAR_EXATO, 1, 0, 0
        resultado_real = (real_m > real_v) - (real_m < real_v)
        resultado_palp = (palp_m > palp_v) - (palp_m < palp_v)
        acertou_result = int(resultado_real == resultado_palp)
        acertou_gols   = int(real_m == palp_m or real_v == palp_v)
        pts = acertou_result * PONTUACAO_VENCEDOR_OU_EMPATE + acertou_gols * PONTUACAO_GOLS_DE_UM_TIME
        return pts, 0, acertou_result, acertou_gols

    def cria_aposta(nome_aposta, palpites_dict):
        """
        palpites_dict: dict {nome_jogo: (gols_mandante, gols_visitante)}
        Calcula pontuação real para partidas já encerradas.
        """
        aid = db.aposta.insert_one({
            'nome': nome_aposta, 'usuario': uid,
            'bolao': bid, 'pago': True,
        }).inserted_id

        # pontuacao inicial — será atualizada abaixo para jogos encerrados
        for jid in todos_jids:
            db.pontuacao.insert_one({
                'aposta': aid, 'jogo': jid,
                'pontos': 0, 'placar_exato': 0,
                'vencedor_ou_empate': 0, 'gols_de_um_time': 0,
            })

        # palpites e cálculo de pontos para jogos com resultado
        for nome_jogo, (gm, gv) in palpites_dict.items():
            jid = jogo_ids[nome_jogo]
            db.palpite.insert_one({
                'aposta': aid, 'jogo': jid,
                'gols_mandante': gm, 'gols_visitante': gv,
            })
            jogo_doc = db.jogo.find_one({'_id': jid})
            real_m = jogo_doc.get('gols_mandante')
            real_v = jogo_doc.get('gols_visitante')
            if real_m is not None and real_v is not None:
                pts, exato, result, gols = _pontos(real_m, real_v, gm, gv)
                db.pontuacao.update_one(
                    {'aposta': aid, 'jogo': jid},
                    {'$set': {'pontos': pts, 'placar_exato': exato,
                              'vencedor_ou_empate': result, 'gols_de_um_time': gols}},
                )

        logger.info('  Aposta "%s" criada (%d palpites)', nome_aposta, len(palpites_dict))
        return aid

    # ── Apostas ───────────────────────────────────────────────────────────────
    #
    # Estados possíveis por partida:
    #   encerrado+p  = jogo encerrado (tem resultado), com palpite
    #   encerrado/-  = jogo encerrado, sem palpite
    #   andamento+p  = jogo em andamento (sem resultado), com palpite
    #   andamento/-  = jogo em andamento, sem palpite
    #   aberto+p     = jogo futuro, palpite preenchido
    #   aberto/-     = jogo futuro, sem palpite
    #
    #   BRA x ARG    FRA x GER    ARG x BRA    GER x FRA    BRA x FRA    GER x BRA    ARG x FRA
    #   enc (2x1)    enc (1x0)    andamento    andamento    aberto       aberto       aberto
    cria_aposta('Apostador Completo', {
        'BRA x ARG': (1, 1),   # encerrado+p — apostou 1x1, real foi 2x1 (errou placar, acertou nada)
        'FRA x GER': (1, 0),   # encerrado+p — apostou 1x0, real foi 1x0 (placar exato!)
        'ARG x BRA': (2, 0),   # andamento+p — apostou 2x0, jogo em andamento
        # GER x FRA sem palpite → andamento/-
        'BRA x FRA': (2, 1),   # aberto+p    — palpite preenchido, jogo futuro
        'GER x BRA': (0, 2),   # aberto+p    — palpite preenchido, jogo futuro
        #                         ARG x FRA   — aberto/- (campo vazio)
    })

    #   BRA x ARG    FRA x GER    ARG x BRA    GER x FRA    BRA x FRA    GER x BRA    ARG x FRA
    #   enc/-        enc/-        andamento/-  andamento/-  aberto+p     aberto/-     aberto/-
    cria_aposta('Apostador Parcial', {
        # Jogos encerrados e em andamento sem palpite → perdeu o prazo
        'BRA x FRA': (1, 1),   # aberto+p — apenas um jogo futuro apostado
    })

    #   Todos bloqueados → estado B  |  Todos futuros → estado D
    cria_aposta('Apostador Zerado', {
        # sem nenhum palpite: demonstra aposta recém-criada
    })

    n_jogos = db.jogo.count_documents({})
    logger.info(
        'DEV_MOCK_AUTH: banco populado — '
        '%d jogos (Copa do Mundo + Libertadores + Brasileirão + Sulamericana), '
        '1 bolão ("Bolão Dev"), 3 apostas.', n_jogos
    )
