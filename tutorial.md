## Overview
The agent can be used in 2 main ways, by invoking the official docker image with a path to your
user code (**recommended**), or by installing the agent framework locally as a package and calling
it from your own code.

Before we write any user code, it's useful to understand the agent protocol at a high level.
The agent can be thought of as a kind of process manager, starting, observing and stopping jobs while providing
updates to the user about the status of each job. At the same time it also acts like a mini-dashboard,
used see the current state of your jobs, like the Task Manager in Windows or the Activity Monitor in OSX.

## Basic use case
To get a sense of how the agent works , let's walk through the example below.

Say that as a researcher you'd like to ensure a given model produces the same results
(within a reasonable statistical margin) on every run. All we need to do is get the agent to
submit the same job multiple times and let us know when things are done so we can analyze the
output.

```python
jobs_idx = 0
jobs_to_submit = [
    {'command': ['/code/mymodel.py'], 'image': 'images.borgy.elementai.net/myproject/myimage:latest'},
    {'command': ['/code/mymodel.py'], 'image': 'images.borgy.elementai.net/myproject/myimage:latest'},
    {'command': ['/code/mymodel.py'], 'image': 'images.borgy.elementai.net/myproject/myimage:latest'},
    {'command': ['/code/mymodel.py'], 'image': 'images.borgy.elementai.net/myproject/myimage:latest'}
]

def user_create(agent):
    global jobs_idx, jobs_to_submit
    if jobs_index == len(jobs_to_submit):
        return None
    specs = jobs_to_submit[jobs_idx::1]
    jobs_idx += 1
    return specs

def user_update(agent, jobs):
    pass
```

### Submit a process agent job

To submit the job, you need to use the `pa` subset of commands in borgy CLI.
For example:
```sh
borgy pa submit -i images.borgy.elementai.net/borgy/process-agent:2.0.0 -- borgy_process_agent -c /path/to/my_user_code.py
```
You can use `borgy help pa submit` for a full list of options to the `pa submit` command.
