# Borgy Process Agent

## Requirements.

Python 3.3+

## Installation & Usage

### pip install

If the python package is hosted on Github, you can install directly from Github

```sh
pip install git+ssh://git@github.com/ElementAI/borgy-process-agent.git
```

You can also install from the distribution server:

```sh
pip install http://distrib.borgy.elementai.lan/python/borgy-process-agent/borgy-process-agent-[version].tar.gz
```

Finally, it is also possible to install from our private pypi repository:

```sh
pip install --extra-index-url https://pypi.elmt.io/repo/eai-ai-enablement borgy-process-agent==[version]
```

### Setuptools

Install via [Setuptools](http://pypi.python.org/pypi/setuptools).

```sh
python setup.py install --user
```
(or `sudo python setup.py install` to install the package for all users)

### Getting Started


Please follow the [installation procedure](#installation--usage) and then here is a python 3 example:

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

## Contributing

### Install requirements

Update `~/.pip/pip.conf` with extra index url:
```sh
[global]
extra-index-url = https://username:password@pypi.elmt.io/repo/eai-ai-enablement
```
and call pip to install requirements
```sh
pip install -r ./requirements.txt
```

OR call directly pip with extra index url in parameter:

```sh
pip install --extra-index-url https://username:password@pypi.elmt.io/repo/eai-ai-enablement -r ./requirements.txt
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
make VERSION_TAG_LAST=[new_version]
git commit -a -m "Upgrade to [new_version]"
git tag [new_version]
```

**NOTE: The tag must match the version used in VERSION_TAG_LAST above**

Once merged in the dev branch - after appropriate pull request process - a tag will
release the package through drone. Release notes will be added to the repo on github,
a source distribution will be made available in:

http://distrib.borgy.elementai.lan/python/borgy-process-agent/
