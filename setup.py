# -*- coding: utf-8 -*-
#
# setup.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

from setuptools import setup, find_packages

install_requires = [
    "borgy-process-agent-api-server==0.0.4",
    "parsedatetime==2.4",
    "python-dateutil==2.7.3",
    "six==1.11.0",
    "dictdiffer==0.7.1"
]

setup(
    name='borgy-process-agent',
    version='0.0.1',
    description='',
    author='Borygy Team',
    packages=find_packages(exclude=('tests', 'docs')),
    install_requires=install_requires,
    dependency_links=[
        'http://distrib.borgy.elementai.lan/python/borgy-process-agent-api/' # noqa
    ]
)