
from pymongo import MongoClient
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime


def get_soup(url, prints=False):
    r = requests.get(url)
    if prints:
        print(r.text)
    return BeautifulSoup(r.text, "html.parser")


def monta_selecao(span_informacoes):
    sigla = span_informacoes.find('span', {'class': 'placar-jogo-equipes-sigla'}).text
    selecao_banco = tbl_selecao.find_one({"sigla": sigla})

    if selecao_banco:
        return selecao_banco["_id"]
    else:
        nome = span_informacoes.find('span', {'class': 'placar-jogo-equipes-nome'}).text
        escudo = span_informacoes.find('img')['src']
        time = {"nome": nome,
                "sigla": sigla,
                "escudo": escudo,
                "grupo": nome_grupo}
        return tbl_selecao.insert_one(time).inserted_id


def calcula_pontos(id_jogo):
    pass


def monta_jogo():
    nome_jogo = jogo.find('meta', {'itemprop': 'name'})['content']

    jogo_banco = tbl_jogo.find_one({"nome": nome_jogo})

    gols_mandante = jogo.find('span', {'class': 'placar-jogo-equipes-placar-mandante'}).text
    gols_visitante = jogo.find('span', {'class': 'placar-jogo-equipes-placar-visitante'}).text

    precisa_calcular = False
    if not jogo_banco:
        data = jogo.find('meta', {'itemprop': 'startDate'})['content']
        texto_informacoes = jogo.find('div', {'class': 'placar-jogo-informacoes'}).text
        hora = re.findall(pattern_hora, texto_informacoes)[0]
        local = jogo.find('span', {'class': 'placar-jogo-informacoes-local'}).text
        jogo_obj = {"nome": nome_jogo,
                    "data": datetime.strptime('{0} {1}'.format(data, hora), '%Y-%m-%d %H:%M'),
                    "local": local,
                    "mandante": id_mandante,
                    "visitante": id_visitante,
                    "gols_mandante": gols_mandante,
                    "gols_visitante": gols_visitante,
                    "grupo": nome_grupo,
                    "rodada": rodada}
        id_jogo = tbl_jogo.insert_one(jogo_obj).inserted_id
        precisa_calcular = gols_mandante > ''
    elif gols_mandante != jogo_banco['gols_mandante']:
        precisa_calcular = gols_mandante > ''
        id_jogo = jogo_banco['_id']
        tbl_jogo.update_one({"nome": nome_jogo},
                            {"$set": {"gols_mandante": gols_mandante,
                                      "gols_visitante": gols_visitante}})
        
    if precisa_calcular:
        calcula_pontos(id_jogo)
        

pattern_hora = re.compile(r'\d{2}:\d{2}')

url_base = 'http://globoesporte.globo.com'
url_base_info = 'http://globoesporte.globo.com/futebol/copa-do-mundo/classificacao.html'

client = MongoClient()
db = client.dev

tbl_selecao = db.selecao
tbl_jogo = db.jogo

pagina = get_soup(url_base_info)

for secao_grupo in pagina.find_all('section', {'class': 'section-container'}):
    nome_grupo = secao_grupo.find('h2').text
    url_base_rodadas = secao_grupo.find('aside', {'class': 'lista-de-jogos lista-de-jogos-dentro-grupo'})['data-url-pattern-navegador-jogos']
    numero_rodadas = 3
    for i in range(numero_rodadas):
        rodada = i+1
        url_rodada = url_base + url_base_rodadas + str(rodada) + '/jogos.html'
        pagina_rodada = get_soup(url_rodada)
        for jogo in pagina_rodada.find_all('div', {'class': 'placar-jogo'}):
            mandante = jogo.find('span', {'class': 'placar-jogo-equipes-item placar-jogo-equipes-mandante'})
            visitante = jogo.find('span', {'class': 'placar-jogo-equipes-item placar-jogo-equipes-visitante'})
            id_mandante = monta_selecao(mandante)
            id_visitante = monta_selecao(visitante)
            monta_jogo()

