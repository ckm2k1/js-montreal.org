
all: test package.build.process-agent

deployzor/deployzor.mk:
	git subtree add --squash --prefix deployzor git@github.com:ElementAI/eai-deployzor.git 1.2.0

DEPLOYZOR_PROJECT=borgy
-include deployzor/deployzor.mk

test:
	@tox

test.full:
	@tox -e 'flake8,cov-init,py34,py35,py36,coverage'

image.build.%: DEPLOYZOR_DOCKER_OPTIONS_EXTRA=--build-arg PIP_EXTRA_INDEX_URL=$(PIP_EXTRA_INDEX_URL)

package.build.%:
	virtualenv -p python3 venv; \
	. venv/bin/activate; \
	python setup.py sdist; \
	deactivate; \
	mv dist/*.tar.gz $(DEPLOYZOR_PACKAGE_NAME)

docker-build-pythons:
	docker build -f docker/Dockerfile-pythons -t $(DEPLOYZOR_DOCKER_REGISTRY)/$(DEPLOYZOR_PROJECT)/pythons .

docker-publish-pythons: docker-build-pythons
	docker push $(DEPLOYZOR_DOCKER_REGISTRY)/$(DEPLOYZOR_PROJECT)/pythons

.PHONY: test test.full
