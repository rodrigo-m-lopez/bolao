from pymongo import MongoClient
import collections

client = MongoClient()
db = client.dev
tbl_jogo = db.jogo

#vamos considerar que os jogos vão ter 2 horas de duração, 90 min para os dois tempos,
#  15 min de intervalo mais uns 15 min de tolerância
duracao_horas = 2

horarios = {}

FORMATO_COMANDO = '* {}-{} {} 6 * python GloboEsporteCrawler.py'

for jogo in tbl_jogo.find():
    datetime_jogo = jogo['data']

    dia = datetime_jogo.day
    hora = datetime_jogo.hour

    if dia not in horarios:
        horarios[dia] = []

    if hora not in horarios[dia]:
        horarios[dia].append(hora)

horarios = collections.OrderedDict(sorted(horarios.items()))

for dia in horarios:
    horarios[dia] = sorted(horarios[dia])
    for hora in horarios[dia]:
        print(FORMATO_COMANDO.format(hora, hora+2, dia))

