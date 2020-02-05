FROM python:3.7.6
ARG SERVER_PORT=8666
ARG PIP_EXTRA_INDEX_URL

WORKDIR /app
ADD requirements.txt ./
ADD setup.cfg ./
ADD setup.py ./
RUN pip install -r requirements.txt

ARG DPZ_VERSION
ENV VERSION ${DPZ_VERSION}

ADD . .
RUN pip install -e .
CMD ["borgy_process_agent"]