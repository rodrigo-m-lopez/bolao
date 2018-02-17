import pymongo
from flask import Flask
from flask import request
from flask import render_template
from pymongo import MongoClient
from operator import itemgetter

client = MongoClient()
db = client.dev
tbl_jogo = db.jogo
tbl_selecao = db.selecao
tbl_usuario = db.usuario
tbl_palpite = db.palpite
tbl_pontuacao = db.pontuacao
app = Flask(__name__)
grupos = {}
todos_jogos = []


@app.route('/')
def inicio():
    return ranking()


@app.route('/aposta', methods=['GET', 'POST'])
def aposta():
    grupos = monta_dto_grupos()
    if request.method == 'GET':
        return render_template('aposta.html', grupos=grupos)
    else:
        if not usuario_ja_existe(request.form['inputNome']):
            id_usuario = tbl_usuario.insert_one({'nome': request.form['inputNome'],
                                                 'email': request.form['inputEmail'],
                                                 'pago': False}).inserted_id
            insere_palpites(id_usuario, request.form)
            insere_pontuacoes(id_usuario)
            return ranking()
        else:
            return render_template('aposta.html', grupos=grupos, nome_existente=request.form['inputNome'])


@app.route('/ranking')
def ranking():
    lista_usuarios = monta_dto_usuarios()
    return render_template('ranking.html', lista_usuarios=lista_usuarios)


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'GET':
        lista_usuarios = monta_dto_usuarios()
        return render_template('admin.html', lista_usuarios=lista_usuarios)
    else:
        pass


@app.route('/valida_usuario', methods=['POST'])
def valida_usuario():
    novo_usuario = request.form['novo_usuario']

    if usuario_ja_existe(novo_usuario):
        return '''<div class="alert alert-danger alert-dismissible fade show" style="width: 52rem;">
	              Nome <Strong>{0}</Strong> já existe para este bolão, escolha outro</div>'''.format(novo_usuario)
    else:
        return ''


@app.route('/toggle_pago', methods=['POST'])
def toggle_pago():
    nome_usuario = request.form['usuario']
    usuario = tbl_usuario.find_one({'nome': nome_usuario})
    novo_pago = not usuario['pago']

    tbl_usuario.update_one({"nome": nome_usuario},
                           {"$set": {"pago": novo_pago}})
    return 'on' if novo_pago else 'off'


def totaliza_pontuacao(id_usuario):
    total = 0
    for pontuacao in tbl_pontuacao.find({'usuario': id_usuario}):
        total = total + pontuacao["pontos"]
    return total

def monta_dto_usuarios():
    lista_retorno = []

    for usuario in tbl_usuario.find():
        pontuacao_usuario = totaliza_pontuacao(str(usuario["_id"]))
        lista_retorno.append({"nome": usuario["nome"],
                              "pontuacao": pontuacao_usuario,
                              "pago": usuario["pago"]})
    return sorted(lista_retorno, key=itemgetter('pontuacao'), reverse=True)


def insere_pontuacoes(usuario):
    for jogo in todos_jogos:
        id_jogo = jogo["_id"]
        id_usuario = str(usuario)
        tbl_pontuacao.insert_one({'usuario': id_usuario,
                                  'jogo': id_jogo,
                                  'pontos': 0})


def insere_palpites(usuario, form):
    for jogo in todos_jogos:
        id_jogo = jogo["_id"]
        id_usuario = str(usuario)
        id_mandante_form = 'm{0}'.format(id_jogo)
        id_visitante_form = 'v{0}'.format(id_jogo)
        tbl_palpite.insert_one({'usuario': id_usuario,
                                'jogo': id_jogo,
                                'gols_mandante': int(form[id_mandante_form]),
                                'gols_visitante': int(form[id_visitante_form])})


def usuario_ja_existe(nome_usuario):
    return tbl_usuario.find_one({'nome': nome_usuario}) != None


def monta_dto_jogo(jogo):
    mandante = tbl_selecao.find_one({'_id': jogo["mandante"]})
    visitante = tbl_selecao.find_one({'_id': jogo["visitante"]})
    return {"_id": str(jogo["_id"]),
            "nome": jogo["nome"],
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
    dto_jogo = monta_dto_jogo(jogo)
    jogos.append(dto_jogo)
    todos_jogos.append(dto_jogo)


def monta_dto_grupos():
    if not grupos:
        # for jogo in tbl_jogo.find({'grupo': 'Grupo A', 'rodada': 1}):  # para testar com menos jogos
        for jogo in tbl_jogo.find():
            nome_grupo = jogo["grupo"]
            if nome_grupo not in grupos.keys():
                grupos[nome_grupo] = {"nome": nome_grupo,
                                      "rodadas": []}

            rodadas = grupos[nome_grupo]["rodadas"]
            inclui_jogo_na_lista_rodadas(rodadas, jogo)
    return grupos.values()
