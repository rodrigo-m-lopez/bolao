"""Constantes de pontuação do bolão."""

# Pontuação por acerto
PONTUACAO_PLACAR_EXATO = 18       # Placar exato (ex: 2x1 chutando 2x1)
PONTUACAO_VENCEDOR_OU_EMPATE = 9  # Vencedor correto ou empate correto
PONTUACAO_GOLS_DE_UM_TIME = 3     # Gols corretos de apenas um dos times

# Campos do banco que compõem a pontuação (ordem importa para ranking)
CAMPOS_PONTUACAO_BANCO = ('pontos', 'placar_exato', 'vencedor_ou_empate', 'gols_de_um_time')

# Campos equivalentes no DTO de retorno da API
CAMPOS_PONTUACAO_DTO = ('pontuacao', 'placar_exato', 'vencedor_ou_empate', 'gols_de_um_time')

# Campos do DTO referentes à rodada anterior (para calcular variação)
CAMPOS_PONTUACAO_ANTERIOR = ('pontuacao_ant', 'placar_exato_ant', 'vencedor_ou_empate_ant', 'gols_de_um_time_ant')
