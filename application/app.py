# coding: utf-8

import sys
import os
import logging

sys.path.append(os.path.abspath('../../bolao'))

import bisect
import pymongo
from datetime import datetime
from flask import Flask, flash, jsonify, abort
from flask import request
from flask import render_template, redirect, url_for, session
from operator import itemgetter
from bson import ObjectId
from urllib.parse import urlparse, urljoin
from markupsafe import escape

from application.db_config import get_db_client
from application.db_indexes import create_indexes
from application.constants import (
    CAMPOS_PONTUACAO_BANCO,
    CAMPOS_PONTUACAO_DTO,
    CAMPOS_PONTUACAO_ANTERIOR,
    COMPETICOES_DISPONIVEIS,
)

from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from flask_wtf.csrf import CSRFProtect
from application.oauth import OAuthSignIn

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

client = get_db_client()

db = client[os.environ.get('MONGO_DB_NAME', 'dev')]
create_indexes(db)

tbl_jogo = db.jogo
tbl_selecao = db.selecao
tbl_usuario = db.usuario
tbl_bolao = db.bolao
tbl_aposta = db.aposta
tbl_palpite = db.palpite
tbl_pontuacao = db.pontuacao
tbl_historico = db.historico

DEV_MOCK_AUTH = os.environ.get('DEV_MOCK_AUTH', '').lower() in ('1', 'true', 'yes')

if DEV_MOCK_AUTH:
    _required_vars = ('FLASK_SECRET_KEY',)
    logger.warning('DEV_MOCK_AUTH ativado — autenticação Google desabilitada. NÃO use em produção!')
else:
    _required_vars = ('GOOGLE_OAUTH_CREDENTIAL_ID', 'GOOGLE_OAUTH_CREDENTIAL_SECRET', 'FLASK_SECRET_KEY')

_missing = [v for v in _required_vars if v not in os.environ]
if _missing:
    raise Exception(
        'Variáveis de ambiente obrigatórias ausentes: {}'.format(', '.join(_missing))
    )

def _init_dev_db(db):
    """Seed the in-memory DB at startup (DEV_MOCK_AUTH mode).

    - SEED_FROM_API=true + FOOTBALL_DATA_API_KEY set → calls the real API
      seed in-process so data persists in the same mongomock instance.
    - Otherwise → uses the local mock seed with synthetic test scenarios.
    """
    if os.environ.get('SEED_FROM_API') == 'true' and os.environ.get('FOOTBALL_DATA_API_KEY'):
        from application.crawler_2026 import seed_database
        from application.crawler_brasileirao import seed_brasileirao
        seed_database(db)
        seed_brasileirao(db)
    else:
        from application.dev_seed import populate_dev_db
        populate_dev_db(db)


if DEV_MOCK_AUTH:
    _init_dev_db(db)

app = Flask(__name__)
app.secret_key = os.environ['FLASK_SECRET_KEY']
app.config.from_object(__name__)
SECRET_KEY = app.secret_key
csrf = CSRFProtect(app)

app.config['OAUTH_CREDENTIALS'] = {
    'google': {
        'id': os.environ.get('GOOGLE_OAUTH_CREDENTIAL_ID', 'mock'),
        'secret': os.environ.get('GOOGLE_OAUTH_CREDENTIAL_SECRET', 'mock')
    }
}
app.config['DEV_MOCK_AUTH'] = DEV_MOCK_AUTH

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Você precisa estar logado para acessar esta página!'
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return Usuario(user_id)


@app.route('/')
def inicio():
    return intro()


@app.route('/novo_bolao', methods=['GET', 'POST'])
@login_required
def novo_bolao():
    if request.method == 'GET':
        return render_template('novo_bolao.html', competicoes=COMPETICOES_DISPONIVEIS)
    else:
        if not valida_informacoes_bolao(request.form):
            return render_template('novo_bolao.html', competicoes=COMPETICOES_DISPONIVEIS)
        cria_bolao(request.form)
        return lista_bolao()


@app.route('/intro')
def intro():
    return render_template('intro.html')


@app.route('/lista_bolao')
def lista_bolao():
    boloes = monta_dto_boloes()
    return render_template('lista_bolao.html', lista_boloes=boloes)


@app.route('/<bolao>/nova_aposta', methods=['GET', 'POST'])
@login_required
def nova_aposta(bolao):
    bolao_doc = tbl_bolao.find_one({'nome': bolao}) or {}
    competicao = bolao_doc.get('competicao', '')
    grupos, todos_jogos = monta_dto_grupos(competicao)
    if request.method == 'GET':
        return render_template('aposta.html', grupos=grupos, bolao=bolao)
    else:
        id_bolao = get_bolao_id(bolao)
        nome_aposta = request.form['inputNome']
        if not aposta_ja_existe(nome_aposta, id_bolao):
            id_aposta = insere_aposta(nome_aposta, id_bolao)
            insere_palpites(id_aposta, request.form, todos_jogos)
            insere_pontuacoes(id_aposta, todos_jogos)
            return redirect(url_for('editar_palpites', bolao=bolao, nome_aposta=nome_aposta))
        else:
            flash('Já existe uma aposta para este bolão com o nome [{}]. Escolha outro.'.format(nome_aposta))
            return render_template('aposta.html', bolao=bolao, grupos=grupos)


@app.route('/<bolao>/descricao_bolao')
def descricao(bolao):
    bolao_selecionado = tbl_bolao.find_one({'nome': bolao})
    responsavel = tbl_usuario.find_one({'_id': bolao_selecionado['usuario']})
    return render_template('descricao_bolao.html', bolao=bolao, bolao_selecionado=bolao_selecionado,
                           responsavel=responsavel)


@app.route('/<bolao>/ranking')
def ranking(bolao):
    lista_apostas = monta_dto_apostas(bolao)
    bolao_doc = tbl_bolao.find_one({'nome': bolao}) or {}
    competicao = bolao_doc.get('competicao', '')
    return render_template('ranking.html', bolao=bolao, lista_apostas=lista_apostas, competicao=competicao)


@app.route('/<bolao>/admin')
@login_required
def admin(bolao):
    if usuario_criou_o_bolao(bolao):
        lista_apostas = monta_dto_apostas(bolao)
        return render_template('admin.html', bolao=bolao, lista_apostas=lista_apostas)
    else:
        flash('Requisição inválida, apenas usuário que criou o bolão pode acessar sua área de Admin')
        return lista_bolao()


@app.route('/valida_nome_bolao', methods=['POST'])
def valida_nome_bolao():
    nome_bolao = request.form['nome_bolao']
    return valida_nome_bolao_ja_existe(nome_bolao)


@app.route('/<bolao>/valida_nome_aposta', methods=['POST'])
def valida_nome_aposta(bolao):
    nome_aposta = request.form['nome_aposta']
    id_bolao = get_bolao_id(bolao)

    if aposta_ja_existe(nome_aposta, id_bolao):
        return 'Aposta com nome <strong>{}</strong> já existe para este bolão, escolha outro.'.format(escape(nome_aposta))
    else:
        return ''


@app.route('/<bolao>/toggle_pago', methods=['POST'])
@login_required
def toggle_pago(bolao):
    if usuario_criou_o_bolao(bolao):
        id_bolao = get_bolao_id(bolao)
        nome_aposta = request.form['nome_aposta']
        aposta = tbl_aposta.find_one({'nome': nome_aposta, 'bolao': id_bolao})
        novo_pago = not aposta['pago']

        tbl_aposta.update_one({'nome': nome_aposta,
                               'bolao': id_bolao},
                              {"$set": {"pago": novo_pago}})

        lista_apostas = monta_dto_apostas(bolao)
        return render_template('admin.html', bolao=bolao, lista_apostas=lista_apostas)
    else:
        flash('Requisição inválida, apenas usuário que criou o bolão pode acessar sua área de Admin')
        return lista_bolao()


@app.route('/pago', methods=['GET', 'POST'])
def grade():
    if request.method == 'POST':
        return 'Form posted.'


@app.route('/<bolao>/remover_aposta', methods=['POST'])
@login_required
def remover_aposta(bolao):
    if usuario_criou_o_bolao(bolao):
        id_bolao = get_bolao_id(bolao)
        nome_aposta = request.form['nome_aposta']
        id_aposta = tbl_aposta.find_one({"nome": nome_aposta, 'bolao': id_bolao})['_id']
        tbl_aposta.delete_one({'_id': id_aposta})
        lista_apostas = monta_dto_apostas(bolao)
        return render_template('admin.html', bolao=bolao, lista_apostas=lista_apostas)
    else:
        flash('Requisição inválida, apenas usuário que criou o bolão pode acessar sua área de Admin')
        return lista_bolao()


@app.route('/<bolao>/remover_bolao', methods=['POST'])
@login_required
def remover_bolao(bolao):
    if usuario_criou_o_bolao(bolao):
        id_bolao = get_bolao_id(bolao)
        tbl_bolao.delete_one({'_id': id_bolao})
        return redirect(url_for('lista_bolao'))
    else:
        flash('Requisição inválida, apenas usuário que criou o bolão pode acessar sua área de Admin')
        return lista_bolao()


@app.route('/<bolao>/palpite/<nome_aposta>')
def palpite(bolao, nome_aposta):
    id_bolao = get_bolao_id(bolao)
    aposta = tbl_aposta.find_one({'nome': nome_aposta, 'bolao': id_bolao})
    bolao_doc = tbl_bolao.find_one({'nome': bolao}) or {}
    _, todos_jogos = monta_dto_grupos(bolao_doc.get('competicao', ''))
    palpites = monta_palpites(aposta, todos_jogos)
    pontuacoes = monta_pontuacoes(aposta, todos_jogos)
    lista_jogos_ordem_tela = []
    placares = monta_placares(lista_jogos_ordem_tela, todos_jogos)

    return render_template('palpites.html', bolao=bolao, jogos=lista_jogos_ordem_tela, palpites=palpites,
                           pontuacoes=pontuacoes, placares=placares, nome_aposta=nome_aposta)


@app.route('/<bolao>/jogo/<nome_jogo>')
def jogo(bolao, nome_jogo):
    bolao_doc = tbl_bolao.find_one({'nome': bolao}) or {}
    _, todos_jogos = monta_dto_grupos(bolao_doc.get('competicao', ''))
    jogo_dto = next((x for x in todos_jogos if x['nome'] == nome_jogo), None)
    if jogo_dto is None:
        flash('Jogo não encontrado.')
        return redirect(url_for('lista_bolao'))
    placar = '{} x {}'.format(jogo_dto["gols_mandante"], jogo_dto["gols_visitante"])
    apostas = monta_dto_apostas(bolao)
    palpites = {}
    pontuacoes = {}
    for aposta in apostas:
        palpite_jogo = tbl_palpite.find_one({'aposta': aposta['id'], 'jogo': jogo_dto['_id']})
        if palpite_jogo:
            palpites[aposta['nome']] = '{} x {}'.format(palpite_jogo['gols_mandante'], palpite_jogo['gols_visitante'])
        else:
            palpites[aposta['nome']] = '- x -'
        pontuacao_jogo = tbl_pontuacao.find_one({'aposta': aposta['id'], 'jogo': jogo_dto['_id']})
        pontuacoes[aposta['nome']] = pontuacao_jogo['pontos']
    apostas.sort(key=lambda a: a['nome'])
    apostas.sort(key=lambda a: pontuacoes[a['nome']], reverse=True)
    return render_template('jogos.html', bolao=bolao, jogo=jogo_dto, palpites=palpites,
                           apostas=apostas, placar=placar, pontuacoes=pontuacoes)


@app.route('/<bolao>/editar_palpites/<nome_aposta>')
@login_required
def editar_palpites(bolao, nome_aposta):
    id_bolao = get_bolao_id(bolao)
    aposta = get_aposta_by_nome(nome_aposta, id_bolao)
    bolao_doc = tbl_bolao.find_one({'nome': bolao}) or {}
    competicao = bolao_doc.get('competicao', '')
    grupos, todos_jogos = monta_dto_grupos(competicao)
    palpites_map = {str(p['jogo']): p for p in tbl_palpite.find({'aposta': aposta['_id']})}
    return render_template('editar_palpites.html', bolao=bolao, nome_aposta=nome_aposta,
                           grupos=grupos, palpites_map=palpites_map)


@app.route('/<bolao>/salvar_palpites/<nome_aposta>', methods=['POST'])
@login_required
def salvar_palpites(bolao, nome_aposta):
    """Salva palpites de múltiplos jogos em uma única requisição.

    Recebe JSON: [{"id_jogo": "...", "gols_mandante": N, "gols_visitante": N}, ...]
    Valida jogo a jogo no servidor, bloqueando os que já iniciaram.
    Retorna: {"salvos": [...ids], "bloqueados": [...{id_jogo, nome}], "erros": [...{id_jogo, erro}]}
    """
    id_bolao = get_bolao_id(bolao)
    aposta = get_aposta_by_nome(nome_aposta, id_bolao)
    payload = request.get_json(silent=True)
    if not isinstance(payload, list):
        return jsonify({'erro': 'Formato inválido.'}), 400

    salvos = []
    bloqueados = []
    erros = []

    for item in payload:
        id_jogo_str = str(item.get('id_jogo', ''))
        gols_m_str  = str(item.get('gols_mandante', '')).strip()
        gols_v_str  = str(item.get('gols_visitante', '')).strip()

        try:
            id_jogo = ObjectId(id_jogo_str)
        except Exception:
            erros.append({'id_jogo': id_jogo_str, 'erro': 'ID de jogo inválido.'})
            continue

        jogo_doc = tbl_jogo.find_one({'_id': id_jogo})
        if jogo_doc is None:
            erros.append({'id_jogo': id_jogo_str, 'erro': 'Jogo não encontrado.'})
            continue

        if jogo_ja_iniciou(jogo_doc['data']) or jogo_tem_time_tbd(jogo_doc):
            bloqueados.append({'id_jogo': id_jogo_str, 'nome': jogo_doc.get('nome', '')})
            continue

        try:
            gm, gv = int(gols_m_str), int(gols_v_str)
            if gm < 0 or gv < 0:
                raise ValueError('negative')
        except ValueError:
            erros.append({'id_jogo': id_jogo_str, 'erro': 'Placar inválido.'})
            continue

        tbl_palpite.update_one(
            {'aposta': aposta['_id'], 'jogo': id_jogo},
            {'$set': {'gols_mandante': gm, 'gols_visitante': gv}},
            upsert=True
        )
        salvos.append(id_jogo_str)

    return jsonify({'salvos': salvos, 'bloqueados': bloqueados, 'erros': erros})


@app.route('/<bolao>/salvar_palpite/<nome_aposta>', methods=['POST'])
@login_required
def salvar_palpite(bolao, nome_aposta):
    id_bolao = get_bolao_id(bolao)
    aposta = get_aposta_by_nome(nome_aposta, id_bolao)
    id_jogo_str = request.form.get('id_jogo', '')
    gols_m_str = request.form.get('gols_mandante', '').strip()
    gols_v_str = request.form.get('gols_visitante', '').strip()
    try:
        id_jogo = ObjectId(id_jogo_str)
    except Exception:
        return jsonify({'ok': False, 'erro': 'Jogo inválido.'}), 400
    jogo_doc = tbl_jogo.find_one({'_id': id_jogo})
    if jogo_doc is None:
        return jsonify({'ok': False, 'erro': 'Jogo não encontrado.'}), 404
    if jogo_ja_iniciou(jogo_doc['data']) or jogo_tem_time_tbd(jogo_doc):
        return jsonify({'ok': False, 'erro': 'Este jogo já começou. Palpite bloqueado.'}), 403
    try:
        gm, gv = int(gols_m_str), int(gols_v_str)
        if gm < 0 or gv < 0:
            raise ValueError('negative')
    except ValueError:
        return jsonify({'ok': False, 'erro': 'Placar inválido.'}), 400
    tbl_palpite.update_one(
        {'aposta': aposta['_id'], 'jogo': id_jogo},
        {'$set': {'gols_mandante': gm, 'gols_visitante': gv}},
        upsert=True
    )
    return jsonify({'ok': True})


@app.route('/login', methods=['GET', 'POST'])
def login():
    session['next'] = safe_next('lista_bolao')
    return render_template('login.html')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(safe_next('intro'))


@app.route('/dev_login')
def dev_login():
    """Login automático para desenvolvimento local. Só funciona com DEV_MOCK_AUTH=true."""
    from flask import abort
    if not app.config.get('DEV_MOCK_AUTH'):
        abort(404)
    email = 'dev@local.test'
    nome = 'Dev User'
    usuario = tbl_usuario.find_one({'email': email})
    if usuario is None:
        tbl_usuario.insert_one({
            'nome': nome, 'email': email,
            'primeiro_nome': 'Dev', 'sobrenome': 'User',
            'foto': '', 'sexo': 'm'
        })
    login_user(Usuario(email), remember=True)
    logger.info('Dev mock login: %s', email)
    next_uri = session.get('next') or url_for('lista_bolao')
    if not is_safe_url(next_uri):
        next_uri = url_for('lista_bolao')
    return redirect(next_uri)


@app.route('/callback/<provider>')
def oauth_callback(provider):
    next_uri = session.get('next')
    if not next_uri or not is_safe_url(next_uri):
        next_uri = url_for('lista_bolao')
    if not current_user.is_anonymous:
        return redirect(next_uri)
    oauth = OAuthSignIn.get_provider(provider)
    result = oauth.callback()
    nome = result[0]
    if nome is None:
        flash('Falha na autenticação.')
        return redirect(url_for('login'))
    email, primeiro_nome, sobrenome, foto, sexo = result[1], result[2], result[3], result[4], result[5]
    usuario = Usuario(email)
    if usuario.is_anonymous():
        tbl_usuario.insert_one({'nome': nome,
                                'email': email,
                                'primeiro_nome': primeiro_nome,
                                'sobrenome': sobrenome,
                                'foto': foto,
                                'sexo': None if sexo is None else sexo[0]})
        usuario = Usuario(email)
    login_user(usuario, remember=True)
    logger.info('User %s logged in via %s', email, provider)
    return redirect(next_uri)


@app.route('/authorize/<provider>')
def oauth_authorize(provider):
    logger.debug('OAuth authorize session: %s', dict(session))
    next_uri = session.get('next')
    if not next_uri or not is_safe_url(next_uri):
        next_uri = url_for('lista_bolao')
    if not current_user.is_anonymous:
        return redirect(next_uri)
    oauth = OAuthSignIn.get_provider(provider)
    return oauth.authorize()


@app.route('/<bolao>/chart/<id_aposta>')
def chart(bolao, id_aposta):
    id_bolao = get_bolao_id(bolao)
    aposta = tbl_aposta.find_one({'_id': ObjectId(id_aposta)})
    nome_aposta = aposta['nome']
    logger.debug('Chart view for aposta: %s', nome_aposta)
    qtd_participantes = tbl_aposta.count_documents({'bolao': id_bolao})
    horarios = obtem_horarios_rodadas()
    horarios_com_pontuacoes = obtem_datas_rodadas_com_pontuacao()
    labels = [obtem_label(horario) for horario in horarios]
    values = []
    horario_ultima_rodada = obtem_data_rodada_anterior()
    for horario in horarios_com_pontuacoes:
        posicao = calcula_posicao(id_bolao, id_aposta, horario, horario_ultima_rodada)
        if posicao is not None:
            values.append(posicao)

    return render_template('chart.html', values=values, labels=labels, qtd_participantes=qtd_participantes,
                           nome_aposta=nome_aposta, bolao=bolao)


# ── Helpers ──────────────────────────────────────────────────────────────────

def jogo_ja_iniciou(jogo_data_utc):
    """Returns True if the match has already started, using server UTC time."""
    return datetime.utcnow() >= jogo_data_utc


def jogo_tem_time_tbd(jogo_doc):
    """Returns True if either team in the match is TBD (sigla '???')."""
    for field in ('mandante', 'visitante'):
        sel = tbl_selecao.find_one({'_id': jogo_doc.get(field)})
        if sel and sel.get('sigla') == '???':
            return True
    return False


def get_bolao_id(nome_bolao):
    """Return the ObjectId of a bolão by name, or abort 404."""
    from flask import abort
    bolao = tbl_bolao.find_one({'nome': nome_bolao})
    if bolao is None:
        abort(404, description="Bolão '{}' não encontrado.".format(nome_bolao))
    return bolao['_id']


def get_aposta_by_nome(nome_aposta, id_bolao):
    """Return the aposta document by name and bolao id, or abort 404."""
    from flask import abort
    aposta = tbl_aposta.find_one({'nome': nome_aposta, 'bolao': id_bolao})
    if aposta is None:
        abort(404, description="Aposta '{}' não encontrada.".format(nome_aposta))
    return aposta


def is_safe_url(target):
    """Return True only if target points to the same host (prevents open redirect)."""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def safe_next(default_endpoint):
    """Return a validated next URL from the request args, or the default endpoint URL."""
    next_uri = request.args.get('next')
    if next_uri and is_safe_url(next_uri):
        return next_uri
    return url_for(default_endpoint)


def flash_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(u"Erro no campo %s - %s" % (getattr(form, field).label.text, error))


def usuario_criou_o_bolao(nome_bolao):
    return tbl_bolao.find_one({'usuario': current_user.mongo_id, 'nome': nome_bolao}) is not None


def monta_placares(lista_jogos_ordem_tela, todos_jogos):
    """Build placares dict from todos_jogos DTO — no extra DB queries needed."""
    placares = {}
    lista_sem_resultados = []
    lista_com_resultados = []
    for jogo in todos_jogos:
        # monta_dto_jogo already set gols_mandante to '-' when None
        sem_resultado = jogo['gols_mandante'] == '-'
        (lista_sem_resultados if sem_resultado else lista_com_resultados).append(jogo)
        placares[jogo['nome']] = '{} x {}'.format(jogo['gols_mandante'], jogo['gols_visitante'])

    lista_com_resultados.sort(key=itemgetter('date_time'), reverse=True)
    lista_sem_resultados.sort(key=itemgetter('date_time'), reverse=False)
    lista_com_resultados.extend(lista_sem_resultados)
    lista_jogos_ordem_tela.extend(lista_com_resultados)
    return placares


def monta_pontuacoes(aposta, todos_jogos):
    """Return pontuacao por jogo using 1 query instead of 1-per-jogo."""
    jogos_map = {jogo['_id']: jogo['nome'] for jogo in todos_jogos}
    pontuacoes = {jogo['nome']: 0 for jogo in todos_jogos}
    for pontuacao in tbl_pontuacao.find({'aposta': aposta['_id']}):
        nome = jogos_map.get(pontuacao['jogo'])
        if nome:
            pontuacoes[nome] = pontuacao['pontos']
    return pontuacoes


def monta_palpites(aposta, todos_jogos):
    """Return palpites por jogo using 1 query instead of 1-per-jogo."""
    jogos_map = {jogo['_id']: jogo['nome'] for jogo in todos_jogos}
    palpites = {}
    for palpite in tbl_palpite.find({'aposta': aposta['_id']}):
        nome = jogos_map.get(palpite['jogo'])
        if nome:
            palpites[nome] = '{} x {}'.format(palpite['gols_mandante'], palpite['gols_visitante'])
    return palpites


def cria_bolao(form):
    tbl_bolao.insert_one({'nome': form['inputNome'],
                          'usuario': current_user.mongo_id,
                          'valor': int(form['inputValor']),
                          'premiacao': form['inputPremiacao'],
                          'descricao': form['inputDescricao'],
                          'competicao': form['inputCompeticao']})


def valida_nome_bolao_ja_existe(nome_bolao):
    if tbl_bolao.find_one({'nome': nome_bolao}) is not None:
        return 'Nome [{}] já foi escolhido para um bolão, escolha outro.'.format(escape(nome_bolao))
    else:
        return ''


def valida_campo_preenchido(valor_campo, nome_campo):
    if valor_campo == '':
        return 'Campo [{}] é de preenchimento obrigatório.'.format(nome_campo)
    else:
        return ''


def valida_campo_numerico(valor_campo):
    try:
        inteiro = int(valor_campo.strip())
        if inteiro < 0:
            return 'O campo Valor não pode ser negativo'
        return ''
    except ValueError:
        return 'O campo Valor precisa ser um número'


def valida_senhas_iguais(senha1, senha2):
    if senha1 != senha2:
        return 'Senhas não conferem.'
    return ''


def valida_informacoes_bolao(form):
    algum_erro = False
    competicao = form.get('inputCompeticao', '')
    if competicao not in COMPETICOES_DISPONIVEIS:
        flash('Selecione uma competição válida.')
        algum_erro = True
    validacoes = [valida_nome_bolao_ja_existe(form['inputNome']),
                  valida_campo_preenchido(form['inputValor'], 'Valor'),
                  valida_campo_numerico(form['inputValor']),
                  valida_campo_preenchido(form['inputPremiacao'], 'Premiação')]
    for erro in validacoes:
        if erro > '':
            algum_erro = True
            flash(erro)
    return not algum_erro


def totaliza_pontuacao(id_aposta, campos, data_pontuacao=None):
    """Sum pontuacao fields for a single aposta. Use totaliza_pontuacao_batch for bulk."""
    totais = {campo: 0 for campo in campos}
    for pontuacao in tbl_pontuacao.find({'aposta': id_aposta}):
        id_jogo = pontuacao['jogo']
        jogo = tbl_jogo.find_one({'_id': id_jogo})
        if data_pontuacao is None or jogo['data'] <= data_pontuacao:
            for campo in campos:
                totais[campo] = totais[campo] + pontuacao[campo]
    return totais


def totaliza_pontuacao_batch(pontuacoes_list, jogos_data_map, campos, data_pontuacao=None):
    """Sum pontuacao fields from pre-fetched documents — no DB queries."""
    totais = {campo: 0 for campo in campos}
    for pontuacao in pontuacoes_list:
        jogo_data = jogos_data_map.get(pontuacao['jogo'])
        if data_pontuacao is None or (jogo_data is not None and jogo_data <= data_pontuacao):
            for campo in campos:
                totais[campo] += pontuacao[campo]
    return totais


def incluiRanking(lista, campos, campo_ranking):
    lista = sorted(lista, key=itemgetter(*campos), reverse=True)
    posicao = 1
    posicao_anterior = posicao
    anterior = [-1, -1, -1, -1]
    for item in lista:
        atual = [item[campo] for campo in campos]
        if anterior == atual:
            item[campo_ranking] = posicao_anterior
        else:
            item[campo_ranking] = posicao

        anterior = atual
        posicao_anterior = item[campo_ranking]
        posicao += 1

    return lista


def obtem_label(data):
    """Return label string for a round date using 2 queries (jogos + selecoes)."""
    jogos_data = list(tbl_jogo.find({'data': data}))
    if not jogos_data:
        return ''
    selecao_ids = [j['mandante'] for j in jogos_data] + [j['visitante'] for j in jogos_data]
    selecoes = {s['_id']: s['sigla'] for s in tbl_selecao.find({'_id': {'$in': selecao_ids}})}
    return ','.join(
        '{} x {}'.format(selecoes.get(j['mandante'], '?'), selecoes.get(j['visitante'], '?'))
        for j in jogos_data
    )


def obtem_horarios_rodadas():
    horarios = []
    for jogo in tbl_jogo.find():
        horario = jogo['data']
        if horario not in horarios:
            bisect.insort(horarios, horario)
    return horarios


def obtem_datas_rodadas_com_pontuacao():
    horarios = []
    for jogo in tbl_jogo.find({'gols_mandante': {"$ne": None}}):
        horario = jogo['data']
        if horario not in horarios:
            bisect.insort(horarios, horario)
    return horarios


def obtem_data_rodada_anterior():
    horarios = obtem_datas_rodadas_com_pontuacao()
    return None if len(horarios) < 2 else horarios[-2]


def calcula_posicao(id_bolao, id_aposta, horario, horario_ultima_rodada):
    if horario_ultima_rodada is not None and horario <= horario_ultima_rodada:
        historico = tbl_historico.find_one({'horario': horario, 'aposta': id_aposta})
        if historico is not None:
            return historico['posicao']

    posicao = None
    lista_retorno = []
    campos = CAMPOS_PONTUACAO_BANCO
    for aposta in tbl_aposta.find({'bolao': id_bolao}):
        nova_aposta = {"id": str(aposta["_id"])}
        pontuacao_totalizada = totaliza_pontuacao(aposta['_id'], campos, horario)
        for campo in campos:
            nova_aposta[campo] = pontuacao_totalizada[campo]
        lista_retorno.append(nova_aposta)

    lista_ordenada = incluiRanking(lista_retorno, campos, 'posicao')

    for item in lista_ordenada:
        if item['id'] == id_aposta:
            posicao = item['posicao']
            break

    if horario_ultima_rodada is not None and horario <= horario_ultima_rodada:
        if posicao is not None:
            historico = {'horario': horario,
                         'aposta': id_aposta,
                         'posicao': posicao}
            tbl_historico.insert_one(historico)

    return posicao


def monta_dto_apostas(bolao):
    """Build apostas DTO with ranking using O(4) queries instead of O(N*M)."""
    id_bolao = get_bolao_id(bolao)
    data_rodada_anterior = obtem_data_rodada_anterior()
    campos_banco = CAMPOS_PONTUACAO_BANCO
    campos_dto = CAMPOS_PONTUACAO_DTO
    campos_rodada_anterior = CAMPOS_PONTUACAO_ANTERIOR

    apostas = list(tbl_aposta.find({'bolao': id_bolao}))
    if not apostas:
        return []

    aposta_ids = [a['_id'] for a in apostas]

    # 1 query: all usuarios
    usuarios_map = {u['_id']: u for u in tbl_usuario.find(
        {'_id': {'$in': [a['usuario'] for a in apostas]}}
    )}

    # 1 query: all pontuacoes for all apostas
    pontuacoes_all = list(tbl_pontuacao.find({'aposta': {'$in': aposta_ids}}))
    pontuacoes_by_aposta = {}
    for p in pontuacoes_all:
        pontuacoes_by_aposta.setdefault(p['aposta'], []).append(p)

    # 1 query: all jogo dates (needed for date-filtered totals)
    jogo_ids = list({p['jogo'] for p in pontuacoes_all})
    jogos_data_map = {j['_id']: j['data'] for j in tbl_jogo.find(
        {'_id': {'$in': jogo_ids}}, {'data': 1}
    )}

    lista_retorno = []
    for aposta in apostas:
        usuario = usuarios_map.get(aposta['usuario'], {})
        nova_aposta = {"id": aposta["_id"],
                       "nome": aposta["nome"],
                       "pago": aposta["pago"],
                       "foto": usuario.get('foto', '')}
        nova_aposta.update({'usuario_nome': usuario.get('nome', ''),
                            'usuario_email': usuario.get('email', '')})

        ponts = pontuacoes_by_aposta.get(aposta['_id'], [])

        pontuacao_total = totaliza_pontuacao_batch(ponts, jogos_data_map, campos_banco)
        for i in range(len(campos_banco)):
            nova_aposta[campos_dto[i]] = pontuacao_total[campos_banco[i]]

        pontuacao_ant = totaliza_pontuacao_batch(ponts, jogos_data_map, campos_banco, data_rodada_anterior)
        for i in range(len(campos_banco)):
            nova_aposta[campos_rodada_anterior[i]] = pontuacao_ant[campos_banco[i]]

        lista_retorno.append(nova_aposta)

    incluiRanking(lista_retorno, campos_rodada_anterior, 'posicao_anterior')
    lista_ordenada = incluiRanking(lista_retorno, campos_dto, 'posicao')

    for item in lista_ordenada:
        item['variacao'] = item['posicao_anterior'] - item['posicao']

    return lista_ordenada


def insere_aposta(nome, id_bolao):
    return tbl_aposta.insert_one({'nome': nome,
                                  'usuario': current_user.mongo_id,
                                  'bolao': id_bolao,
                                  'pago': False,
                                  }).inserted_id


def insere_pontuacoes(id_aposta, todos_jogos):
    for jogo in todos_jogos:
        id_jogo = jogo["_id"]
        tbl_pontuacao.insert_one({'aposta': id_aposta,
                                  'jogo': id_jogo,
                                  'pontos': 0,
                                  'placar_exato': 0,
                                  'vencedor_ou_empate': 0,
                                  'gols_de_um_time': 0})


def insere_palpites(id_aposta, form, todos_jogos):
    for jogo in todos_jogos:
        if jogo_ja_iniciou(jogo["date_time"]):
            continue
        id_jogo = jogo["_id"]
        gols_m_str = form.get('m{}'.format(str(id_jogo)), '').strip()
        gols_v_str = form.get('v{}'.format(str(id_jogo)), '').strip()
        if gols_m_str == '' or gols_v_str == '':
            continue
        try:
            gm, gv = int(gols_m_str), int(gols_v_str)
        except ValueError:
            continue
        tbl_palpite.insert_one({'aposta': id_aposta, 'jogo': id_jogo,
                                'gols_mandante': gm, 'gols_visitante': gv})


def aposta_ja_existe(nome_aposta, id_bolao):
    return tbl_aposta.find_one({'nome': nome_aposta, 'bolao': id_bolao}) is not None


def monta_dto_jogo(jogo):
    mandante = tbl_selecao.find_one({'_id': jogo["mandante"]})
    visitante = tbl_selecao.find_one({'_id': jogo["visitante"]})
    tbd = (
        (mandante and mandante.get('sigla') == '???') or
        (visitante and visitante.get('sigla') == '???')
    )
    return {"_id": jogo["_id"],
            "nome": jogo["nome"],
            "gols_mandante": '-' if jogo["gols_mandante"] is None else jogo["gols_mandante"],
            "gols_visitante": '-' if jogo["gols_visitante"] is None else jogo["gols_visitante"],
            "escudo_mandante": mandante["escudo"] if mandante else '',
            "escudo_visitante": visitante["escudo"] if visitante else '',
            "nome_mandante": mandante["nome"] if mandante else 'A Definir',
            "nome_visitante": visitante["nome"] if visitante else 'A Definir',
            "id_input_mandante": 'm{0}'.format(str(jogo["_id"])),
            "id_input_visitante": 'v{0}'.format(str(jogo["_id"])),
            "data": jogo["data"].strftime('%d/%m %H:%M'),
            "data_utc_iso": jogo["data"].strftime('%Y-%m-%dT%H:%M:%SZ'),
            "date_time": jogo["data"],
            "local": jogo["local"],
            "tbd": tbd,
            "bloqueado": tbd or jogo_ja_iniciou(jogo["data"])}


def inclui_jogo_na_lista_rodadas(lista_rodadas, jogo, todos_jogos):
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
                              "nome": '{}ª Rodada'.format(rodada_do_jogo),
                              "jogos": jogos})
    dto_jogo = monta_dto_jogo(jogo)
    jogos.append(dto_jogo)
    todos_jogos.append(dto_jogo)


def monta_dto_boloes():
    dto_boloes = []
    for bolao in tbl_bolao.find():
        dto_boloes.append({'nome': bolao['nome']})
    return dto_boloes


def monta_dto_grupos(competicao=None):
    """Return (grupos_list, todos_jogos_list) — always fresh from DB, no global state.

    Se `competicao` for informada, filtra apenas os jogos daquela competição.
    """
    filtro = {'competicao': competicao} if competicao else {}
    grupos_dict = {}
    todos_jogos_local = []
    for jogo in tbl_jogo.find(filtro).sort(
            [("grupo", pymongo.ASCENDING), ("rodada", pymongo.ASCENDING), ("data", pymongo.ASCENDING)]):
        nome_grupo = jogo["grupo"]
        if nome_grupo not in grupos_dict:
            grupos_dict[nome_grupo] = {"nome": nome_grupo, "rodadas": []}
        rodadas = grupos_dict[nome_grupo]["rodadas"]
        inclui_jogo_na_lista_rodadas(rodadas, jogo, todos_jogos_local)
    return [grupos_dict[x] for x in sorted(grupos_dict)], todos_jogos_local


class Usuario:
    def __init__(self, email):
        self.usuario_banco = tbl_usuario.find_one({'email': email})
        self.mongo_id = None
        if self.usuario_banco is not None:
            self.email = str(self.usuario_banco['email'])
            self.nome = str(self.usuario_banco['nome'])
            self.foto = str(self.usuario_banco['foto'])
            self.primeiro_nome = str(self.usuario_banco['primeiro_nome'])
            self.sobrenome = str(self.usuario_banco['sobrenome'])
            self.sexo = str(self.usuario_banco['sexo'])
            self.mongo_id = self.usuario_banco['_id']

    def is_authenticated(self):
        return self.usuario_banco is not None

    def is_active(self):
        return self.usuario_banco is not None

    def is_anonymous(self):
        return self.usuario_banco is None

    def get_id(self):
        return self.email

    def eh_criador_do_bolao(self, nome_bolao):
        bolao = tbl_bolao.find_one({'nome': nome_bolao})
        return self.is_authenticated and self.mongo_id == bolao['usuario']


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
