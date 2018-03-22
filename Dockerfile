FROM python:3

MAINTAINER Rodrigo & Colodas "bolaodagalera@gmail.com"

RUN apt-get update && apt-get install -qq -y cron && apt-get install -y -qq vim
RUN service cron start

RUN mkdir /bolao
RUN mkdir /bolao/Project

WORKDIR bolao/Project

COPY ./Project .

# Add crontab file in the cron directory
ADD ./cron_crawler/crontab /etc/cron.d/cron_crawler

# Give execution rights on the cron job
RUN chmod 0644 /etc/cron.d/cron_crawler

# Create the log file to be able to run tail
RUN touch /var/log/cron.log

RUN pip install -r requirements.txt

CMD cron && python hello.py

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
