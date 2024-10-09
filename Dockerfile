FROM python:3.13-alpine AS builder

ARG BUILD_ENV
ENV BUILD_ENV=${BUILD_ENV} \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apk add gcc musl-dev postgresql-dev && \
    pip install -U pip pipenv && \
    python -m venv /venv
COPY Pipfile Pipfile.lock /venv/
WORKDIR /venv
RUN pipenv requirements $(test "$BUILD_ENV" != "production" && echo "--dev") > requirements.txt && \
    /venv/bin/pip install -r requirements.txt

FROM python:3.13-alpine AS production

RUN apk add ffmpeg espeak jemalloc postgresql-libs && \
    rm -rf /var/cache/apk/*
COPY --from=builder /venv/ /venv/
WORKDIR /code
COPY . /code/

ENV PATH="/venv/bin/:${PATH}" \
    PYTHONUNBUFFERED=1 \
    LD_PRELOAD=libjemalloc.so.2
