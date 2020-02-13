from typing import List

import pytest

from borgy_process_agent.models import OrkJob
from borgy_process_agent.enums import State, Restart
from borgy_process_agent.job2 import Job

oj = {
    "alive": False,
    "billCode": "default",
    "command": ["python3", "-m", "model.tadam", "--log_dir=/logs", "--number_of_steps=21000"],
    "createdBy": "thomas@elementai.com",
    "createdOn": "2019-05-09T19:45:36.879276+00:00",
    "environmentVars": [
        "EAI_PROCESS_AGENT_INDEX=0", "EAI_PROCESS_AGENT=d45e066c-3177-4a1d-b03c-cb196232d2a4",
        "SHK_TRIAL_ID=646174",
        "SHK_API_URL=http://shk-service.eai-shuriken-prod.svc.borgy-k8s.elementai.lan/api/v1"
    ],
    "evictOthersIfNeeded": False,
    "id": "11f4d244-c5bb-4706-93c3-55b4abf7b2df",
    "image": "images.borgy.elementai.net/tadam/tadam:de9f22b4c41c9105be1abdd2c9ca9560b85adb69",
    "interactive": False,
    "isProcessAgent": False,
    "labels": [],
    "maxRunTimeSecs": 0,
    "name": "tadam-sgd-aixfe-646174",
    "options": {},
    "preemptable": True,
    "reqCores": 1.2,
    "reqGpus": 1,
    "reqRamGbytes": 6,
    "restart": "no",
    "runs": [{
        "createdOn": "2019-05-09T19:45:36.879276+00:00",
        "endedOn": "2019-05-10T02:21:00+00:00",
        "exitCode": 0,
        "id": "266c6ebf-2ac6-4d82-921f-b1e8bb8257ac",
        "info": {
            "gpu_uuids": ["GPU-9e0ab4c3-2da0-a56a-0f68-087fc49478b0"],
            "gpus": [1]
        },
        "ip": "10.200.34.99",
        "jobId": "11f4d244-c5bb-4706-93c3-55b4abf7b2df",
        "nodeName": "dc1-8gpu-21",
        "queuedOn": "2019-05-09T19:45:43.409909+00:00",
        "startedOn": "2019-05-09T19:45:45+00:00",
        "state": "SUCCEEDED"
    }],
    "state": "SUCCEEDED",
    "stateInfo": "",
    "stdin": False,
    "volumes": ["/mnt/datasets/public/:/data", "/mnt/home/thomas/logs/tadam:/logs"],
    "workdir": ""
},


class TestJob2:

    def test_init(self):
        job = Job(1, 'parent')
        assert job.updated is None
        assert job.created is None
        assert job.user is None
        assert job.parent_id == 'parent'
        assert job.state == State.PENDING

    def test_init_from_spec(self):
        job = Job.from_spec(1, 'user', 'parent', spec={
            'command': ['bash'],
            'image': 'ubuntu',
        })

        assert job.user == 'user'
        assert job.parent_id == 'parent'
        assert isinstance(job.ork_job, OrkJob)

