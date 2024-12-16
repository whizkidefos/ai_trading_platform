@echo off
start cmd /k "celery -A core worker -l info"
start cmd /k "celery -A core beat -l info"
