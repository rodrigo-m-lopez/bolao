# coding: utf-8
"""
Crawler / seeder para o Campeonato Brasileiro Série A 2026.

Usa a API gratuita football-data.org (v4) para:
  1. seed_brasileirao(db)        — popula clubes e jogos do campeonato
  2. atualiza_resultados_br(db)  — atualiza placares dos jogos encerrados

Variável de ambiente necessária:
  FOOTBALL_DATA_API_KEY — chave gratuita em https://www.football-data.org/client/register

Execução manual:
  python -m application.crawler_brasileirao seed    # popula times e jogos
  python -m application.crawler_brasileirao update  # atualiza resultados
"""

import os
import time
import logging
from datetime import datetime

import requests
from pymongo import ASCENDING

logger = logging.getLogger(__name__)

_BASE_URL = 'https://api.football-data.org/v4'
_COMPETITION = 'BSA'
_SEASON = 2026
_TIMEOUT = 15
_COMPETICAO = 'Campeonato Brasileiro Série A 2026'


def _headers():
    api_key = os.environ.get('FOOTBALL_DATA_API_KEY', '')
    if not api_key:
        raise EnvironmentError(
            'Variável FOOTBALL_DATA_API_KEY não definida.\n'
            'Obtenha uma chave gratuita em https://www.football-data.org/client/register'
        )
    return {'X-Auth-Token': api_key}


def _get(path, params=None, _retries=3):
    url = _BASE_URL + path
    for attempt in range(_retries):
        try:
            resp = requests.get(url, headers=_headers(), params=params, timeout=_TIMEOUT)
            if resp.status_code == 429:
                wait = int(resp.headers.get('Retry-After', 65))
                logger.warning('Rate limit atingido em %s — aguardando %ds (tentativa %d/%d)',
                               url, wait, attempt + 1, _retries)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            logger.error('Timeout ao acessar %s', url)
            raise
        except requests.exceptions.HTTPError as exc:
            logger.error('HTTP %s ao acessar %s: %s', exc.response.status_code, url, exc)
            raise
    raise RuntimeError(f'Falhou após {_retries} tentativas: {url}')


# ── Seed ─────────────────────────────────────────────────────────────────────

def seed_brasileirao(db):
    """Popula o banco com clubes e jogos do Brasileirão Série A 2026.

    Idempotente: usa upsert, pode ser executado mais de uma vez sem duplicar dados.
    """
    logger.info('Iniciando seed do Brasileirão Série A 2026...')
    _seed_clubes(db)
    _seed_jogos(db)
    logger.info('Seed do Brasileirão concluído.')


def _seed_clubes(db):
    logger.info('Buscando clubes na API...')
    data = _get(f'/competitions/{_COMPETITION}/teams', params={'season': _SEASON})
    teams = data.get('teams', [])
    logger.info('%d clubes recebidos', len(teams))

    for team in teams:
        sigla = (team.get('tla') or team.get('shortName') or team.get('name') or '???')[:3].upper()
        nome = team.get('name') or sigla
        escudo = team.get('crest', '')

        db.selecao.update_one(
            {'sigla': sigla},
            {'$setOnInsert': {'sigla': sigla, 'nome': nome, 'escudo': escudo, 'grupo': ''}},
            upsert=True,
        )
    logger.info('Clubes inseridos/atualizados.')


def _seed_jogos(db):
    logger.info('Buscando jogos do Brasileirão na API...')
    data = _get(f'/competitions/{_COMPETITION}/matches', params={'season': _SEASON})
    matches = data.get('matches', [])
    logger.info('%d jogos recebidos', len(matches))

    for match in matches:
        _upsert_jogo(db, match)

    logger.info('Jogos inseridos/atualizados.')


def _upsert_jogo(db, match):
    home = match['homeTeam']
    away = match['awayTeam']

    sigla_m = (home.get('tla') or home.get('shortName') or home.get('name') or '???')[:3].upper()
    sigla_v = (away.get('tla') or away.get('shortName') or away.get('name') or '???')[:3].upper()
    nome_jogo = f'{sigla_m} x {sigla_v}'

    rodada = match.get('matchday', 1)
    grupo = f'Rodada {rodada}'

    utc_str = match.get('utcDate', '')
    try:
        data = datetime.fromisoformat(utc_str.replace('Z', '+00:00')).replace(tzinfo=None)
    except (ValueError, AttributeError):
        data = None

    score = match.get('score', {})
    ft = score.get('fullTime', {})
    gols_m = ft.get('home')
    gols_v = ft.get('away')

    sel_m = db.selecao.find_one({'sigla': sigla_m})
    sel_v = db.selecao.find_one({'sigla': sigla_v})

    if sel_m is None or sel_v is None:
        logger.warning('Clube não encontrado para jogo %s — pulando', nome_jogo)
        return

    venue = match.get('venue') or ''

    db.jogo.update_one(
        {'nome': nome_jogo, 'competicao': _COMPETICAO},
        {'$set': {
            'nome': nome_jogo,
            'data': data,
            'local': venue,
            'mandante': sel_m['_id'],
            'visitante': sel_v['_id'],
            'gols_mandante': gols_m,
            'gols_visitante': gols_v,
            'grupo': grupo,
            'rodada': rodada,
            'competicao': _COMPETICAO,
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


def atualiza_resultados_br(db):
    """Atualiza placares dos jogos encerrados e recalcula pontuações."""
    logger.info('Atualizando resultados do Brasileirão...')
    data = _get(
        f'/competitions/{_COMPETITION}/matches',
        params={'season': _SEASON, 'status': 'FINISHED'},
    )
    matches = data.get('matches', [])
    logger.info('%d jogos encerrados recebidos', len(matches))

    for match in matches:
        home = match['homeTeam']
        away = match['awayTeam']
        sigla_m = (home.get('tla') or home.get('shortName') or home.get('name') or '')[:3].upper()
        sigla_v = (away.get('tla') or away.get('shortName') or away.get('name') or '')[:3].upper()
        nome_jogo = f'{sigla_m} x {sigla_v}'

        ft = match.get('score', {}).get('fullTime', {})
        gols_m = ft.get('home')
        gols_v = ft.get('away')

        if gols_m is None or gols_v is None:
            continue

        jogo = db.jogo.find_one({'nome': nome_jogo, 'competicao': _COMPETICAO})
        if jogo is None:
            logger.warning('Jogo %s não encontrado — execute seed primeiro', nome_jogo)
            continue

        if jogo.get('gols_mandante') == gols_m and jogo.get('gols_visitante') == gols_v:
            continue

        db.jogo.update_one(
            {'_id': jogo['_id']},
            {'$set': {'gols_mandante': gols_m, 'gols_visitante': gols_v}},
        )
        logger.info('Placar atualizado: %s %d x %d', nome_jogo, gols_m, gols_v)
        _calcula_pontos_apostas(db, jogo['_id'], gols_m, gols_v)

    logger.info('Atualização de resultados do Brasileirão concluída.')


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

    cmd = sys.argv[1] if len(sys.argv) > 1 else 'seed'

    from application.db_config import get_db_client
    _client = get_db_client()
    _db = _client[os.environ.get('MONGO_DB_NAME', 'dev')]

    if cmd == 'seed':
        seed_brasileirao(_db)
    elif cmd == 'update':
        atualiza_resultados_br(_db)
    else:
        print('Uso: python -m application.crawler_brasileirao [seed|update]')
        sys.exit(1)
