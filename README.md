# EAI Process Agent

[![Drone](https://drone.elementai.com:8443/api/badges/ElementAI/borgy-process-agent/status.svg?branch=dev)](https://drone.elementai.com:8443/ElementAI/borgy-process-agent)
[![Coverage Status](https://coveralls.io/repos/github/ElementAI/borgy-process-agent/badge.svg?branch=master&t=zqIPKC)](https://coveralls.io/github/ElementAI/borgy-process-agent)

Process agents allow submission of a single job to EAI which is composed of many jobs and can evolve based on results from previously submitted jobs.

![Process agent schema](./docs/process-agent.png)

## Requirements.

Python 3.7+

## Installation & Usage

### pip install

If the python package is hosted on Github, you can install directly from Github

```sh
pip install git+ssh://git@github.com/ElementAI/borgy-process-agent.git
```

You can also install from the distribution server:

```sh
pip install https://distrib.borgy.elementai.net/python/borgy-process-agent/borgy-process-agent-[version].tar.gz
```

Finally, it is also possible to install from our private pypi repository:

```sh
pip install --extra-index-url https://pypi.elmt.io/repo/eai-core borgy-process-agent==[version]
```

### Setuptools

Install via [Setuptools](https://pypi.python.org/pypi/setuptools).

```sh
python setup.py install --user
```
(or `sudo python setup.py install` to install the package for all users)

### Getting Started


Please follow the [installation procedure](#installation--usage) and then here is a Python 3 example:

```python
from borgy_process_agent import ProcessAgent

i_job = 0
process_agent = ProcessAgent()

def return_new_jobs(pa):
    global i_job
    i_job = i_job + 1
    res = [{'command': ['sleep', str(i_job)]}]
    return res

process_agent.set_callback_jobs_provider(return_new_jobs)

def jobs_update(event):
    print(event.pa)
    print(event.jobs)

process_agent.subscribe_jobs_update(jobs_update)

process_agent.start()
```

Another example to launch a set of jobs:
```python
process_agent = ProcessAgent()

jobs_idx = 0
jobs_to_submit = [
{'command': ['sleep', 5]},
{'command': ['sleep', 5]},
{'command': ['sleep', 5]},
{'command': ['sleep', 5]}
]

def return_new_jobs(pa):
    global jobs_idx, jobs_to_submit
    specs = jobs_to_submit[jobs_idx:jobs_idx+100]
    if not specs:
        return None
    jobs_idx = jobs_idx + 100
    return specs

process_agent.set_callback_jobs_provider(return_new_jobs)

def jobs_update(event):
    print(event.pa)
    print(event.jobs)

process_agent.subscribe_jobs_update(jobs_update)

process_agent.start()
```

### Submit the process agent job

To submit the job, you need to use the `pa` subset of commands in borgy CLI.

Example to submit a jobs:

```sh
borgy pa submit -e PA_TESTER_CHILDREN=3 -i images.borgy.elementai.net/borgy/process-agent:1.16.0
```


## Contributing

### Install requirements

Update `~/.pip/pip.conf` with extra index url:
```sh
[global]
extra-index-url = https://username:password@pypi.elmt.io/repo/eai-core
```
and call pip to install requirements
```sh
pip install -r ./requirements.txt
```

OR call directly pip with extra index url in parameter:

```sh
pip install --extra-index-url https://username:password@pypi.elmt.io/repo/eai-core -r ./requirements.txt
```

## Build

The project uses deployzor to build and distrib the process agent.


To build pip package:
```
make
```

To simulate the distribution of the pip packages locally:
```
export DEPLOYZOR_DISTRIB_BASE=./distrib
make package.build.process-agent package.distrib.process-agent
```


### Testing

In a virtual env, do the following:

```sh
# Unit tests using the generated tests
pip install -r requirements.txt
pip install -r requirements-tests.txt

make test

# Full test - All python versions
make test.full
```

### Releasing

```sh
vim setup.py
git commit -a -m "Upgrade to [new_version]"
git tag [new_version]
```

**NOTE: The tag must match the version used in VERSION_TAG_LAST above**

Once merged in the dev branch - after appropriate pull request process - a tag will
release the package through drone. Release notes will be added to the repo on github,
a source distribution will be made available in:

https://distrib.borgy.elementai.net/python/borgy-process-agent/
