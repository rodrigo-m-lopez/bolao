FROM python:3

MAINTAINER Rodrigo & Colodas "bolaodagalera@gmail.com"

RUN apt-get update && apt-get install -qq -y cron
RUN service cron start

RUN mkdir /bolao
RUN mkdir /bolao/Project

WORKDIR bolao/Project

COPY ./Project .
COPY ./cronjobs /etc/cron.d

RUN pip install -r requirements.txt

#ENTRYPOINT [ "python" ]

#CMD [ "hello.py" ]

CMD python hello.py

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
