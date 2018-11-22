# Copyright (c) 2017 ElementAI. All rights reserved.
#
# Get usage notes at github.com/ElementAI/eai-deployzor

# Parameters to configure behavior before inclusion:
#
# DPZ_PROJECT: (MANDATORY)
#   Used as a namespace in the Docker image name.

$(if $(DPZ_PROJECT),,$(error DPZ_PROJECT should be set before including $(lastword $(MAKEFILE_LIST))))
#
# DPZ_BASE_PATH:
#   Path from where the components files will be searched from. (default: empty, thus current directory)
DPZ_BASE_PATH?=.
#
# DPZ_USE_COMPONENT_PREFIX:
#   Should be set to "1" if more than one component are to be built and maybe deployed
#   from the same repo. If set, the component Dockerfile and k8s-deploy.template will
#   be found in the $(DPZ_COMPONENT)/ subdirectory under $(DPZ_COMPONENTS_ROOT). If not,
#   both the Dockerfile and k8s-deploy.template will be found in the $(DPZ_COMPONENTS_ROOT)
#   directory. (default: unset, thus false)

DPZ_COMPONENT_PREFIX_DIR=$(DPZ_BASE_PATH)$(if $(findstring 1,$(DPZ_USE_COMPONENT_PREFIX)),/%)

# Version synthesis
#
_DPZ_VERSION_TAG_LAST=$(shell git describe --tags --abbrev=0 2> /dev/null)
DPZ_VERSION_TAG_LAST:=$(if $(_DPZ_VERSION_TAG_LAST),$(_DPZ_VERSION_TAG_LAST),0.0.1)
DPZ_VERSION_COMMIT=$(shell git rev-parse --short HEAD)
DPZ_VERSION_TAG=$(shell git describe --exact-match --tags $(DPZ_VERSION_COMMIT) 2> /dev/null)
DPZ_BRANCH_NAME=$(shell git rev-parse --abbrev-ref HEAD)
DPZ_VERSION:=$(if $(DPZ_VERSION),$(DPZ_VERSION),$(_DPZ_VERSION))
_DPZ_VERSION ?= $(shell \
	if [ -z "`git status --porcelain`" ]; then \
		if echo $(DPZ_VERSION_TAG) | grep -qE "([0-9]+\.){2}[0-9]+\w*"; then \
			echo $(DPZ_VERSION_TAG); \
		else \
			echo $(DPZ_VERSION_COMMIT); \
		fi \
	else \
	    echo `whoami`-`git rev-parse --abbrev-ref HEAD`-`git rev-parse --short HEAD`-`date +%Y%m%d%H%M%S`; \
	fi)
DPZ_VERSION_SPECIFIED:=$(if $(DPZ_VERSION),true,false)
DPZ_VERSION:=$(if $(DPZ_VERSION),$(DPZ_VERSION),$(_DPZ_VERSION))

# Image naming and building
#
DPZ_DOCKER_REGISTRY?=images.borgy.elementai.lan
DPZ_COMPONENT?=
DPZ_DOCKER_IMAGE_NAME?=$(DPZ_DOCKER_REGISTRY)/$(DPZ_PROJECT)/$(DPZ_COMPONENT)
DPZ_DOCKER_FULL_IMAGE_NAME?=$(DPZ_DOCKER_REGISTRY)/$(DPZ_PROJECT)/$(DPZ_COMPONENT):$(DPZ_VERSION)
_DPZ_FORCE_BUILD:=$(if $(findstring 1,$(DPZ_FORCE_BUILD)),true,false)
# Official regex from https://github.com/docker/distribution/blob/master/reference/regexp.go#L31
DPZ_DOCKER_REGEX_DOMAIN="^([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9](\.[a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9])*(:[0-9]+)?)"
DPZ_DOCKER_DOMAIN?=$(shell echo $(DPZ_DOCKER_REGISTRY) | grep -oE $(DPZ_DOCKER_REGEX_DOMAIN))
DPZ_DOCKER_AUTH?= $(shell \
	if command -v python > /dev/null; then \
	  cat ~/.docker/config.json|python -c "import sys, json; print(json.load(sys.stdin)['auths']['$(DPZ_DOCKER_DOMAIN)']['auth'])" 2> /dev/null; \
	fi)
DPZ_DOCKER_CURL_BASIC_AUTH?=$(if $(DPZ_DOCKER_AUTH),-H 'Authorization:Basic $(DPZ_DOCKER_AUTH)')

# This makes sure that the required Dockerfile exists
#
$(DPZ_COMPONENT_PREFIX_DIR)/Dockerfile:
	@echo ""; echo "     " Expected \"$@\" is not found, can not build image.; echo ""; exit 1

# Generic docker build target
# `make image.build.foo` builds a docker based on the foo/Dockerfile file.
#
image.build.%: DPZ_COMPONENT=$*
image.build.%: $(DPZ_COMPONENT_PREFIX_DIR)/Dockerfile $(if $(findstring 1,$(DPZ_ENABLE_BUILD_DEPENDENCY)),build.%)
	docker build $(DPZ_DOCKER_BUILD_OPTIONS_EXTRA) --build-arg DPZ_VERSION=$(DPZ_VERSION) --build-arg DPZ_PROJECT=$(DPZ_PROJECT) --build-arg DPZ_COMPONENT=$(DPZ_COMPONENT) -f $< -t $(DPZ_DOCKER_FULL_IMAGE_NAME) $(if $(findstring 1,$(DPZ_GLOBAL_DOCKER_CONTEXT)),.,$(<D))


image.run.%: DPZ_COMPONENT=$*
image.run.%: image.build.%
	docker run $(DPZ_DOCKER_RUN_OPTIONS_EXTRA) --rm $(DPZ_DOCKER_FULL_IMAGE_NAME) $(DPZ_CMD)

image.delete.%: DPZ_COMPONENT=$*
image.delete.%:
	docker rmi --no-prune $(DPZ_DOCKER_FULL_IMAGE_NAME)

image.volatile_run.%: DPZ_COMPONENT=$*
image.volatile_run.%:
	rc=0; \
	  make image.run.$* DPZ_VERSION=$(DPZ_VERSION) \
	    DPZ_CMD='$(DPZ_CMD)' || rc=$$?; \
	  make image.delete.$* DPZ_VERSION=$(DPZ_VERSION)>/dev/null; exit $$rc;

image.publish.%: DPZ_COMPONENT=$*
image.publish.%:
	@echo Checking for $(DPZ_DOCKER_FULL_IMAGE_NAME) in registry;\
	set -e; \
	if ($(_DPZ_FORCE_BUILD) || ! curl -k -f --head $(DPZ_DOCKER_CURL_BASIC_AUTH) https://$(DPZ_DOCKER_REGISTRY)/v2/$(DPZ_PROJECT)/$(DPZ_COMPONENT)/manifests/$(DPZ_VERSION) 2>/dev/null >/dev/null); \
	then \
	  if ($(_DPZ_FORCE_BUILD) || ! docker inspect $(DPZ_DOCKER_FULL_IMAGE_NAME) > /dev/null 2> /dev/null); then \
	    if ! $(_DPZ_FORCE_BUILD) && $(DPZ_VERSION_SPECIFIED); then \
	      echo ; \
	      echo "Version was specified and image does not exist locally. Aborting" >&2; \
	      echo "Use DPZ_FORCE_BUILD=1 to override." >&2; \
	      echo ; \
	      exit 1; \
	    fi; \
	    echo Image does not exists in registry nor locally. It will be built now; \
	    $(MAKE) -f $(firstword $(MAKEFILE_LIST)) image.build.$* DPZ_VERSION=$(DPZ_VERSION); \
	  else \
	    echo Image exists locally but not in the registry. Only need to push it; \
	  fi; \
	  docker push $(DPZ_DOCKER_FULL_IMAGE_NAME); \
	else \
	  echo Image found in registry, good to go.; \
	fi

image.published.%: DPZ_COMPONENT=$*
image.published.%:
	@echo Checking for $(DPZ_DOCKER_FULL_IMAGE_NAME) in registry;\
	set -e; \
	if (! curl -k -f --head $(DPZ_DOCKER_CURL_BASIC_AUTH) https://$(DPZ_DOCKER_REGISTRY)/v2/$(DPZ_PROJECT)/$(DPZ_COMPONENT)/manifests/$(DPZ_VERSION) 2>/dev/null >/dev/null); \
	then \
	  echo ""; echo -e "    " $(DPZ_DOCKER_FULL_IMAGE_NAME) has not been published to registry.\\n "   " make image.publish.$(DPZ_COMPONENT) should be called first; echo ""; exit 1; \
	fi

image.tag.latest.%: DPZ_COMPONENT=$*
image.tag.latest.%: image.published.%
	docker pull $(DPZ_DOCKER_FULL_IMAGE_NAME)
	docker tag $(DPZ_DOCKER_FULL_IMAGE_NAME) $(DPZ_DOCKER_IMAGE_NAME):latest
	docker push $(DPZ_DOCKER_IMAGE_NAME):latest

.PHONY: image.publish.% image.build.%


# k8s deploy file parameterization

# Make sure tha the k8s-deploy.template file exists
#
$(DPZ_COMPONENT_PREFIX_DIR)/k8s-deploy.template:
	@echo ""; echo "     " Expected \"$@\" is not found, can not deploy image.; echo ""; exit 1

# Replace the docker image name with the one that has been built/published
#
k8s-deploy.%.yml: DPZ_COMPONENT=$*
k8s-deploy.%.yml: $(DPZ_COMPONENT_PREFIX_DIR)/k8s-deploy.template image.publish.% FORCE
	sed -e 's|DPZ_DOCKER_IMAGE|$(DPZ_DOCKER_FULL_IMAGE_NAME)|g' < $< > $@

.PHONY: k8s-deploy.%.yml FORCE
FORCE: ;

build_in_env.%: DEV_ENV=$(word 1,$(subst ., ,$*))
build_in_env.%: DPZ_COMPONENT=$(word 2,$(subst ., ,$*))
build_in_env.%:
	@[ "$(words $(subst ., ,$*))" = "2" ] || (echo "Pattern has too many pieces. Should be build_in_env.ENV.DPZ_COMPONENT was build_in_env.$*"; exit 1)
	@if [ "$(DPZ_DEV_ENV)" ]; then \
	  if [ $(DPZ_DEV_ENV) = "$(DEV_ENV)" ]; then \
	    make -f $(firstword $(MAKEFILE_LIST)) build_cmd.$(DPZ_COMPONENT); \
	  else \
	    echo "Actual and required environment ($(DPZ_DEV_ENV) != $(DEV_ENV))"; exit 1; \
	  fi; \
	else \
	  docker run --rm -v $$(pwd):$$(pwd) -w $$(pwd) $(DPZ_DOCKER_REGISTRY)/dev/$(DEV_ENV) make -f $(firstword $(MAKEFILE_LIST)) build_cmd.$(DPZ_COMPONENT); \
	fi

DPZ_SELF_DIR := $(dir $(lastword $(MAKEFILE_LIST)))
-include $(DPZ_SELF_DIR)/deployzor.scanning.mk
-include $(DPZ_SELF_DIR)/deployzor.packaging.mk
