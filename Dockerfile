FROM python:3.10-slim

ARG APP_ENVIRONMENT=production

ENV LANG="C.UTF-8"\
	LC_ALL="C.UTF-8"\
	PYTHONDONTWRITEBYTECODE=1\
	PYTHONFAULTHANDLER=1

WORKDIR /rss_temple

COPY . .

RUN pip install -U pip\
	&& pip install --no-cache-dir pipenv\
	&& pipenv install --system --deploy $(if [ "$APP_ENVIRONMENT" != "production" ]; then echo '--dev'; fi)
