#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# runner.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

from borgy_process_agent import ProcessAgent, ProcessAgentMode

i_pa = 0


def main():
    process_agent = ProcessAgent(mode=ProcessAgentMode.DOCKER)

    def return_new_jobs(pa):
        global i_pa
        i_pa = i_pa + 1
        res = {
            'command': ['bash', '-c', 'echo', str(i_pa), ';', 'sleep', str(i_pa)],
            'image': 'ubuntu:16.04'
        }
        return res

    process_agent.set_callback_jobs_provider(return_new_jobs)

    def jobs_update(jobs):
        print(jobs)

    process_agent.subscribe_jobs_update(jobs_update)

    process_agent.start()


if __name__ == '__main__':
    main()
