#!/bin/sh

docker run -it -p 443:443 -p 80:80  -v /home/ec2-user/bolao/certs:/etc/letsencrypt -v /home/ec2-user/bolao/certs-lib:/var/lib/letsencrypt certbot/certbot certonly --standalone -d bolaodacopa2018.com -d www.bolaodacopa2018.com
