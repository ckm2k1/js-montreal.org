# EAI Process Agent

[![Drone](https://drone.elementai.com:8443/api/badges/ElementAI/borgy-process-agent/status.svg?branch=dev)](https://drone.elementai.com:8443/ElementAI/borgy-process-agent)
[![Coverage Status](https://coveralls.io/repos/github/ElementAI/borgy-process-agent/badge.svg?branch=master&t=zqIPKC)](https://coveralls.io/github/ElementAI/borgy-process-agent)

## What is the process agent?
The process agent is designed primarily as a low level tool for running, managing and monitoring multiple jobs in the
Ork cluster. You can find details about it's internals in the sections below.
The agent runs mostly like any other job in the cluster but with the important distinction that it is also
responsible for it's child jobs and if terminated, all children will be shutdown as well.

### Who is it for?
The agent can be used by anyone with access to the cluster, but is generally recommended for users who wish
run multiple jobs with usecases that are too simple or unfitting to run with Shuriken. Additionally, anyone looking
to implement job run patterns that are not currently supported or are too custom to implement in the agent can
easily extend the agent for their own use.

## Installation & Usage

### Installing locally

From github:
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

Read the full tutorial here: [Tutorial](tutorial.md)

## Contributing

### Install requirements

Before you start, we highly recommend creating a new virtual env and installing dependencies inside it.
Python 3.7+ is required to run the agent.

1. Update `~/.pip/pip.conf` with extra index url:
```sh
[global]
extra-index-url = https://username:password@pypi.elmt.io/repo/eai-core
```
1. Install requirements
```sh
pip install -r ./requirements.txt
```
OR call directly pip with extra index url in parameter:
```sh
pip install --extra-index-url https://username:password@pypi.elmt.io/repo/eai-core -r ./requirements.txt
```
1. Install test dependencies
```sh
pip install -r ./requirements-tests.txt
```
1. If you want to be able to invoke the agent as a cli command, install the package:
```sh
pip install -e .
```
You can now use `borgy_process_agent` while your virtualenv is active.

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

Make sure tests dependencies are installed first.
Run the following for the full test suite, including coverage:

```sh
# Unit tests using the generated tests
make test
```
You can view an HTML version of the coverage report by opening the `index.html` file in the
coverage_html directory that will be generated after the tests have run.

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


![Process agent schema](./docs/process-agent.png)