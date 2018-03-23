#!/bin/sh

echo _Starting...

echo _    Running Crawler...
#python GloboEsporteCrawler.py
echo _    Running Crawler...OK!

echo _    Starting Cron...
crontab crawler_cron
service cron start
echo _    Starting Cron...OK!

echo _Starting...OK!
python hello.py
