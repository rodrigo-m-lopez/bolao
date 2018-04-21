#!/bin/sh

call_certbot() {
  if [ "$PROD" == "true" ]
  then
    echo "running certbot in prod mode"
  else
    echo "running certbot in test mode"
    EXTRA_ARGS="--test-cert"
  fi

  certbot $EXTRA_ARGS --nginx -m $CERTBOT_EMAIL --agree-tos --eff-email --noninteractive -d $CERTBOT_DOMAIN
}

if [ -z "$CERTBOT_EMAIL" ]; then
  echo "No certbot email set, exiting"
  exit 1
fi

if [ -z "$CERTBOT_DOMAIN" ]; then
  echo "No certbot domain set, exiting"
  exit 1
fi

# When we get killed, kill all our children
trap "exit" INT TERM
trap "kill 0" EXIT

# Start up nginx, save PID so we can reload config inside of run_certbot.sh
nginx -g "daemon off;" &
export NGINX_PID=$!

#If the cert isn't out there yet, call certbot for it
if [ ! -f "/etc/letsencrypt/live/$CERTBOT_DOMAIN/fullchain.pem" ]; then
  echo "calling call_certbot"
  call_certbot
fi

echo "Contents of my project.conf"
cat /etc/nginx/conf.d/project.conf

# Run `cron -f &` so that it's a background job owned by bash and then `wait`.
# This allows SIGINT (e.g. CTRL-C) to kill cron gracefully, due to our `trap`.
cron -f &
wait "$NGINX_PID"
