"""MongoDB index definitions for the bolão application.

Run once at startup (or manually) to create indexes on all frequently
queried fields. Safe to call multiple times — MongoDB ignores existing indexes.
"""
import logging
import os

from pymongo import ASCENDING

logger = logging.getLogger(__name__)


def create_indexes(db):
    """Create all application indexes on the given database instance."""

    # bolao: looked up by nome (get_bolao_id, ranking, admin, etc.)
    db.bolao.create_index([('nome', ASCENDING)], unique=True, name='idx_bolao_nome')
    db.bolao.create_index([('usuario', ASCENDING)], name='idx_bolao_usuario')

    # aposta: looked up by bolao+nome (valida_nome_aposta, toggle_pago, etc.)
    db.aposta.create_index(
        [('bolao', ASCENDING), ('nome', ASCENDING)],
        unique=True, name='idx_aposta_bolao_nome'
    )
    db.aposta.create_index([('bolao', ASCENDING)], name='idx_aposta_bolao')
    db.aposta.create_index([('usuario', ASCENDING)], name='idx_aposta_usuario')

    # palpite: looked up by aposta (monta_palpites) and by jogo (crawler)
    db.palpite.create_index(
        [('aposta', ASCENDING), ('jogo', ASCENDING)],
        unique=True, name='idx_palpite_aposta_jogo'
    )
    db.palpite.create_index([('jogo', ASCENDING)], name='idx_palpite_jogo')

    # pontuacao: looked up by aposta (monta_pontuacoes, totaliza_pontuacao_batch)
    # and by aposta+jogo (crawler updates)
    db.pontuacao.create_index(
        [('aposta', ASCENDING), ('jogo', ASCENDING)],
        unique=True, name='idx_pontuacao_aposta_jogo'
    )
    db.pontuacao.create_index([('aposta', ASCENDING)], name='idx_pontuacao_aposta')

    # jogo: upsert key é {nome, competicao}; nome sozinho não é único entre competições
    # Remove índice legado (nome único sem competicao) se ainda existir
    try:
        db.jogo.drop_index('idx_jogo_nome')
    except Exception:
        pass
    db.jogo.create_index(
        [('nome', ASCENDING), ('competicao', ASCENDING)],
        unique=True, name='idx_jogo_nome_competicao',
    )
    db.jogo.create_index([('data', ASCENDING)], name='idx_jogo_data')
    db.jogo.create_index(
        [('grupo', ASCENDING), ('rodada', ASCENDING), ('data', ASCENDING)],
        name='idx_jogo_sort'
    )
    # gols_mandante: filtered in obtem_datas_rodadas_com_pontuacao
    db.jogo.create_index([('gols_mandante', ASCENDING)], name='idx_jogo_gols_mandante')

    # usuario: looked up by email (oauth_callback, Usuario.__init__)
    db.usuario.create_index([('email', ASCENDING)], unique=True, name='idx_usuario_email')

    # selecao: looked up by sigla (crawler monta_selecao)
    db.selecao.create_index([('sigla', ASCENDING)], unique=True, name='idx_selecao_sigla')

    # historico: looked up by horario+aposta (calcula_posicao)
    db.historico.create_index(
        [('horario', ASCENDING), ('aposta', ASCENDING)],
        unique=True, name='idx_historico_horario_aposta'
    )

    logger.info('Índices MongoDB criados/verificados com sucesso.')


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '.')
    logging.basicConfig(level=logging.INFO)
    from application.db_config import get_db_client
    _client = get_db_client()
    _db_name = os.environ.get('MONGO_DB_NAME', 'dev')
    create_indexes(_client[_db_name])
