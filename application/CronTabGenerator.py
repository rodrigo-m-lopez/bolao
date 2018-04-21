from pymongo import MongoClient
import collections

client = MongoClient()
db = client.dev
tbl_jogo = db.jogo

#vamos considerar que os jogos vão ter 2 horas de duração, 90 min para os dois tempos,
#  15 min de intervalo mais uns 15 min de tolerância
duracao_horas = 2

horarios = {}

FORMATO_COMANDO = '* {}-{} {} 6 * python /bolao/application/GloboEsporteCrawler.py'

for jogo in tbl_jogo.find():
    datetime_jogo = jogo['data']

    dia = datetime_jogo.day
    hora = datetime_jogo.hour

    if hora not in horarios:
        horarios[hora] = []

    if dia not in horarios[hora]:
        horarios[hora].append(dia)

horarios = collections.OrderedDict(sorted(horarios.items()))

for hora in horarios:
    horarios[hora] = sorted(horarios[hora])
    # TODO: rodrigo: imprimir para arquivo crawler_cron/crawler
    print(FORMATO_COMANDO.format(hora, hora+2, ','.join([str(hora) for hora in horarios[hora]])))

