# bolao

Passos pra funcionar:
Vou explicar só uma vez mesmo sabendo q vc é burro, quando aparecer (...) nos comandos troca pelo caminho que vc fez checkout do projeto
# venv
Instalar o venv, executar ele e instalar os requisitos do projeto:
```
cd (...)\bolao
pip install virtualenv
virtualenv venv
venv\Scripts\activate
cd Project
pip install -r requirements.txt
```
Se for instalar mais alguma dependencia do python com pip install, abre o power shell e roda os comandos abaixo:
```
cd (...)\bolao\Project
pip freeze > requirements.txt
git add requirements.txt
git commit -m "atualizando as dependências"
git push
```
# MongoDB
Instala o mongo desse caminho aqui (só sai clicando em next):
https://www.mongodb.com/download-center#production
Cria as pastas do Mongo no projeto:
```
cd (...)\bolao
mkdir data
cd data
mkdir db
mkdir log
```
Cria um arquivo "C:\Program Files\MongoDB\Server\3.6\mongod.cfg" com o conteúdo abaixo, precisa ser administrador:

```
systemLog:
    destination: file
    path: (...)\bolao\data\log\mongod.log
storage:
    dbPath: (...)\bolao\data\db
```
Agora cria um serviço do mongo que vai startar com sua máquina, também precisa ser administrador:
```
sc.exe create MongoDB binPath= "\"C:\Program Files\MongoDB\Server\3.6\bin\mongod.exe\" --service --config=\"C:\Program Files\MongoDB\Server\3.6\mongod.cfg\"" DisplayName= "MongoDB" start= "auto"
```
Inicia o serviço:
```
net start MongoDB
```

# Pra rodar o crawler 
O crawler popula o banco na primeira vez e depois calcula a pontuação se teve alteração pra ultima vez:
```
python GloboEsporteCrawler.py
```

# Pra rodar o site:

```
cd (...)\bolao
venv/Scripts/activate
cd Project
sudo python3 hello.py
```

# Configurando na amazon:

```
sudo yum clean all
sudo yum update
sudo yum install python36 python36-virtualenv python36-pip


sudo yum install -y docker
sudo usermod -a -G docker ec2-user
sudo curl -L https://github.com/docker/compose/releases/download/1.19.0/docker-compose-`uname -s`-`uname -m` | sudo tee /usr/local/bin/docker-compose > /dev/null
sudo chmod +x /usr/local/bin/docker-compose
sudo service docker start
sudo chkconfig docker on
```

eu copiei via ssh da minha máquna local a pasta bolao para ~/bolao, depois disso:

```
cd bolao
python3.6 -m venv venv
. venv/bin/activate
cd Project/
pip install -r requirements.txt
```



