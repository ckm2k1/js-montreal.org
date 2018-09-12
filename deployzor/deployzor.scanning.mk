###############################################
#
#  Black duck scanning facility
#
#  Note. This is included from deployzor.mk and relies on targets and variables defined
#  therein. It can not be used on its own.
#
#  To scan an image with black duck, the following should be done:
#
#    make image.scan.{COMPONENT}
#
#  The SRC_PATH variable needs to be set for the scanning to work. The typical rules
#  that would be needed from the project Makefile would be:
#
#  scan: SRC_PATH=/source/path/in/the/container
#  scan: image.scan.your_component_here ;

# Inlined Black Duck Dockerfile
#
define BLACK_DUCK_DOCKERFILE
ARG IMAGE_TAG
ARG IMAGE_NAME

FROM $${IMAGE_NAME}:$${IMAGE_TAG} as base

# Use same distro as your base image https://hub.docker.com/_/openjdk/
FROM openjdk:8-jre as blackduck

ARG API_KEY
ARG PROJECT_NAME
ARG PROJECT_VERSION
ARG PROJECT_PHASE
ARG PROJECT_SRC_PATH

# According to the BD documentation
# https://blackducksoftware.atlassian.net/wiki/spaces/INTDOCS/pages/49131875/Hub+Detect#HubDetect-DownloadingandrunningHubDetect
WORKDIR /hub-detect
RUN curl -s https://blackducksoftware.github.io/hub-detect/hub-detect.sh > hub-detect.sh && chmod +x hub-detect.sh

COPY --from=base / /

RUN pip install --no-cache-dir --upgrade pip # work only with pip<10
RUN pip freeze > /requirements.txt # need a requirements.txt to work

RUN /hub-detect/hub-detect.sh \\
    --detect.pip.requirements.path=/requirements.txt \\
    --detect.project.version.name=$${PROJECT_VERSION} \\
    --detect.project.version.phase=$${PROJECT_PHASE} \\
    --detect.project.name=$${PROJECT_NAME} \\
    --blackduck.hub.url=https://elementai.blackducksoftware.com/ \\
    --blackduck.hub.api.token="$${API_KEY}" \\
    --detect.pip.python3=true \\
    --detect.source.path="$${PROJECT_SRC_PATH}"
endef
export BLACK_DUCK_DOCKERFILE

image.scan.%.dockerfile: COMPONENT=$*
image.scan.%.dockerfile:
	echo "$$BLACK_DUCK_DOCKERFILE" > $@

SRC_PATH?=/usr/src/app
image.scan.%: COMPONENT=$*
image.scan.%: image.build.% image.scan.%.dockerfile
	docker build \
	--build-arg IMAGE_NAME=$(DOCKER_IMAGE_NAME) \
	--build-arg IMAGE_TAG=$(VERSION) \
	--build-arg API_KEY="$(BLACK_DUCK_API_KEY)" \
	--build-arg PROJECT_NAME=$(DEPLOYZOR_PROJECT)-$(COMPONENT) \
	--build-arg PROJECT_VERSION=$(VERSION) \
	--build-arg PROJECT_PHASE=$(if $(VERSION_TAG),RELEASED,DEVELOPMENT) \
	--build-arg PROJECT_SRC_PATH=$(SRC_PATH) \
	-f image.scan.$*.dockerfile \
	.

.PHONY: image.scan.%
