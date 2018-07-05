# -*- coding: utf-8 -*-
#
# setup.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

from setuptools import setup, find_packages

install_requires = [
    "borgy-process-agent-api-server==1.1.0",
    "borgy-job-service-client==1.6.4",
    "parsedatetime==2.4",
    "python-dateutil==2.7.3",
    "dictdiffer==0.7.1",
    "docker==3.4.0"
]

setup(
    name='borgy-process-agent',
    version='1.3.0',
    description='',
    author='Borygy Team',
    packages=find_packages(exclude=('tests', 'docs')),
    install_requires=install_requires
)
