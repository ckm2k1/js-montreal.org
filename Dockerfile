FROM python:alpine3.6

WORKDIR /usr/src/app

RUN apk update \
 && apk upgrade

ADD requirements.txt ./
ADD setup.cfg ./
ADD setup.py ./

ARG PIP_EXTRA_INDEX_URL
RUN pip install -r requirements.txt

COPY requirements-tests.txt ./
RUN pip install -r requirements-tests.txt

ARG DPZ_VERSION
ENV VERSION ${DPZ_VERSION}

ADD . .
RUN pip install -e .

CMD /usr/local/bin/python3 /usr/src/app/runner_test.py
