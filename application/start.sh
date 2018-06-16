#!/bin/sh


# please do not change this file...please!

echo _Starting...

echo _    Running Crawler...
python GloboEsporteCrawler.py
echo _    Running Crawler...OK!

# echo _    Starting Cron...
# crontab crawler_cron
# service cron start
# echo _    Starting Cron...OK!

echo _    Starting Loop...
nohup sh ./loop.sh &
echo _    Starting Loop...OK!

echo "Environment variables..."
export
echo "Environment variables...OK!"

echo "All proccesses..."
ps aux

echo _Starting...OK!
gunicorn -w 1 -b :8000 app:app
