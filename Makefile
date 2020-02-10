all: test package.build.process-agent

deployzor/deployzor.mk:
	git subtree add --squash --prefix deployzor git@github.com:ElementAI/eai-deployzor.git 3.3.0

DPZ_PROJECT=borgy
-include deployzor/deployzor.mk

test:
	@tox -e 'py37'

test.full: test # backwards compat.

flake8:
	python -m flake8

image.build.%: DPZ_DOCKER_BUILD_OPTIONS_EXTRA=--build-arg PIP_EXTRA_INDEX_URL=$(PIP_EXTRA_INDEX_URL)

package.build.%:
	virtualenv -p python3 venv; \
	. venv/bin/activate; \
	python setup.py sdist; \
	deactivate; \
	mv dist/*.tar.gz $(DPZ_PACKAGE_NAME)

.PHONY: test test.full

run.ork:
	borgy pa submit -i images.borgy.elementai.net/borgy/process-agent:async -- borgy_process_agent -v $(args)

run.ork.inter:
	borgy pa submit --restartable --preemptable -a interrupts=1 -a interrupt-after=15 -i images.borgy.elementai.net/borgy/process-agent:inter -- borgy_process_agent -v

run.local:
	borgy_process_agent $(args)

test.docker.integ:
	PA_TESTER_CHILDREN=10 borgy_process_agent -d docker --integration-tests $(args)
	test -z $? || (echo Integration tests failed.; exit 1)
