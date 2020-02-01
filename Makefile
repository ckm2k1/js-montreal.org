all: test package.build.process-agent

deployzor/deployzor.mk:
	git subtree add --squash --prefix deployzor git@github.com:ElementAI/eai-deployzor.git 3.3.0

DPZ_PROJECT=borgy
-include deployzor/deployzor.mk

test:
	@tox

test.full:
	@tox -e 'flake8,py37,coverage'

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


build:
	docker build -t asyncagent --build-arg PIP_EXTRA_INDEX_URL=$(PIP_EXTRA_INDEX_URL) .

build.vol:
	docker build -t volatile-images.borgy.elementai.net/asyncagent/asyncagent --build-arg PIP_EXTRA_INDEX_URL=$(PIP_EXTRA_INDEX_URL) .

run:
	docker run -it -p 8080:8666 asyncagent python main.py -d docker

publish:
	docker push volatile-images.borgy.elementai.net/asyncagent/asyncagent:latest

run.ork:
	borgy pa submit -i volatile-images.borgy.elementai.net/borgy/borgy-process-agent:async -- python main.py -d ork

run.ork.inter:
	borgy pa submit --restartable --preemptable -a interrupts=1 -a interrupt-after=15 -i volatile-images.borgy.elementai.net/borgy/borgy-process-agent:inter -- python main.py -d ork -v

run.local:
	python main.py $(args)
