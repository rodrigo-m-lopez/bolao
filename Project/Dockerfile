FROM python:3

MAINTAINER Rodrigo & Colodas "bolaodagalera@gmail.com"

RUN apt-get update && apt-get install -qq -y cron && apt-get install -y -qq vim

RUN mkdir /bolao
RUN mkdir /bolao/Project

WORKDIR bolao/Project

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Give execution rights on the cron job
RUN chmod 0644 crawler_cron

# deletar depois
RUN touch /var/log/cron.log

RUN chmod 755 ./start.sh

CMD ["./start.sh"]
