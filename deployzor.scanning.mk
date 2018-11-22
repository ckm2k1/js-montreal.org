###############################################
#
#  Black duck scanning facility
#
#  Note. This is included from deployzor.mk and relies on targets and variables defined
#  therein. It can not be used on its own.
#
#  To scan an image with black duck, the following should be done:
#
#    make image.scan.{DPZ_COMPONENT}
#
#  The DPZ_SRC_PATH variable needs to be set for the scanning to work. The typical rules
#  that would be needed from the project Makefile would be:
#
#  scan: DPZ_SRC_PATH=/source/path/in/the/container
#  scan: image.scan.your_component_here ;

# Inlined Black Duck Dockerfile
#
define DPZ_BLACK_DUCK_DOCKERFILE
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
ARG PROJECT_CODE_LOCATION_NAME

# According to the BD documentation
# https://blackducksoftware.atlassian.net/wiki/spaces/INTDOCS/pages/49131875/Hub+Detect#HubDetect-DownloadingandrunningHubDetect
WORKDIR /hub-detect
RUN curl -s https://blackducksoftware.github.io/hub-detect/hub-detect.sh > hub-detect.sh && chmod +x hub-detect.sh

COPY --from=base / /

RUN pip install --no-cache-dir --upgrade pip
RUN pip freeze > /requirements.txt # need a requirements.txt to work

RUN /hub-detect/hub-detect.sh \\
    --detect.pip.requirements.path=/requirements.txt \\
    --detect.project.version.name=$${PROJECT_VERSION} \\
    --detect.project.version.phase=$${PROJECT_PHASE} \\
    --detect.project.name=$${PROJECT_NAME} \\
    --blackduck.url=https://elementai.blackducksoftware.com/ \\
    --blackduck.api.token="$${API_KEY}" \\
    --detect.code.location.name="$${PROJECT_CODE_LOCATION_NAME}" \\
    --detect.pip.python3=true \\
    --detect.source.path="$${PROJECT_SRC_PATH}"
endef
export DPZ_BLACK_DUCK_DOCKERFILE

image.scan.%.dockerfile: DPZ_COMPONENT=$*
image.scan.%.dockerfile:
	echo "$$DPZ_BLACK_DUCK_DOCKERFILE" > $@

DPZ_SRC_PATH?=/usr/src/app
image.scan.%: DPZ_COMPONENT=$*
image.scan.%: image.build.% image.scan.%.dockerfile
	docker build \
	--build-arg IMAGE_NAME=$(DPZ_DOCKER_IMAGE_NAME) \
	--build-arg IMAGE_TAG=$(DPZ_VERSION) \
	--build-arg API_KEY="$(BLACK_DUCK_API_KEY)" \
	--build-arg PROJECT_NAME=$(DPZ_PROJECT)-$(DPZ_COMPONENT) \
	--build-arg PROJECT_VERSION=$(if $(DPZ_VERSION_TAG),$(DPZ_VERSION_TAG),$(DPZ_BRANCH_NAME)) \
	--build-arg PROJECT_PHASE=$(if $(DPZ_VERSION_TAG),RELEASED,DEVELOPMENT) \
	--build-arg PROJECT_SRC_PATH=$(DPZ_SRC_PATH) \
	--build-arg PROJECT_CODE_LOCATION_NAME=$(if $(DPZ_VERSION_TAG),$(DPZ_VERSION_TAG),$(DPZ_BRANCH_NAME)) \
	-f image.scan.$*.dockerfile \
	.

.PHONY: image.scan.%
