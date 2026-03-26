"""Tests verifying N+1 query fixes."""
import pytest
from unittest.mock import patch, call
from bson import ObjectId
from datetime import datetime
import application.app as app_module
from application.app import (
    monta_dto_apostas, monta_palpites, monta_pontuacoes,
    monta_placares, totaliza_pontuacao_batch,
)
from application.constants import CAMPOS_PONTUACAO_BANCO


def _seed_minimal():
    """Seed DB with 2 apostas, 1 jogo, pontuacoes and palpites."""
    selecao_bra = app_module.tbl_selecao.insert_one(
        {'sigla': 'BRA', 'nome': 'Brasil', 'escudo': 'bra.png', 'grupo': 'Grupo A'}
    ).inserted_id
    selecao_ger = app_module.tbl_selecao.insert_one(
        {'sigla': 'GER', 'nome': 'Alemanha', 'escudo': 'ger.png', 'grupo': 'Grupo A'}
    ).inserted_id
    jogo_id = app_module.tbl_jogo.insert_one({
        'nome': 'BRA x GER',
        'data': datetime(2026, 6, 12, 18, 0),
        'local': 'MetLife',
        'mandante': selecao_bra,
        'visitante': selecao_ger,
        'gols_mandante': 3,
        'gols_visitante': 0,
        'grupo': 'Grupo A',
        'rodada': 1,
        'url_rodada': '/rodada/1',
    }).inserted_id

    user1_id = app_module.tbl_usuario.insert_one(
        {'nome': 'User1', 'email': 'u1@test.com', 'foto': '', 'primeiro_nome': 'User', 'sobrenome': '1', 'sexo': 'm'}
    ).inserted_id
    user2_id = app_module.tbl_usuario.insert_one(
        {'nome': 'User2', 'email': 'u2@test.com', 'foto': '', 'primeiro_nome': 'User', 'sobrenome': '2', 'sexo': 'f'}
    ).inserted_id
    bolao_id = app_module.tbl_bolao.insert_one(
        {'nome': 'bolao1', 'usuario': user1_id, 'valor': 50, 'premiacao': '', 'descricao': ''}
    ).inserted_id

    aposta1_id = app_module.tbl_aposta.insert_one(
        {'nome': 'ap1', 'bolao': bolao_id, 'usuario': user1_id, 'pago': True}
    ).inserted_id
    aposta2_id = app_module.tbl_aposta.insert_one(
        {'nome': 'ap2', 'bolao': bolao_id, 'usuario': user2_id, 'pago': False}
    ).inserted_id

    for aposta_id in (aposta1_id, aposta2_id):
        app_module.tbl_pontuacao.insert_one(
            {'aposta': aposta_id, 'jogo': jogo_id, 'pontos': 18,
             'placar_exato': 1, 'vencedor_ou_empate': 0, 'gols_de_um_time': 0}
        )
        app_module.tbl_palpite.insert_one(
            {'aposta': aposta_id, 'jogo': jogo_id, 'gols_mandante': 3, 'gols_visitante': 0}
        )

    return bolao_id, aposta1_id, aposta2_id, jogo_id


class TestMontaDtoApostasQueryCount:
    def test_usuario_fetched_once_not_per_aposta(self, flask_app):
        _seed_minimal()
        with flask_app.test_request_context('/'):
            with patch.object(app_module.tbl_usuario, 'find', wraps=app_module.tbl_usuario.find) as mock_find:
                monta_dto_apostas('bolao1')
                assert mock_find.call_count == 1, "tbl_usuario.find should be called once, not per aposta"

    def test_pontuacao_fetched_once_not_per_aposta(self, flask_app):
        _seed_minimal()
        with flask_app.test_request_context('/'):
            with patch.object(app_module.tbl_pontuacao, 'find', wraps=app_module.tbl_pontuacao.find) as mock_find:
                monta_dto_apostas('bolao1')
                assert mock_find.call_count == 1, "tbl_pontuacao.find should be called once, not per aposta"

    def test_returns_correct_ranking(self, flask_app):
        _seed_minimal()
        with flask_app.test_request_context('/'):
            result = monta_dto_apostas('bolao1')
        assert len(result) == 2
        assert result[0]['posicao'] == 1


class TestMontaPalpitesQueryCount:
    def test_single_query_for_all_jogos(self, flask_app):
        _, aposta_id, _, jogo_id = _seed_minimal()
        _, todos_jogos = app_module.monta_dto_grupos()
        aposta = {'_id': aposta_id}
        with patch.object(app_module.tbl_palpite, 'find', wraps=app_module.tbl_palpite.find) as mock_find:
            monta_palpites(aposta, todos_jogos)
            assert mock_find.call_count == 1, "tbl_palpite.find should be called once"


class TestMontaPlacaresNoExtraQueries:
    def test_no_jogo_find_one_called(self):
        """monta_placares should use DTO data, not query DB again."""
        _, todos_jogos = app_module.monta_dto_grupos()
        lista = []
        with patch.object(app_module.tbl_jogo, 'find_one') as mock_find_one:
            monta_placares(lista, todos_jogos)
            mock_find_one.assert_not_called()


class TestTotalizaPontuacaoBatch:
    def test_without_date_filter(self):
        ponts = [
            {'jogo': ObjectId(), 'pontos': 18, 'placar_exato': 1, 'vencedor_ou_empate': 0, 'gols_de_um_time': 0},
            {'jogo': ObjectId(), 'pontos': 9,  'placar_exato': 0, 'vencedor_ou_empate': 1, 'gols_de_um_time': 0},
        ]
        result = totaliza_pontuacao_batch(ponts, {}, CAMPOS_PONTUACAO_BANCO)
        assert result['pontos'] == 27
        assert result['placar_exato'] == 1
        assert result['vencedor_ou_empate'] == 1

    def test_with_date_filter(self):
        d1 = datetime(2026, 6, 12)
        d2 = datetime(2026, 6, 20)
        j1_id, j2_id = ObjectId(), ObjectId()
        jogos_data_map = {j1_id: d1, j2_id: d2}
        ponts = [
            {'jogo': j1_id, 'pontos': 18, 'placar_exato': 1, 'vencedor_ou_empate': 0, 'gols_de_um_time': 0},
            {'jogo': j2_id, 'pontos': 9,  'placar_exato': 0, 'vencedor_ou_empate': 1, 'gols_de_um_time': 0},
        ]
        # filter up to d1: only j1 should count
        result = totaliza_pontuacao_batch(ponts, jogos_data_map, CAMPOS_PONTUACAO_BANCO, d1)
        assert result['pontos'] == 18
        assert result['placar_exato'] == 1
        assert result['vencedor_ou_empate'] == 0
