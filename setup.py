# -*- coding: utf-8 -*-
#
# setup.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

from setuptools import setup, find_packages

install_requires = [
    "borgy-process-agent-api-server==0.1.1",
    "borgy-job-service-client==1.6.3",
    "parsedatetime==2.4",
    "python-dateutil==2.7.3",
    "dictdiffer==0.7.1"
]

setup(
    name='borgy-process-agent',
    version='0.0.19',
    description='',
    author='Borygy Team',
    packages=find_packages(exclude=('tests', 'docs')),
    install_requires=install_requires,
    extras_require={
        'docker':  ["docker==3.4.0"],
    }
)
