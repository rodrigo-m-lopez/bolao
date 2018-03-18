# coding: latin-1

import pymongo
from flask import Flask
from flask import request
from flask import render_template
from operator import itemgetter
import uuid
import hashlib
from bson import ObjectId

import Project.db_config as db_config
client = db_config.get_db_client()

db = client.dev
tbl_jogo = db.jogo
tbl_selecao = db.selecao
tbl_usuario = db.usuario
tbl_bolao = db.bolao
tbl_palpite = db.palpite
tbl_pontuacao = db.pontuacao
app = Flask(__name__)
grupos = {}
todos_jogos = []



@app.route('/')
def inicio():
    return lista_bolao()


@app.route('/novo_bolao', methods=['GET', 'POST'])
def novo_bolao():
    if request.method == 'GET':
        return render_template('novo_bolao.html')
    else:
        erro_validacao = valida_informacoes_bolao(request.form)
        if erro_validacao:
            return render_template('novo_bolao.html', erro=erro_validacao)
        cria_bolao(request.form)
        return lista_bolao()


@app.route('/lista_bolao')
def lista_bolao():
    boloes = monta_dto_boloes()
    return render_template('lista_bolao.html', lista_boloes=boloes)


@app.route('/<bolao>/aposta', methods=['GET', 'POST'])
def aposta(bolao):
    grupos = monta_dto_grupos()
    id_bolao = tbl_bolao.find_one({'nome': bolao})['_id']
    if request.method == 'GET':
        return render_template('aposta.html', grupos=grupos, bolao=bolao)
    else:
        if not usuario_ja_existe(request.form['inputNome'], id_bolao):
            id_usuario = tbl_usuario.insert_one({'nome': request.form['inputNome'],
                                                 'email': request.form['inputEmail'],
                                                 'bolao': id_bolao,
                                                 'pago': False}).inserted_id
            insere_palpites(id_usuario, request.form)
            insere_pontuacoes(id_usuario)
            return ranking(bolao)
        else:
            return render_template('aposta.html', bolao=bolao, grupos=grupos, nome_existente=request.form['inputNome'])


@app.route('/<bolao>/ranking')
def ranking(bolao):
    lista_usuarios = monta_dto_usuarios(bolao)
    return render_template('ranking.html', bolao=bolao, lista_usuarios=lista_usuarios)


@app.route('/<bolao>/admin', methods=['GET', 'POST'])
def admin(bolao):
    if request.method == 'GET':
        return render_template('valida_admin_bolao.html', bolao=bolao)
    else:
        input_senha_admin = request.form['senhaAdmin']
        hashed_password = tbl_bolao.find_one({'nome': bolao})['senhaAdmin']

        if check_password(hashed_password, input_senha_admin):
            lista_usuarios = monta_dto_usuarios(bolao)
            return render_template('admin.html', bolao=bolao, lista_usuarios=lista_usuarios)
        else:
            return render_template('valida_admin_bolao.html', bolao=bolao, erro='Senha Invalida')

@app.route('/valida_nome_bolao', methods=['POST'])
def valida_nome_bolao():
    nome_bolao = request.form['nome_bolao']
    return valida_nome_bolao_ja_existe(nome_bolao)


@app.route('/<bolao>/valida_usuario', methods=['POST'])
def valida_usuario(bolao):
    novo_usuario = request.form['novo_usuario']
    id_bolao = tbl_bolao.find_one({'nome': bolao})['_id']

    if usuario_ja_existe(novo_usuario, id_bolao):
        return '''Nome <Strong>{0}</Strong> já existe para este bolão, escolha outro'''.format(novo_usuario)
    else:
        return ''


@app.route('/<bolao>/toggle_pago', methods=['POST'])
def toggle_pago(bolao):
    id_bolao = tbl_bolao.find_one({'nome': bolao})['_id']
    nome_usuario = request.form['usuario']
    usuario = tbl_usuario.find_one({'nome': nome_usuario, 'bolao': id_bolao})
    novo_pago = not usuario['pago']

    tbl_usuario.update_one({"nome": nome_usuario,
                            'bolao': id_bolao},
                           {"$set": {"pago": novo_pago}})
    return 'on' if novo_pago else 'off'


@app.route('/<bolao>/palpite/<nome_usuario>')
def palpite(bolao, nome_usuario):
    id_bolao = tbl_bolao.find_one({'nome': bolao})['_id']
    usuario = tbl_usuario.find_one({'nome': nome_usuario, 'bolao': id_bolao})
    monta_dto_grupos()
    jogos = todos_jogos
    palpites = monta_palpites(usuario)
    pontuacoes = monta_pontuacoes(usuario)
    lista_jogos_ordem_tela = []
    placares = monta_placares(lista_jogos_ordem_tela)

    return render_template('palpites.html', bolao=bolao, jogos=lista_jogos_ordem_tela, palpites=palpites,
                           pontuacoes=pontuacoes, placares=placares, nome_usuario=nome_usuario)


def monta_placares(lista_jogos_ordem_tela):
    placares = {}
    lista_sem_resultados = []
    lista_com_resultados = []
    for jogo in todos_jogos:
        id_jogo = ObjectId(jogo['_id'])
        jogo_banco = tbl_jogo.find_one({'_id': id_jogo})
        lista = lista_sem_resultados if jogo_banco['gols_mandante'] is None else lista_com_resultados
        lista.append(jogo)
        gols_mandante = '-' if jogo_banco['gols_mandante'] is None else jogo_banco['gols_mandante']
        gols_visitante = '-' if jogo_banco['gols_visitante'] is None else jogo_banco['gols_visitante']
        placares[jogo['nome']] = '{} x {}'.format(gols_mandante, gols_visitante)

    lista_com_resultados.sort(key=itemgetter('date_time'), reverse=True)
    lista_sem_resultados.sort(key=itemgetter('date_time'), reverse=False)
    lista_com_resultados.extend(lista_sem_resultados)
    lista_jogos_ordem_tela.extend(lista_com_resultados)
    return placares


def monta_pontuacoes(usuario):
    pontuacoes = {}
    for jogo in todos_jogos:
        pontuacao_jogo = tbl_pontuacao.find_one({'usuario': str(usuario['_id']),
                                                 'jogo': str(jogo['_id'])})
        pontuacoes[jogo['nome']] = pontuacao_jogo['pontos']
    return pontuacoes


def monta_palpites(usuario):
    palpites = {}
    for jogo in todos_jogos:
        palpite_jogo = tbl_palpite.find_one({'usuario': str(usuario['_id']),
                                             'jogo': str(jogo['_id'])})
        palpites[jogo['nome']] = '{} x {}'.format(palpite_jogo['gols_mandante'], palpite_jogo['gols_visitante'])
    return palpites


def hash_password(password, salt=None):
    if salt is None:
        salt = uuid.uuid4().hex
    return hashlib.sha256(salt.encode() + password.encode()).hexdigest() + ':' + salt


def check_password(hashed_password, user_password):
    password, salt = hashed_password.split(':')
    return password == hashlib.sha256(salt.encode() + user_password.encode()).hexdigest()


def cria_bolao(form):
    tbl_bolao.insert_one({'nome': form['inputNome'],
                          'responsavel': form['inputResponsavel'],
                          'email': form['inputEmail'],
                          'valor': int(form['inputValor']),
                          'senhaAdmin': hash_password(form['inputSenhaAdmin']),
                          'descricao': form['inputDescricao']})


def valida_nome_bolao_ja_existe(nome_bolao):
    if tbl_bolao.find_one({'nome': nome_bolao}) is not None:
        return '''Nome <Strong>{0}</Strong> já foi escolhido para um bolão, escolha outro'''.format(nome_bolao)
    else:
        return ''


def valida_campo_preenchido(valor_campo, nome_campo):
    if valor_campo == '':
        return '''Campo <Strong>{0}</Strong> é de preenchimento obrigatório'''.format(nome_campo)
    else:
        return ''


def valida_campo_numerico(valor_campo):
    try:
        inteiro = int(valor_campo.strip())
        if inteiro < 0:
            return 'O campo valor não pode ser negativo'
        return ''
    except ValueError:
        return 'O campo Valor precisa ser um número'


def valida_senhas_iguais(senha1, senha2):
    if senha1 != senha2:
        return 'Senhas não conferem.'
    return ''


def valida_informacoes_bolao(form):
    validacoes = [valida_nome_bolao_ja_existe(form['inputNome']),
                  valida_campo_preenchido(form['inputResponsavel'], 'Responsável'),
                  valida_campo_preenchido(form['inputEmail'], 'Email do Responsável'),
                  valida_campo_preenchido(form['inputValor'], 'Valor'),
                  valida_campo_numerico(form['inputValor']),
                  valida_campo_preenchido(form['inputSenhaAdmin'], 'Senha do Admin'),
                  valida_campo_preenchido(form['inputSenhaAdminRepetida'], 'Repetição da senha do Admin'),
                  valida_senhas_iguais(form['inputSenhaAdmin'], form['inputSenhaAdminRepetida'])]
    for erro in validacoes:
        if erro > '':
            return erro
    return ''


def totaliza_pontuacao(id_usuario, campo):
    total = 0
    for pontuacao in tbl_pontuacao.find({'usuario': id_usuario}):
        total = total + pontuacao[campo]
    return total


def monta_dto_usuarios(bolao):
    lista_retorno = []
    id_bolao = tbl_bolao.find_one({'nome': bolao})['_id']
    for usuario in tbl_usuario.find({'bolao': id_bolao}):
        pontuacao_usuario = totaliza_pontuacao(str(usuario["_id"]), 'pontos')
        placares_exatos_usuario = totaliza_pontuacao(str(usuario["_id"]), 'placar_exato')
        vencedor_ou_empate_usuario = totaliza_pontuacao(str(usuario["_id"]), 'vencedor_ou_empate')
        gols_de_um_time_usuario =totaliza_pontuacao(str(usuario["_id"]), 'gols_de_um_time')
        lista_retorno.append({"nome": usuario["nome"],
                              "pontuacao": pontuacao_usuario,
                              "placar_exato": placares_exatos_usuario,
                              "vencedor_ou_empate": vencedor_ou_empate_usuario,
                              "gols_de_um_time": gols_de_um_time_usuario,
                              "pago": usuario["pago"]})
    return sorted(lista_retorno, key=itemgetter('pontuacao', 'placar_exato', 'vencedor_ou_empate', 'gols_de_um_time'),
                  reverse=True)


def insere_pontuacoes(usuario):
    for jogo in todos_jogos:
        id_jogo = jogo["_id"]
        id_usuario = str(usuario)
        tbl_pontuacao.insert_one({'usuario': id_usuario,
                                  'jogo': id_jogo,
                                  'pontos': 0,
                                  'placar_exato': 0,
                                  'vencedor_ou_empate': 0,
                                  'gols_de_um_time': 0})


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


def usuario_ja_existe(nome_usuario, id_bolao):
    return tbl_usuario.find_one({'nome': nome_usuario, 'bolao': id_bolao}) is not None


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
            "date_time": jogo["data"],
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


def monta_dto_boloes():
    dto_boloes = []
    for bolao in tbl_bolao.find():
        dto_boloes.append({'nome': bolao['nome']})
    return dto_boloes


def monta_dto_grupos():
    if not grupos:
        # for jogo in tbl_jogo.find({'grupo': 'Grupo A', 'rodada': 1}):  # para testar com menos jogos
        for jogo in tbl_jogo.find().sort(
                [("grupo", pymongo.ASCENDING), ("rodada", pymongo.ASCENDING), ("data", pymongo.ASCENDING)]):
            nome_grupo = jogo["grupo"]
            if nome_grupo not in grupos.keys():
                grupos[nome_grupo] = {"nome": nome_grupo,
                                      "rodadas": []}

            rodadas = grupos[nome_grupo]["rodadas"]
            inclui_jogo_na_lista_rodadas(rodadas, jogo)
    return [grupos[x] for x in sorted(grupos)]


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=80)
