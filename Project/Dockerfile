FROM python:3

MAINTAINER Rodrigo & Colodas "bolaodagalera@gmail.com"

RUN mkdir /app

WORKDIR /app

# We copy just the requirements.txt first to leverage Docker cache
COPY . .

RUN pip install -r requirements.txt

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
