# -*- coding: utf-8 -*-
#
# setup.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

from setuptools import setup, find_packages

install_requires = [
    "borgy-process-agent-api-server==1.5.0",
    "borgy-job-service-client==1.10.1",
    "parsedatetime==2.4",
    "python-dateutil==2.7.3",
    "dictdiffer==0.7.1",
    "docker==3.4.0",
    "connexion[swagger-ui]"
]

setup(
    name='borgy-process-agent',
    url='https://github.com/ElementAI/borgy-process-agent',
    version='1.13.0b7',
    description='',
    author='Borgy Team',
    packages=find_packages(exclude=('tests', 'docs')),
    install_requires=install_requires
)
