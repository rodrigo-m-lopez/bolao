# coding: utf-8
"""
Crawler / seeder para a Copa do Mundo 2026.

Usa a API gratuita football-data.org (v4) para:
  1. seed_database(db)     — popula seleções e jogos da fase de grupos
  2. atualiza_resultados(db) — atualiza placares dos jogos já encerrados

Variável de ambiente necessária:
  FOOTBALL_DATA_API_KEY — chave gratuita em https://www.football-data.org/client/register

Execução manual:
  python -m application.crawler_2026 seed       # popula times e jogos
  python -m application.crawler_2026 update     # atualiza resultados
"""

import os
import logging
import sys
from datetime import datetime, timezone

import requests
from pymongo import ASCENDING

logger = logging.getLogger(__name__)

_BASE_URL = 'https://api.football-data.org/v4'
_COMPETITION = 'WC'
_SEASON = 2026
_TIMEOUT = 15

# Mapeamento grupo API → nome exibido na tela
_GRUPOS = {
    'GROUP_A': 'Grupo A', 'GROUP_B': 'Grupo B', 'GROUP_C': 'Grupo C',
    'GROUP_D': 'Grupo D', 'GROUP_E': 'Grupo E', 'GROUP_F': 'Grupo F',
    'GROUP_G': 'Grupo G', 'GROUP_H': 'Grupo H', 'GROUP_I': 'Grupo I',
    'GROUP_J': 'Grupo J', 'GROUP_K': 'Grupo K', 'GROUP_L': 'Grupo L',
}


def _headers():
    api_key = os.environ.get('FOOTBALL_DATA_API_KEY', '')
    if not api_key:
        raise EnvironmentError(
            'Variável FOOTBALL_DATA_API_KEY não definida.\n'
            'Obtenha uma chave gratuita em https://www.football-data.org/client/register'
        )
    return {'X-Auth-Token': api_key}


def _get(path, params=None):
    url = _BASE_URL + path
    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        logger.error('Timeout ao acessar %s', url)
        raise
    except requests.exceptions.HTTPError as exc:
        logger.error('HTTP %s ao acessar %s: %s', exc.response.status_code, url, exc)
        raise


# ── Seed ─────────────────────────────────────────────────────────────────────

def seed_database(db):
    """Popula o banco com as seleções e jogos da fase de grupos de 2026.

    Idempotente: usa upsert, pode ser executado mais de uma vez sem duplicar dados.
    """
    logger.info('Iniciando seed da Copa 2026...')
    _seed_selecoes(db)
    _seed_jogos(db)
    logger.info('Seed concluído.')


def _seed_selecoes(db):
    logger.info('Buscando seleções na API...')
    data = _get(f'/competitions/{_COMPETITION}/teams', params={'season': _SEASON})
    teams = data.get('teams', [])
    logger.info('%d seleções recebidas', len(teams))

    for team in teams:
        sigla = (team.get('tla') or (team.get('shortName') or team.get('name', '???'))[:3]).upper()
        nome = team.get('name') or sigla
        escudo = team.get('crest', '')

        # O grupo vem nos standings, não no endpoint de times — deixamos em branco
        # e preenchemos ao processar os jogos
        db.selecao.update_one(
            {'sigla': sigla},
            {'$setOnInsert': {'sigla': sigla, 'nome': nome, 'escudo': escudo, 'grupo': ''}},
            upsert=True,
        )
    logger.info('Seleções inseridas/atualizadas.')


def _seed_jogos(db):
    logger.info('Buscando jogos da fase de grupos na API...')
    data = _get(
        f'/competitions/{_COMPETITION}/matches',
        params={'season': _SEASON, 'stage': 'GROUP_STAGE'},
    )
    matches = data.get('matches', [])
    logger.info('%d jogos recebidos', len(matches))

    for match in matches:
        _upsert_jogo(db, match)

    logger.info('Jogos inseridos/atualizados.')


def _upsert_jogo(db, match):
    home = match['homeTeam']
    away = match['awayTeam']

    sigla_mandante = (home.get('tla') or (home.get('shortName') or home.get('name', '???'))[:3]).upper()
    sigla_visitante = (away.get('tla') or (away.get('shortName') or away.get('name', '???'))[:3]).upper()
    nome_jogo = f'{sigla_mandante} x {sigla_visitante}'

    grupo_api = match.get('group') or ''
    grupo = _GRUPOS.get(grupo_api, grupo_api)

    # Rodada dentro do grupo (matchday 1-3)
    rodada = match.get('matchday', 1)

    # Data/hora em UTC → datetime sem tz (padrão do app)
    utc_str = match.get('utcDate', '')
    try:
        data = datetime.fromisoformat(utc_str.replace('Z', '+00:00')).replace(tzinfo=None)
    except (ValueError, AttributeError):
        data = None

    score = match.get('score', {})
    ft = score.get('fullTime', {})
    gols_mandante = ft.get('home')
    gols_visitante = ft.get('away')

    # Referências para ObjectId das seleções
    sel_mandante = db.selecao.find_one({'sigla': sigla_mandante})
    sel_visitante = db.selecao.find_one({'sigla': sigla_visitante})

    if sel_mandante is None or sel_visitante is None:
        logger.warning('Seleção não encontrada para jogo %s — pulando', nome_jogo)
        return

    # Atualiza grupo na seleção se ainda em branco
    if not sel_mandante.get('grupo'):
        db.selecao.update_one({'_id': sel_mandante['_id']}, {'$set': {'grupo': grupo}})
    if not sel_visitante.get('grupo'):
        db.selecao.update_one({'_id': sel_visitante['_id']}, {'$set': {'grupo': grupo}})

    venue = match.get('venue') or ''

    db.jogo.update_one(
        {'nome': nome_jogo},
        {'$set': {
            'nome': nome_jogo,
            'data': data,
            'local': venue,
            'mandante': sel_mandante['_id'],
            'visitante': sel_visitante['_id'],
            'gols_mandante': gols_mandante,
            'gols_visitante': gols_visitante,
            'grupo': grupo,
            'rodada': rodada,
            'url_rodada': f'/rodada/{rodada}',
        }},
        upsert=True,
    )


# ── Atualiza resultados ───────────────────────────────────────────────────────

def _resultado(gols_m, gols_v):
    return (gols_m > gols_v) - (gols_m < gols_v)


def _calcula_pontuacao(real_m, real_v, palp_m, palp_v):
    from application.constants import (
        PONTUACAO_PLACAR_EXATO, PONTUACAO_VENCEDOR_OU_EMPATE, PONTUACAO_GOLS_DE_UM_TIME,
    )
    if real_m is None or real_v is None:
        return 0, False, False, False
    if real_m == palp_m and real_v == palp_v:
        return PONTUACAO_PLACAR_EXATO, True, False, False
    pontos = 0
    resultado = _resultado(real_m, real_v) == _resultado(palp_m, palp_v)
    gols_um = real_m == palp_m or real_v == palp_v
    if resultado:
        pontos += PONTUACAO_VENCEDOR_OU_EMPATE
    if gols_um:
        pontos += PONTUACAO_GOLS_DE_UM_TIME
    return pontos, False, resultado, gols_um


def _calcula_pontos_apostas(db, id_jogo, gols_m_real, gols_v_real):
    for palpite in db.palpite.find({'jogo': id_jogo}):
        id_aposta = palpite['aposta']
        aposta = db.aposta.find_one({'_id': id_aposta})
        if aposta is None or not aposta.get('pago'):
            continue
        pontos, exato, resultado, gols_um = _calcula_pontuacao(
            gols_m_real, gols_v_real,
            palpite['gols_mandante'], palpite['gols_visitante'],
        )
        db.pontuacao.update_one(
            {'aposta': id_aposta, 'jogo': id_jogo},
            {'$set': {
                'pontos': pontos,
                'placar_exato': int(exato),
                'vencedor_ou_empate': int(resultado),
                'gols_de_um_time': int(gols_um),
            }},
        )
        logger.info('Pontuação: aposta=%s jogo=%s pontos=%d', aposta['nome'], id_jogo, pontos)


def atualiza_resultados(db):
    """Atualiza placares dos jogos encerrados e recalcula pontuações.

    Deve ser chamado periodicamente durante a Copa (ex.: a cada 5 minutos).
    """
    logger.info('Atualizando resultados...')
    data = _get(
        f'/competitions/{_COMPETITION}/matches',
        params={'season': _SEASON, 'stage': 'GROUP_STAGE', 'status': 'FINISHED'},
    )
    matches = data.get('matches', [])
    logger.info('%d jogos encerrados recebidos', len(matches))

    for match in matches:
        home = match['homeTeam']
        away = match['awayTeam']
        sigla_m = (home.get('tla') or (home.get('shortName') or home.get('name', ''))[:3]).upper()
        sigla_v = (away.get('tla') or (away.get('shortName') or away.get('name', ''))[:3]).upper()
        nome_jogo = f'{sigla_m} x {sigla_v}'

        ft = match.get('score', {}).get('fullTime', {})
        gols_m = ft.get('home')
        gols_v = ft.get('away')

        if gols_m is None or gols_v is None:
            continue

        jogo = db.jogo.find_one({'nome': nome_jogo})
        if jogo is None:
            logger.warning('Jogo %s não encontrado no banco — execute seed primeiro', nome_jogo)
            continue

        # Só recalcula se o placar mudou
        if jogo.get('gols_mandante') == gols_m and jogo.get('gols_visitante') == gols_v:
            continue

        db.jogo.update_one(
            {'_id': jogo['_id']},
            {'$set': {'gols_mandante': gols_m, 'gols_visitante': gols_v}},
        )
        logger.info('Placar atualizado: %s %d x %d', nome_jogo, gols_m, gols_v)
        _calcula_pontos_apostas(db, jogo['_id'], gols_m, gols_v)

    logger.info('Atualização de resultados concluída.')


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

    cmd = sys.argv[1] if len(sys.argv) > 1 else 'seed'

    from application.db_config import get_db_client
    _client = get_db_client()
    _db = _client[os.environ.get('MONGO_DB_NAME', 'dev')]

    if cmd == 'seed':
        seed_database(_db)
    elif cmd == 'update':
        atualiza_resultados(_db)
    else:
        print(f'Uso: python -m application.crawler_2026 [seed|update]')
        sys.exit(1)
