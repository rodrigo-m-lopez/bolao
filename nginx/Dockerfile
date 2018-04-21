FROM nginx:1.13.8
LABEL maintainer="bolaodagalera2018@gmail.com"
RUN echo "deb http://ftp.debian.org/debian stretch-backports main" >> /etc/apt/sources.list \
  && apt-get update \
  && apt-get install -y cron \
  && apt-get install -y -qq vim \
  && apt-get install -y python-certbot-nginx -t stretch-backports \
  && apt-get purge -y --auto-remove
COPY crontab.txt crontab.txt
RUN crontab crontab.txt
COPY entrypoint.sh entrypoint.sh
RUN rm /etc/nginx/conf.d/default.conf
COPY conf.d /etc/nginx/conf.d
COPY nginx.conf /etc/nginx/nginx.conf
CMD ["bash", "entrypoint.sh"]
