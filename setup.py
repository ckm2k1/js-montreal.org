# -*- coding: utf-8 -*-
#
# setup.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

from setuptools import setup, find_packages

install_requires = [
    "aiohttp==3.6.2",
    "aiohttp_jinja2==1.2.0",
    "borgy-process-agent-api-server==1.12.2",
    "borgy-process-agent-api-client==1.12.2",
    "dictdiffer==0.8.1",
    "docker==4.1.0",
    "parsedatetime>=2.4.0,<3.0.0",
    "python-dateutil>=2.6.0,<3.0.0",
    "connexion[swagger-ui]>=2.0.0,<3.0.0",
    "blinker>=1.4,<2.0.0",
    "prometheus_client>=0.6.0,<1.0.0",
]

setup(
    name='borgy-process-agent',
    url='https://github.com/ElementAI/borgy-process-agent',
    version='2.0.0',
    description='',
    author='Borgy Team',
    packages=find_packages(exclude=('tests', 'docs')),
    install_requires=install_requires
)
