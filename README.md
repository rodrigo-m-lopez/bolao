# bolao

Passos pra funcionar:

além dessa pasta project , cria um venv no mesmo nivel do projeto e usa o requirements.txt

Instala o MongoDB e cria a pasta data no mesmo nivel da project com usuario padrão e configura um serviço pra startar com sua máquina

# Pra rodar o crawler 
Por enquanto só popula o banco com os jogos e os times, ainda falta atualizar as pontuações:
```
python GloboEsporteCrawler.py
```

# Pra rodar o site:

cmd.exe(a partir da pasta bolao):

```
venv/Scripts/activate
cd Projects
set FLASK_APP=hello.py
set FLASK_DEBUG=1
flask run
```

