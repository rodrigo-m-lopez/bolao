#!/bin/sh

while sleep 60;
do 
	echo running crawler baby...
	python GloboEsporteCrawler.py; 
done

