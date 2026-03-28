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

logger = logging.getLogger(__name__)

_JOGOS = [
    # (nome,         grupo, rodada, delta_tempo,            gm,   gv,   mandante, visitante)
    # ── Bloqueados (passado) ──────────────────────────────────────────────────
    ('BRA x ARG',   'A',   1,   timedelta(days=-3),      2,    1,    'BRA', 'ARG'),  # COM resultado
    ('FRA x GER',   'B',   1,   timedelta(days=-1),      None, None, 'FRA', 'GER'),  # SEM resultado
    ('ARG x BRA',   'A',   2,   timedelta(minutes=-30),  None, None, 'ARG', 'BRA'),  # recém bloqueado
    # ── Desbloqueados (futuro) ────────────────────────────────────────────────
    ('BRA x FRA',   'A',   3,   timedelta(hours=2),      None, None, 'BRA', 'FRA'),  # quase começando
    ('GER x BRA',   'B',   2,   timedelta(days=3),       None, None, 'GER', 'BRA'),  # próximos dias
    ('ARG x FRA',   'B',   3,   timedelta(days=6),       None, None, 'ARG', 'FRA'),  # semana que vem
]

_SELECOES = [
    {'nome': 'Brasil',    'sigla': 'BRA', 'escudo': '', 'grupo': 'A'},
    {'nome': 'Argentina', 'sigla': 'ARG', 'escudo': '', 'grupo': 'A'},
    {'nome': 'França',    'sigla': 'FRA', 'escudo': '', 'grupo': 'B'},
    {'nome': 'Alemanha',  'sigla': 'GER', 'escudo': '', 'grupo': 'B'},
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

    # ── Jogos do Brasileirão ──────────────────────────────────────────────────
    db.selecao.insert_many(_CLUBES_BR)
    sel_br = {s['sigla']: s['_id'] for s in db.selecao.find({'grupo': ''})}
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
    def cria_aposta(nome_aposta, palpites):
        """
        palpites: dict {nome_jogo: (gols_mandante, gols_visitante)}
        """
        aid = db.aposta.insert_one({
            'nome': nome_aposta, 'usuario': uid,
            'bolao': bid, 'pago': False,
        }).inserted_id

        # pontuacao zerada para todos os jogos (padrão do sistema)
        for jid in todos_jids:
            db.pontuacao.insert_one({
                'aposta': aid, 'jogo': jid,
                'pontos': 0, 'placar_exato': 0,
                'vencedor_ou_empate': 0, 'gols_de_um_time': 0,
            })

        # palpites somente onde fornecido
        for nome_jogo, (gm, gv) in palpites.items():
            db.palpite.insert_one({
                'aposta': aid,
                'jogo': jogo_ids[nome_jogo],
                'gols_mandante': gm,
                'gols_visitante': gv,
            })

        logger.info('  Aposta "%s" criada (%d palpites)', nome_aposta, len(palpites))
        return aid

    # ── Apostas ───────────────────────────────────────────────────────────────
    #
    # Cenários cobertos por jogo para cada aposta:
    #   BRA x ARG   FRA x GER  ARG x BRA   BRA x FRA   GER x BRA   ARG x FRA
    #   (A: bloq+p) (A: bloq+p)(A: bloq+p) (C: lib+p)  (C: lib+p)  (D: lib/-)
    cria_aposta('Apostador Completo', {
        'BRA x ARG': (1, 1),   # estado A — bloqueado, palpite errou o placar
        'FRA x GER': (2, 0),   # estado A — bloqueado, sem resultado ainda
        'ARG x BRA': (0, 1),   # estado A — recém bloqueado, com palpite
        'BRA x FRA': (2, 1),   # estado C — liberado, palpite preenchido
        'GER x BRA': (0, 2),   # estado C — liberado, palpite preenchido
        #                        estado D — ARG x FRA sem palpite (campo vazio)
    })

    #   BRA x ARG   FRA x GER  ARG x BRA   BRA x FRA   GER x BRA   ARG x FRA
    #   (B: bloq/-) (B: bloq/-)(B: bloq/-)  (C: lib+p)  (D: lib/-)  (D: lib/-)
    cria_aposta('Apostador Parcial', {
        # jogos passados omitidos → estado B (perdeu o prazo)
        'BRA x FRA': (1, 1),   # estado C — liberado, palpite preenchido
        #                        estado D — GER x BRA e ARG x FRA sem palpite
    })

    #   Todos bloqueados → estado B  |  Todos futuros → estado D
    cria_aposta('Apostador Zerado', {
        # sem nenhum palpite: demonstra aposta recém-criada
    })

    logger.info(
        'DEV_MOCK_AUTH: banco populado — '
        '4 seleções, 6 jogos (3 bloqueados / 3 liberados), '
        '1 bolão ("Bolão Dev"), 3 apostas.'
    )
