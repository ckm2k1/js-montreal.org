FROM python:3.6.5

ARG PIP_EXTRA_INDEX_URL

WORKDIR /usr/src/app

RUN export DEBIAN_FRONTEND=noninteractive; apt-get update && apt-get -y upgrade \
    && apt-get autoremove && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ADD requirements.txt ./
ADD setup.cfg ./
ADD setup.py ./

RUN pip install -r requirements.txt

ENV VERSION ${version}

ADD . .
