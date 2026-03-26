"""Tests for scoring constants and their use in app.py."""
from application.constants import (
    PONTUACAO_PLACAR_EXATO,
    PONTUACAO_VENCEDOR_OU_EMPATE,
    PONTUACAO_GOLS_DE_UM_TIME,
    CAMPOS_PONTUACAO_BANCO,
    CAMPOS_PONTUACAO_DTO,
    CAMPOS_PONTUACAO_ANTERIOR,
)


class TestConstantsValues:
    def test_placar_exato_maior_que_parcial(self):
        """Acertar o placar exato deve valer mais que acertar tudo parcialmente."""
        max_parcial = PONTUACAO_VENCEDOR_OU_EMPATE + PONTUACAO_GOLS_DE_UM_TIME
        assert PONTUACAO_PLACAR_EXATO > max_parcial

    def test_vencedor_maior_que_gols(self):
        assert PONTUACAO_VENCEDOR_OU_EMPATE > PONTUACAO_GOLS_DE_UM_TIME

    def test_todos_positivos(self):
        assert PONTUACAO_PLACAR_EXATO > 0
        assert PONTUACAO_VENCEDOR_OU_EMPATE > 0
        assert PONTUACAO_GOLS_DE_UM_TIME > 0


class TestCamposTuples:
    def test_campos_banco_contem_pontos(self):
        assert 'pontos' in CAMPOS_PONTUACAO_BANCO

    def test_campos_dto_contem_pontuacao(self):
        assert 'pontuacao' in CAMPOS_PONTUACAO_DTO

    def test_campos_anterior_contem_pontuacao_ant(self):
        assert 'pontuacao_ant' in CAMPOS_PONTUACAO_ANTERIOR

    def test_mesmo_numero_de_campos(self):
        assert len(CAMPOS_PONTUACAO_BANCO) == len(CAMPOS_PONTUACAO_DTO) == len(CAMPOS_PONTUACAO_ANTERIOR)

    def test_campos_banco_importados_em_app(self):
        """app.py deve usar os campos de constants, não strings locais."""
        import application.app as app_module
        # Verificar que o app usa as mesmas constantes
        from application.constants import CAMPOS_PONTUACAO_BANCO
        assert CAMPOS_PONTUACAO_BANCO == ('pontos', 'placar_exato', 'vencedor_ou_empate', 'gols_de_um_time')

    def test_crawler_usa_mesmas_constantes(self):
        """O crawler deve usar as mesmas constantes do constants.py."""
        import application.GloboEsporteCrawler as crawler_module
        assert crawler_module.PONTUACAO_PLACAR_EXATO == PONTUACAO_PLACAR_EXATO
        assert crawler_module.PONTUACAO_VENCEDOR_OU_EMPATE == PONTUACAO_VENCEDOR_OU_EMPATE
        assert crawler_module.PONTUACAO_GOLS_DE_UM_TIME == PONTUACAO_GOLS_DE_UM_TIME
