"""Tests for the scoring logic in GloboEsporteCrawler.

These tests exercise the pure-logic functions that are independent of the
website scraper (which targets 2018 Copa do Mundo pages that no longer exist).
"""
import sys
import os

import pytest

# Import the Crawler class without triggering __init__ (which hits the network).
import application.GloboEsporteCrawler as crawler_module

# Instantiate Crawler bypassing __init__ to test pure logic only.
crawler = crawler_module.Crawler.__new__(crawler_module.Crawler)


class TestResultado:
    def test_mandante_vence(self):
        assert crawler.resultado(2, 0) == 1

    def test_visitante_vence(self):
        assert crawler.resultado(0, 2) == -1

    def test_empate(self):
        assert crawler.resultado(1, 1) == 0

    def test_um_a_zero(self):
        assert crawler.resultado(1, 0) == 1


class TestCalculaPontuacao:
    def test_placar_exato(self):
        pontos, exato, resultado, gols = crawler.calcula_pontuacao(2, 1, 2, 1)
        assert exato is True
        assert pontos == crawler_module.PONTUACAO_PLACAR_EXATO

    def test_placar_exato_empate(self):
        pontos, exato, resultado, gols = crawler.calcula_pontuacao(0, 0, 0, 0)
        assert exato is True
        assert pontos == crawler_module.PONTUACAO_PLACAR_EXATO

    def test_vencedor_correto_mais_gols_mandante(self):
        # Acertou o vencedor E um placar
        pontos, exato, resultado, gols = crawler.calcula_pontuacao(3, 1, 2, 1)
        assert exato is False
        assert resultado is True
        assert gols is True
        assert pontos == crawler_module.PONTUACAO_VENCEDOR_OU_EMPATE + crawler_module.PONTUACAO_GOLS_DE_UM_TIME

    def test_vencedor_correto_sem_gols(self):
        pontos, exato, resultado, gols = crawler.calcula_pontuacao(3, 0, 2, 1)
        assert resultado is True
        assert gols is False
        assert pontos == crawler_module.PONTUACAO_VENCEDOR_OU_EMPATE

    def test_empate_correto_placar_errado(self):
        pontos, exato, resultado, gols = crawler.calcula_pontuacao(1, 1, 2, 2)
        assert exato is False
        assert resultado is True
        assert pontos >= crawler_module.PONTUACAO_VENCEDOR_OU_EMPATE

    def test_gols_de_um_time_visitante(self):
        pontos, exato, resultado, gols = crawler.calcula_pontuacao(1, 2, 0, 2)
        assert gols is True

    def test_nenhum_acerto(self):
        pontos, exato, resultado, gols = crawler.calcula_pontuacao(1, 0, 0, 2)
        assert pontos == 0
        assert exato is False
        assert resultado is False
        assert gols is False

    def test_sem_placar_real(self):
        """Jogo ainda não aconteceu."""
        pontos, exato, resultado, gols = crawler.calcula_pontuacao(None, None, 1, 0)
        assert pontos == 0
        assert exato is False
        assert resultado is False
        assert gols is False

    def test_pontuacao_maxima_valor(self):
        """Placar exato vale mais que qualquer combinação parcial."""
        pontos_exato = crawler_module.PONTUACAO_PLACAR_EXATO
        pontos_parcial = crawler_module.PONTUACAO_VENCEDOR_OU_EMPATE + crawler_module.PONTUACAO_GOLS_DE_UM_TIME
        assert pontos_exato > pontos_parcial


class TestAppImports:
    def test_app_starts(self, flask_app):
        assert flask_app is not None

    def test_intro_page(self, client):
        rv = client.get('/intro')
        assert rv.status_code == 200

    def test_root_redirects_to_intro(self, client):
        rv = client.get('/')
        assert rv.status_code == 200
