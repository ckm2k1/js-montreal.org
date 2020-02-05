# -*- coding: utf-8 -*-
#
# setup.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

from setuptools import setup, find_packages

setup(
    name='borgy-process-agent',
    url='https://github.com/ElementAI/borgy-process-agent',
    version='2.0.0',
    description='',
    author='Borgy Team',
    packages=find_packages(exclude=('tests', 'docs')),
    entry_points={'console_scripts': ['borgy_process_agent=borgy_process_agent.__main__:main']},
)
