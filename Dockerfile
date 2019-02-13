FROM python:3.6.5

WORKDIR /usr/src/app

RUN export DEBIAN_FRONTEND=noninteractive; apt-get update && apt-get -y upgrade \
    && apt-get autoremove && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ADD requirements.txt ./
ADD setup.cfg ./
ADD setup.py ./

ARG PIP_EXTRA_INDEX_URL
RUN pip install -r requirements.txt

ARG DPZ_VERSION
ENV VERSION ${DPZ_VERSION}

ADD . .
RUN pip install -e .

CMD /usr/local/bin/python3 /usr/src/app/runner_test.py
