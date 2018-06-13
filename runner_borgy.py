#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# runner.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

import os
import uuid
from borgy_process_agent import ProcessAgent
from borgy_process_agent.config import Config


i_pa = 0


def main():
    os.environ['BORGY_JOB_ID'] = str(uuid.uuid4())
    os.environ['BORGY_USER'] = 'gsm'

    Config.set('port', 1234)
    process_agent = ProcessAgent()

    def return_new_jobs(pa):
        global i_pa
        i_pa = i_pa + 1
        res = [{'command': ['bash', str(i_pa)]}]
        return res

    process_agent.set_callback_jobs_provider(return_new_jobs)

    def jobs_update(jobs):
        print(jobs)

    process_agent.subscribe_jobs_update(jobs_update)

    process_agent.start()


if __name__ == '__main__':
    main()
