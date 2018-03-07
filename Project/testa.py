import argparse
from pymongo import MongoClient
import sys
from bs4 import BeautifulSoup
import os

encoding = 'latin-1'
def get_soup(url, prints=False):
    with open(url, 'r', encoding=encoding) as myfile:
        text = myfile.read()

    soup = BeautifulSoup(text, "html.parser")
    if prints:
        print(soup.prettify())
    return soup


def altera_jogo():
    url_rodada_jogo = url_teste + jogo['url_rodada']

    if alterar_resultado(url_rodada_jogo):
        print('Alteração de placar: {} x {} de {} x {} para {} x {}'.format(time_mandante, time_visitante,
                                                                            jogo["gols_mandante"],
                                                                            jogo["gols_visitante"],
                                                                            placar_mandante, placar_visitante))
    else:
        print('não foi possível encontrar o jogo no arquivo {}'.format(url_rodada_jogo))

def alterar_resultado(url_rodada_jogo):
    pagina_rodada = get_soup(url_rodada_jogo)
    for li in pagina_rodada.find_all('li'):
        if li.meta['content'] == jogo['nome']:
            span_mandante = li.find('span', {'class': 'placar-jogo-equipes-placar-mandante'})
            span_visitante = li.find('span', {'class': 'placar-jogo-equipes-placar-visitante'})
            span_mandante.string = str(placar_mandante)
            span_visitante.string = str(placar_visitante)
            html = pagina_rodada.prettify(encoding)
            with open(url_rodada_jogo, "wb") as file:
                file.write(html)
            return True

    return False


def executa_crawler_teste():
    if os.name == 'nt': #Windows
        os.system(r"..\venv\Scripts\python.exe GloboEsporteCrawler.py --test")
    else:
        os.system(r"..\venv\bin\python GloboEsporteCrawler.py --test")

url_teste = os.path.abspath("teste_crawler")

parser = argparse.ArgumentParser()
parser.add_argument("-j", "--jogo", help="jogo que se deseja alterar o placar, formato: RUS_URU")
parser.add_argument("-p", "--placar", help="placar do jogo a ser setado, formato 1_0")
args = parser.parse_args()

client = MongoClient()
db = client.dev

tbl_selecao = db.selecao
tbl_jogo = db.jogo

arg_placar = args.placar

placar_mandante = arg_placar.split('_')[0] if arg_placar else ''
placar_visitante = arg_placar.split('_')[1] if arg_placar else ''

arg_jogo = args.jogo

if arg_jogo:
    sigla_mandante = arg_jogo.split('_')[0]
    sigla_visitante = arg_jogo.split('_')[1]

    selecao_mandante = tbl_selecao.find_one({"sigla": sigla_mandante})
    if selecao_mandante:
        time_mandante = selecao_mandante["nome"]
    else:
        print('Sigla {0} não corresponde a nenhuma seleção.'.format(sigla_mandante))
        sys.exit()

    selecao_visitante = tbl_selecao.find_one({"sigla": sigla_visitante})
    if selecao_visitante:
        time_visitante = selecao_visitante["nome"]
    else:
        print('Sigla {0} não corresponde a nenhuma seleção.'.format(sigla_visitante))
        sys.exit()

    jogo = tbl_jogo.find_one({"mandante": selecao_mandante["_id"], "visitante": selecao_visitante["_id"]})

    if not jogo:
        (selecao_mandante, selecao_visitante) = (selecao_visitante, selecao_mandante)
        (placar_mandante, placar_visitante) = (placar_visitante, placar_mandante)
        jogo = tbl_jogo.find_one({"mandante": selecao_mandante["_id"], "visitante": selecao_visitante["_id"]})

    if jogo:
        altera_jogo()
        executa_crawler_teste()
    else:
        print('Jogo {} x {} não existe.'.format(time_visitante, time_mandante))
else:
    for jogo in tbl_jogo.find():
        time_mandante = tbl_selecao.find_one({'id': jogo['mandante']})
        time_visitante = tbl_selecao.find_one({'id': jogo['visitante']})
        altera_jogo()
    executa_crawler_teste()








