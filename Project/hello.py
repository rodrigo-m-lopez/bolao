import pymongo
from flask import Flask
from flask import request
from flask import render_template
from pymongo import MongoClient

client = MongoClient()
db = client.dev
tbl_jogo = db.jogo
tbl_selecao = db.selecao
app = Flask(__name__)
grupos = {}


@app.route('/')
def inicio():
    return ranking()


@app.route('/aposta', methods=['GET', 'POST'])
def aposta():
    grupos = monta_dto_grupos()
    if request.method == 'GET':
        return render_template('aposta.html', grupos=grupos)


@app.route('/ranking')
def ranking():
    if request.method == 'GET':
        return render_template('ranking.html')


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'GET':
        return render_template('admin.html')
    else:
        pass


@app.route('/valida_usuario', methods=['POST'])
def valida_usuario():
    novo_usuario = request.form['novo_usuario']

    if novo_usuario == 'teste':
        return '''<div class="alert alert-danger alert-dismissible fade show" style="width: 52rem;">
	              Nome <Strong>{0}</Strong> já existe para este bolão, escolha outro</div>'''.format(novo_usuario)
    else:
        return ''


def monta_dto_jogo(jogo):
    mandante = tbl_selecao.find_one({'_id': jogo["mandante"]})
    visitante = tbl_selecao.find_one({'_id': jogo["visitante"]})
    return {"nome": jogo["nome"],
            "escudo_mandante": mandante["escudo"],
            "escudo_visitante": visitante["escudo"],
            "nome_mandante": mandante["nome"],
            "nome_visitante": visitante["nome"],
            "id_input_mandante": 'm{0}'.format(str(jogo["_id"])),
            "id_input_visitante": 'v{0}'.format(str(jogo["_id"])),
            "data": jogo["data"].strftime('%d/%m %H:%M'),
            "local": jogo["local"]}


def inclui_jogo_na_lista_rodadas(lista_rodadas, jogo):
    rodada_do_jogo = jogo["rodada"]

    existe_rodada_na_lista = False
    for rodada in lista_rodadas:
        if rodada["numero"] == rodada_do_jogo:
            existe_rodada_na_lista = True
            jogos = rodada["jogos"]
            break

    if not existe_rodada_na_lista:
        jogos = []
        lista_rodadas.append({"numero": rodada_do_jogo,
                              "nome": '{0}ª Rodada'.format(rodada_do_jogo),
                              "jogos": jogos})

    jogos.append(monta_dto_jogo(jogo))


def monta_dto_grupos():
    if not grupos:
        for jogo in tbl_jogo.find({'grupo': 'Grupo A', 'rodada': 1}):  # para testar com menos jogos
            # for jogo in tbl_jogo.find():
            nome_grupo = jogo["grupo"]
            if nome_grupo not in grupos.keys():
                grupos[nome_grupo] = {"nome": nome_grupo,
                                      "rodadas": []}

            rodadas = grupos[nome_grupo]["rodadas"]
            inclui_jogo_na_lista_rodadas(rodadas, jogo)
    return grupos.values()
