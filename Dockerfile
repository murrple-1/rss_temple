FROM python:3.11 as builder

ARG BUILD_ENV
ENV BUILD_ENV=${BUILD_ENV} PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1

RUN pip install -U pip pipenv && python -m venv /venv
COPY Pipfile Pipfile.lock /venv/
WORKDIR /venv
RUN pipenv requirements $(test "$BUILD_ENV" != "production" && echo "--dev") > requirements.txt && /venv/bin/pip install -r requirements.txt

FROM python:3.11 as production

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y ffmpeg espeak && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=builder /venv/ /venv/
WORKDIR /code
COPY . /code/

ENV PATH="/venv/bin/:${PATH}"
