FROM python:3

MAINTAINER Rodrigo & Colodas "bolaodagalera@gmail.com"

RUN mkdir /app

WORKDIR /app

# TODO: Use git to download code from master branch
COPY . .

RUN pip install -r requirements.txt

# TODO: Rodar o crawler ja na inicializacao

ENTRYPOINT [ "python" ]

CMD [ "hello.py" ]

# 
# cd <bolao>/Project
# Verify if docker is installed with: 
# docker ps
#
#
# build with:
# docker build -t bolao_flask_image .
#
# run with:
# docker run -d -p 80:80 bolao_flask_image
