import argparse
from pymongo import MongoClient
import sys
from bs4 import BeautifulSoup
import os

def get_soup(url, prints=False):
    with open(url, 'r') as myfile:
        text = myfile.read()

    soup = BeautifulSoup(text, "html.parser")
    if prints:
        print(soup.prettify())
    return soup


url_teste = os.path.abspath("teste_crawler")


parser = argparse.ArgumentParser()
parser.add_argument("-j", "--jogo", help="jogo que se deseja alterar o placar, formato: RUS_URU")
parser.add_argument("-p", "--placar", help="placar do jogo a ser setado, formato 1_0",default='0_0')
args = parser.parse_args()
open_encoding = 'latin-1'

client = MongoClient()
db = client.dev

tbl_selecao = db.selecao
tbl_jogo = db.jogo

jogo = args.jogo
sigla_mandante = jogo.split('_')[0]
sigla_visitante = jogo.split('_')[1]

placar = args.placar
placar_mandante = int(placar.split('_')[0])
placar_visitante = int(placar.split('_')[1])

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
    url_rodada_jogo = url_teste + jogo['url_rodada']

    get_soup(url_rodada_jogo, True)
    print('Alteração de placar: {} x {} de {} x {} para {} x {}'.format(time_mandante, time_visitante,
                                                                    jogo["gols_mandante"], jogo["gols_visitante"],
                                                                    placar_mandante, placar_visitante))
else:
    print('Jogo {} x {} não existe.'.format(time_visitante, time_mandante))