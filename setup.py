# -*- coding: utf-8 -*-
#
# setup.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

from setuptools import setup, find_packages

install_requires = [
    "borgy-process-agent-api-server==1.12.2",
    "parsedatetime>=2.4.0,<3.0.0",
    "python-dateutil>=2.6.0,<3.0.0",
    "dictdiffer>=0.7.1,<1.0.0",
    "docker>=3.4.0,<4.0.0",
    "connexion[swagger-ui]>=2.0.0,<3.0.0",
    "blinker>=1.4,<2.0.0",
    "prometheus_client>=0.6.0,<1.0.0"
]

setup(
    name='borgy-process-agent',
    url='https://github.com/ElementAI/borgy-process-agent',
    version='1.18.1',
    description='',
    author='Borgy Team',
    packages=find_packages(exclude=('tests', 'docs')),
    install_requires=install_requires
)
