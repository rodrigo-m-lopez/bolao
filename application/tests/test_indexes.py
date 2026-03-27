"""Tests for MongoDB index creation."""
import application.app as app_module
from application.db_indexes import create_indexes


class TestIndexesCreated:
    def setup_method(self):
        create_indexes(app_module.db)

    def test_bolao_nome_index_exists(self):
        info = app_module.db.bolao.index_information()
        names = list(info.keys())
        assert any('nome' in n or 'idx_bolao_nome' in n for n in names)

    def test_aposta_bolao_nome_index_exists(self):
        info = app_module.db.aposta.index_information()
        names = list(info.keys())
        assert any('idx_aposta_bolao_nome' in n for n in names)

    def test_palpite_aposta_jogo_index_exists(self):
        info = app_module.db.palpite.index_information()
        names = list(info.keys())
        assert any('idx_palpite_aposta_jogo' in n for n in names)

    def test_pontuacao_aposta_index_exists(self):
        info = app_module.db.pontuacao.index_information()
        names = list(info.keys())
        assert any('idx_pontuacao_aposta' in n for n in names)

    def test_jogo_nome_unique_index_exists(self):
        info = app_module.db.jogo.index_information()
        names = list(info.keys())
        assert any('idx_jogo_nome' in n for n in names)

    def test_jogo_data_index_exists(self):
        info = app_module.db.jogo.index_information()
        names = list(info.keys())
        assert any('idx_jogo_data' in n for n in names)

    def test_usuario_email_unique_index_exists(self):
        info = app_module.db.usuario.index_information()
        names = list(info.keys())
        assert any('idx_usuario_email' in n for n in names)

    def test_selecao_sigla_unique_index_exists(self):
        info = app_module.db.selecao.index_information()
        names = list(info.keys())
        assert any('idx_selecao_sigla' in n for n in names)

    def test_historico_index_exists(self):
        info = app_module.db.historico.index_information()
        names = list(info.keys())
        assert any('idx_historico_horario_aposta' in n for n in names)

    def test_create_indexes_idempotent(self):
        """Calling create_indexes twice should not raise."""
        create_indexes(app_module.db)  # already called at import; calling again should be safe
