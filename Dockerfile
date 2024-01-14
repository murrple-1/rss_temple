FROM python:3.12 as builder

ARG BUILD_ENV
ENV BUILD_ENV=${BUILD_ENV} PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1

RUN pip install -U pip pipenv && \
    python -m venv /venv
COPY Pipfile Pipfile.lock /venv/
WORKDIR /venv
RUN pipenv requirements $(test "$BUILD_ENV" != "production" && echo "--dev") > requirements.txt && \
    /venv/bin/pip install -r requirements.txt

FROM python:3.12 as production

RUN apt-get update && \
    apt-get install -y \
    ffmpeg espeak libjemalloc2 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    LD_PRELOAD=libjemalloc.so.2

COPY --from=builder /venv/ /venv/
WORKDIR /code
COPY . /code/

ENV PATH="/venv/bin/:${PATH}"
