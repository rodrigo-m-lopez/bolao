from pymongo import MongoClient
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime
import os
import pathlib
from bson import ObjectId
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--test", help="Modo Teste, verifica em pastas locais por resultados", action='store_true')
args = parser.parse_args()
modo_teste = args.test

PONTUACAO_PLACAR_EXATO = 18
PONTUACAO_VENCEDOR_OU_EMPATE = 9
PONTUACAO_GOLS_DE_UM_TIME = 3


def get_soup(url, prints=False):
    if not modo_teste:
        text = requests.get(url).text
    else:
        with open(url, 'r') as myfile:
            text = myfile.read()
    if prints:
        print(text)
    return BeautifulSoup(text, "html.parser")


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


def resultado(gols_mandante, gols_visitante):
    # se mandante ganha retorna 1, empate 0, visitante -1
    return (gols_mandante > gols_visitante) - (gols_mandante < gols_visitante)


def calcula_pontuacao(mandante_real, visitante_real, mandante_palpite, visitante_palpite):
    if mandante_real == mandante_palpite and visitante_real == visitante_palpite:
        return PONTUACAO_PLACAR_EXATO

    pontuacao = 0
    if resultado(mandante_real, visitante_real) == resultado(mandante_palpite, visitante_palpite):
        pontuacao = pontuacao + PONTUACAO_VENCEDOR_OU_EMPATE

    if mandante_real == mandante_palpite or visitante_real == visitante_palpite:
        pontuacao = pontuacao + PONTUACAO_GOLS_DE_UM_TIME

    return pontuacao


def calcula_pontos_usuarios(id_jogo, gols_mandante_real, gols_visitante_real):
    for palpite in tbl_palpite.find({'jogo': id_jogo}):
        usuario = palpite['usuario']
        usuario_banco = tbl_usuario.find_one({'_id': ObjectId(usuario)})		
        jogo_pago = usuario_banco['pago']
        nome_usuario = usuario_banco['nome']
        gols_mandante_palpite = palpite['gols_mandante']
        gols_visitante_palpite = palpite['gols_visitante']
        pontos = calcula_pontuacao(gols_mandante_real, gols_visitante_real, gols_mandante_palpite,
                                   gols_visitante_palpite)
        print('\tPalpite {3} {1} x {2} : {0} pontos'.format(pontos, gols_mandante_palpite, gols_visitante_palpite, nome_usuario))
        if jogo_pago:
            tbl_pontuacao.update_one({'usuario': usuario, 'jogo': id_jogo},
                                     {"$set": {"pontos": pontos}})


def cria_arquivo(caminho, conteudo):
    diretorio = os.path.dirname(caminho)
    pathlib.Path(diretorio).mkdir(parents=True, exist_ok=True)
    with open(caminho, "w+") as f:
        f.write(conteudo)


def txt_to_int(text):
    try:
        return int(text.strip())
    except ValueError:
        return None


def monta_jogo():
    nome_jogo = jogo.find('meta', {'itemprop': 'name'})['content']

    jogo_banco = tbl_jogo.find_one({"nome": nome_jogo})

    gols_mandante = txt_to_int(jogo.find('span', {'class': 'placar-jogo-equipes-placar-mandante'}).text)
    gols_visitante = txt_to_int(jogo.find('span', {'class': 'placar-jogo-equipes-placar-visitante'}).text)

    if jogo_banco:
        gols_mandante_banco = jogo_banco['gols_mandante']
        gols_visitante_banco = jogo_banco['gols_visitante']

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
                    "rodada": rodada,
                    "url_rodada": url_relativa_rodada}
        tbl_jogo.insert_one(jogo_obj).inserted_id
    elif gols_mandante != gols_mandante_banco or gols_visitante != gols_visitante_banco:
        id_jogo = str(jogo_banco['_id'])
        tbl_jogo.update_one({"nome": nome_jogo},
                            {"$set": {"gols_mandante": gols_mandante,
                                      "gols_visitante": gols_visitante}})
        if gols_mandante is not None and gols_visitante is not None:
            print('Alteração de placar: {0} de {1} x {2} para {3} x {4}'.format(nome_jogo, gols_mandante_banco,
                                                                                gols_visitante_banco, gols_mandante,
                                                                                gols_visitante))
            calcula_pontos_usuarios(id_jogo, gols_mandante, gols_visitante)


pattern_hora = re.compile(r'\d{2}:\d{2}')

url_teste = os.path.abspath("teste_crawler")
url_base = url_teste if modo_teste else 'http://globoesporte.globo.com'
url_base_info = url_base + '/futebol/copa-do-mundo/classificacao.html'

client = MongoClient()
db = client.dev

tbl_selecao = db.selecao
tbl_jogo = db.jogo
tbl_usuario = db.usuario
tbl_palpite = db.palpite
tbl_pontuacao = db.pontuacao

pagina = get_soup(url_base_info)

for secao_grupo in pagina.find_all('section', {'class': 'section-container'}):
    nome_grupo = secao_grupo.find('h2').text
    url_base_rodadas = secao_grupo.find('aside', {'class': 'lista-de-jogos lista-de-jogos-dentro-grupo'})[
        'data-url-pattern-navegador-jogos']
    numero_rodadas = 3
    for i in range(numero_rodadas):
        rodada = i + 1
        url_relativa_rodada = url_base_rodadas + str(rodada) + '/jogos.html'
        url_rodada = url_base + url_relativa_rodada

        pagina_rodada = get_soup(url_rodada)

        for jogo in pagina_rodada.find_all('div', {'class': 'placar-jogo'}):
            mandante = jogo.find('span', {'class': 'placar-jogo-equipes-item placar-jogo-equipes-mandante'})
            visitante = jogo.find('span', {'class': 'placar-jogo-equipes-item placar-jogo-equipes-visitante'})
            id_mandante = monta_selecao(mandante)
            id_visitante = monta_selecao(visitante)
            monta_jogo()
