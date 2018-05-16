.PHONY: test test.full
DEPLOYZOR_PROJECT=borgy
all: test package.build.process-agent
include deployzor.mk

test:
	@tox

test.full:
	@tox -e 'flake8,cov-init,py27,py34,py35,py36,coverage'

package.build.%:
	virtualenv -p python3 venv; \
	. venv/bin/activate; \
	python setup.py sdist; \
	deactivate; \
	mv dist/*.tar.gz $(DEPLOYZOR_PACKAGE_NAME); \

