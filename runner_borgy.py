#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# runner.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

import logging
from borgy_process_agent import ProcessAgent, ProcessAgentMode

i_pa = 0


def main():
    logging.basicConfig(level=logging.DEBUG)
    process_agent = ProcessAgent(mode=ProcessAgentMode.BORGY, port=1234)

    def return_new_jobs(pa):
        global i_pa
        i_pa = i_pa + 1
        if i_pa > 5:
            return None
        res = {
            'command': [
                'bash',
                '-c',
                'echo "step '+str(i_pa)+'";for i in $(seq 1 '+str(i_pa*5)+');do echo $i;sleep 1;done;echo done'
            ],
            'image': 'ubuntu:16.04'
        }
        return res

    process_agent.set_callback_jobs_provider(return_new_jobs)

    def jobs_update(event):
        for j in event.jobs:
            print("My job {} updated to {}".format(j['job'].id, j['job'].state))
        # jobs = event.pa.get_jobs()
        # print("All jobs:")
        # for j in jobs.values():
        #     print("  job {}: {}".format(j.id, j.state))

    process_agent.subscribe_jobs_update(jobs_update)

    process_agent.start()
    jobs = process_agent.get_jobs()
    print('\nAll my finished job:')
    for j in jobs.values():
        print("\tjob {}: {}".format(j.id, j.state))
        print("\t\tResult: {}".format(j.runs[-1].result))


if __name__ == '__main__':
    main()
