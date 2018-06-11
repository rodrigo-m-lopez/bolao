import sys
import os
sys.path.append(os.path.abspath('../../bolao'))

from application.db_config import get_db_client
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime
import os
import pathlib
from bson import ObjectId
import argparse


class Crawler:

    def __init__(self, teste):
        self.teste = teste
        self.pattern_hora = re.compile(r'\d{2}:\d{2}')

        client = get_db_client()
        db = client.dev

        self.tbl_selecao = db.selecao
        self.tbl_jogo = db.jogo
        self.tbl_aposta = db.aposta
        self.tbl_palpite = db.palpite
        self.tbl_pontuacao = db.pontuacao

        url_teste = os.path.abspath("teste_crawler")

        self.url_base = url_teste if teste else 'http://globoesporte.globo.com'
        url_base_info = self.url_base + '/futebol/copa-do-mundo/classificacao.html'

        self.pagina = self.get_soup(url_base_info)

    def get_soup(self, url, prints=False):
        if not self.teste:
            text = requests.get(url).text
        else:
            with open(url, 'r', encoding='latin-1') as myfile:
                text = myfile.read()
        if prints:
            print(text)
        return BeautifulSoup(text, "html.parser")

    def monta_selecao(self, span_informacoes):
        sigla = span_informacoes.find('span', {'class': 'placar-jogo-equipes-sigla'}).text.strip()
        selecao_banco = self.tbl_selecao.find_one({"sigla": sigla})

        if selecao_banco:
            return selecao_banco["_id"]
        else:
            nome = span_informacoes.find('span', {'class': 'placar-jogo-equipes-nome'}).text.strip()
            escudo = span_informacoes.find('img')['src']
            time = {"nome": nome,
                    "sigla": sigla,
                    "escudo": escudo,
                    "grupo": self.nome_grupo}
            return self.tbl_selecao.insert_one(time).inserted_id

    def resultado(self, gols_mandante, gols_visitante):
        # se mandante ganha retorna 1, empate 0, visitante -1
        return (gols_mandante > gols_visitante) - (gols_mandante < gols_visitante)

    def calcula_pontuacao(self, mandante_real, visitante_real, mandante_palpite, visitante_palpite):
        (exato, resultado, gols_um_time) = (False, False, False)
        if mandante_real is None or visitante_real is None:
            return 0, exato, resultado, gols_um_time

        if mandante_real == mandante_palpite and visitante_real == visitante_palpite:
            exato = True
            return PONTUACAO_PLACAR_EXATO, exato, resultado, gols_um_time

        pontuacao = 0
        if self.resultado(mandante_real, visitante_real) == self.resultado(mandante_palpite, visitante_palpite):
            resultado = True
            pontuacao = pontuacao + PONTUACAO_VENCEDOR_OU_EMPATE

        if mandante_real == mandante_palpite or visitante_real == visitante_palpite:
            gols_um_time = True
            pontuacao = pontuacao + PONTUACAO_GOLS_DE_UM_TIME

        return pontuacao, exato, resultado, gols_um_time

    def calcula_pontos_apostas(self, id_jogo, gols_mandante_real, gols_visitante_real):
        for palpite in self.tbl_palpite.find({'jogo': id_jogo}):
            id_aposta = palpite['aposta']
            aposta_banco = self.tbl_aposta.find_one({'_id': id_aposta})
            if aposta_banco is None:
                continue
            jogo_pago = aposta_banco['pago']
            nome_aposta = aposta_banco['nome']
            gols_mandante_palpite = palpite['gols_mandante']
            gols_visitante_palpite = palpite['gols_visitante']
            pontos, exato, resultado, gols_um_time = self.calcula_pontuacao(gols_mandante_real, gols_visitante_real,
                                                                            gols_mandante_palpite,
                                                                            gols_visitante_palpite)
            print('\tPalpite {3} {1} x {2} : {0} pontos'.format(pontos, gols_mandante_palpite, gols_visitante_palpite,
                                                                nome_aposta))
            if jogo_pago:
                self.tbl_pontuacao.update_one({'aposta': id_aposta, 'jogo': id_jogo},
                                              {"$set": {'pontos': pontos,
                                                        'placar_exato': int(exato),
                                                        'vencedor_ou_empate': int(resultado),
                                                        'gols_de_um_time': int(gols_um_time)}})

    def cria_arquivo(self, caminho, conteudo):
        diretorio = os.path.dirname(caminho)
        pathlib.Path(diretorio).mkdir(parents=True, exist_ok=True)
        with open(caminho, "w+") as f:
            f.write(conteudo)

    def txt_to_int(self, text):
        try:
            return int(text.strip())
        except ValueError:
            return None

    def monta_jogo(self):
        jogo = self.jogo
        nome_jogo = jogo.find('meta', {'itemprop': 'name'})['content']

        jogo_banco = self.tbl_jogo.find_one({"nome": nome_jogo})

        gols_mandante = self.txt_to_int(jogo.find('span', {'class': 'placar-jogo-equipes-placar-mandante'}).text)
        gols_visitante = self.txt_to_int(jogo.find('span', {'class': 'placar-jogo-equipes-placar-visitante'}).text)

        if jogo_banco:
            gols_mandante_banco = jogo_banco['gols_mandante']
            gols_visitante_banco = jogo_banco['gols_visitante']

        if not jogo_banco:
            data = jogo.find('meta', {'itemprop': 'startDate'})['content']
            texto_informacoes = jogo.find('div', {'class': 'placar-jogo-informacoes'}).text
            hora = re.findall(self.pattern_hora, texto_informacoes)[0]
            local = jogo.find('span', {'class': 'placar-jogo-informacoes-local'}).text
            jogo_obj = {"nome": nome_jogo,
                        "data": datetime.strptime('{0} {1}'.format(data, hora), '%Y-%m-%d %H:%M'),
                        "local": local,
                        "mandante": self.id_mandante,
                        "visitante": self.id_visitante,
                        "gols_mandante": gols_mandante,
                        "gols_visitante": gols_visitante,
                        "grupo": self.nome_grupo,
                        "rodada": self.rodada,
                        "url_rodada": self.url_relativa_rodada}
            self.tbl_jogo.insert_one(jogo_obj).inserted_id
        elif gols_mandante != gols_mandante_banco or gols_visitante != gols_visitante_banco:
            id_jogo = jogo_banco['_id']
            self.tbl_jogo.update_one({"nome": nome_jogo},
                                     {"$set": {"gols_mandante": gols_mandante,
                                               "gols_visitante": gols_visitante}})
            print('Alteração de placar: {0} de {1} x {2} para {3} x {4}'.format(nome_jogo, gols_mandante_banco,
                                                                                gols_visitante_banco, gols_mandante,
                                                                                gols_visitante))
            self.calcula_pontos_apostas(id_jogo, gols_mandante, gols_visitante)

    def executa(self):
        for secao_grupo in self.pagina.find_all('section', {'class': 'section-container'}):
            self.nome_grupo = secao_grupo.find('h2').text
            url_base_rodadas = secao_grupo.find('aside', {'class': 'lista-de-jogos lista-de-jogos-dentro-grupo'})[
                'data-url-pattern-navegador-jogos']
            numero_rodadas = 3
            for i in range(numero_rodadas):
                self.rodada = i + 1
                self.url_relativa_rodada = url_base_rodadas + str(self.rodada) + '/jogos.html'
                url_rodada = self.url_base + self.url_relativa_rodada

                pagina_rodada = self.get_soup(url_rodada)

                for self.jogo in pagina_rodada.find_all('div', {'class': 'placar-jogo'}):
                    mandante = self.jogo.find('span',
                                              {'class': 'placar-jogo-equipes-item placar-jogo-equipes-mandante'})
                    visitante = self.jogo.find('span',
                                               {'class': 'placar-jogo-equipes-item placar-jogo-equipes-visitante'})
                    self.id_mandante = self.monta_selecao(mandante)
                    self.id_visitante = self.monta_selecao(visitante)
                    self.monta_jogo()

modo_teste = False

PONTUACAO_PLACAR_EXATO = 18
PONTUACAO_VENCEDOR_OU_EMPATE = 9
PONTUACAO_GOLS_DE_UM_TIME = 3


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", help="Modo Teste, verifica em pastas locais por resultados", action='store_true')
    args = parser.parse_args()
    modo_teste = args.test
    Crawler(modo_teste).executa()
