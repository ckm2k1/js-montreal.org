# Copyright (c) 2017 ElementAI. All rights reserved.
#
# Get usage notes at github.com/ElementAI/eai-deployzor

# Parameters to configure behavior before inclusion:
#
# DEPLOYZOR_PROJECT: (MANDATORY)
#   Used as a namespace in the Docker image name.

$(if $(DEPLOYZOR_PROJECT),,$(error DEPLOYZOR_PROJECT should be set before including $(lastword $(MAKEFILE_LIST))))
#
# DEPLOYZOR_BASE_PATH:
#   Path from where the components files will be searched from. (default: empty, thus current directory)
DEPLOYZOR_BASE_PATH?=.
#
# DEPLOYZOR_USE_COMPONENT_PREFIX:
#   Should be set to "1" if more than one component are to be built and maybe deployed
#   from the same repo. If set, the component Dockerfile and k8s-deploy.template will
#   be found in the $(COMPONENT)/ subdirectory under $(DEPLOYZOR_COMPONENTS_ROOT). If not,
#   both the Dockerfile and k8s-deploy.template will be found in the $(DEPLOYZOR_COMPONENTS_ROOT)
#   directory. (default: unset, thus false)

COMPONENT_PREFIX_DIR=$(DEPLOYZOR_BASE_PATH)$(if $(findstring 1,$(DEPLOYZOR_USE_COMPONENT_PREFIX)),/%)

_DEPLOYZOR_RELEASE:=$(if $(findstring 1,$(DEPLOYZOR_DEPLOYZOR_RELEASE)),true,false)

# Version synthesis
#
_VERSION_TAG_LAST=$(shell git tag --sort=-version:refname -l '[0-9]*.*'|head -n 1)
VERSION_TAG_LAST:=$(if $(_VERSION_TAG_LAST),$(_VERSION_TAG_LAST),0.0.1)
VERSION_COMMIT=$(shell git rev-parse --short HEAD)
VERSION_TAG=$(shell git describe --exact-match --tags $(VERSION_COMMIT) 2> /dev/null)
VERSION:=$(if $(VERSION),$(VERSION),$(_VERSION))
_VERSION ?= $(shell \
	if [ -z "`git status --porcelain`" ]; then \
		if echo $(VERSION_TAG) | grep -qE "([0-9]+\.){2}[0-9]+\w*"; then \
			echo $(VERSION_TAG); \
		else \
			echo $(VERSION_COMMIT); \
		fi \
	else \
	    echo `whoami`-`git rev-parse --abbrev-ref HEAD`-`git rev-parse --short HEAD`-`date +%Y%m%d%H%M%S`; \
	fi)
VERSION_SPECIFIED:=$(if $(VERSION),true,false)
VERSION:=$(if $(VERSION),$(VERSION),$(_VERSION))

# Image naming and building
#
DEPLOYZOR_DOCKER_REGISTRY?=images.borgy.elementai.lan
COMPONENT?=
DEPLOYZOR_DISTRIB_BASE?=./distrib
DEPLOYZOR_DISTRIB_PACKAGE?=$(DEPLOYZOR_DISTRIB_BASE)/$(DEPLOYZOR_PROJECT)-$(COMPONENT)
DOCKER_IMAGE_NAME?=$(DEPLOYZOR_DOCKER_REGISTRY)/$(DEPLOYZOR_PROJECT)/$(COMPONENT)
DOCKER_FULL_IMAGE_NAME?=$(DEPLOYZOR_DOCKER_REGISTRY)/$(DEPLOYZOR_PROJECT)/$(COMPONENT):$(VERSION)
_FORCE_BUILD:=$(if $(findstring 1,$(FORCE_BUILD)),true,false)

# Package naming
#
DEPLOYZOR_PACKAGE_EXT?=tar.gz
DEPLOYZOR_PACKAGE_NAME?=$(DEPLOYZOR_PROJECT)-$(COMPONENT)-$(VERSION).$(DEPLOYZOR_PACKAGE_EXT)
DEPLOYZOR_PACKAGE_PATH?=$(DEPLOYZOR_DISTRIB_PACKAGE)/$(DEPLOYZOR_PACKAGE_NAME)

# This makes sure that the required Dockerfile exists
#
$(COMPONENT_PREFIX_DIR)/Dockerfile:
	@echo ""; echo "     " Expected \"$@\" is not found, can not build image.; echo ""; exit 1

# Generic docker build target
# `make image.build.foo` builds a docker based on the foo/Dockerfile file.
#
image.build.%: COMPONENT=$*
image.build.%: $(COMPONENT_PREFIX_DIR)/Dockerfile $(if $(findstring 1,$(DEPLOYZOR_ENABLE_BUILD_DEPENDENCY)),build.%)
	docker build --build-arg version=$(VERSION) -f $< -t $(DOCKER_FULL_IMAGE_NAME) $(if $(findstring 1,$(DEPLOYZOR_GLOBAL_DOCKER_CONTEXT)),.,$(<D))

image.run.%: COMPONENT=$*
image.run.%: image.build.%
	docker run --rm $(DOCKER_FULL_IMAGE_NAME) $(CMD)

image.delete.%: COMPONENT=$*
image.delete.%:
	docker rmi $(DOCKER_FULL_IMAGE_NAME)

image.volatile_run.%: COMPONENT=$*
image.volatile_run.%:
	rc=0; \
	  make image.run.$* VERSION=$(VERSION) \
	    CMD='$(CMD)' || rc=$$?; \
	  make image.delete.$* VERSION=$(VERSION)>/dev/null; exit $$rc;

image.publish.%: COMPONENT=$*
image.publish.%:
	@echo Checking for $(DOCKER_FULL_IMAGE_NAME) in registry;\
	set -e; \
	if ($(_FORCE_BUILD) || ! curl -k -f --head https://$(DEPLOYZOR_DOCKER_REGISTRY)/v2/$(DEPLOYZOR_PROJECT)/$(COMPONENT)/manifests/$(VERSION) 2>/dev/null >/dev/null); \
	then \
	  if ($(_FORCE_BUILD) || ! docker inspect $(DOCKER_FULL_IMAGE_NAME) > /dev/null 2> /dev/null); then \
	    if ! $(_FORCE_BUILD) && $(VERSION_SPECIFIED); then \
	      echo ; \
	      echo "Version was specified and image does not exist locally. Aborting" >&2; \
	      echo "Use FORCE_BUILD=1 to override." >&2; \
	      echo ; \
	      exit 1; \
	    fi; \
	    echo Image does not exists in registry nor locally. It will be built now; \
	    $(MAKE) -f $(firstword $(MAKEFILE_LIST)) image.build.$* VERSION=$(VERSION); \
	  else \
	    echo Image exists locally but not in the registry. Only need to push it; \
	  fi; \
	  docker push $(DOCKER_FULL_IMAGE_NAME); \
	else \
	  echo Image found in registry, good to go.; \
	fi

image.latest.%: COMPONENT=$*
image.latest.%: image.publish.%
	docker tag $(DOCKER_FULL_IMAGE_NAME) $(DOCKER_IMAGE_NAME):latest
	docker push $(DOCKER_IMAGE_NAME):latest

.PHONY: image.publish.% image.build.%

# k8s deploy file parameterization

# Make sure tha the k8s-deploy.template file exists
#
$(COMPONENT_PREFIX_DIR)/k8s-deploy.template:
	@echo ""; echo "     " Expected \"$@\" is not found, can not deploy image.; echo ""; exit 1

# Replace the docker image name with the one that has been built/published
#
k8s-deploy.%.yml: COMPONENT=$*
k8s-deploy.%.yml: $(COMPONENT_PREFIX_DIR)/k8s-deploy.template image.publish.% FORCE
	@if [ -f $(COMPONENT_PREFIX_DIR)/k8s-deploy-$(ENV).configmap ]; \
	then \
		echo "Cat configmap in $@"; \
		cat $(COMPONENT_PREFIX_DIR)/k8s-deploy-$(ENV).configmap $< | sed -e 's|DOCKER_IMAGE|$(DOCKER_FULL_IMAGE_NAME)|g' > $@ ; \
	else \
		sed -e 's|DOCKER_IMAGE|$(DOCKER_FULL_IMAGE_NAME)|g' < $< > $@; \
	fi


.PHONY: k8s-deploy.%.yml FORCE
FORCE: ;


# Get package filename
# `make package.filename.foo`
#
package.filename.%: COMPONENT=$*
package.filename.%:
	@echo $(DEPLOYZOR_PACKAGE_NAME)


# Generic package distribution for latest version
# `make package.distrib.foo.latest`
#
package.distrib.%.latest: COMPONENT=$*
package.distrib.%.latest:
	@if $(_DEPLOYZOR_RELEASE) && [ "$(VERSION_TAG)" = "" ] ; then \
		echo ; \
		echo "Release flag is set but no tag was found for the commit $(VERSION_COMMIT)" >&2; \
		echo ; \
		exit 1; \
	fi; \
	$(eval TAG=$(shell git show-ref --tags -d | grep $(shell git show-ref --tags -d | grep $(VERSION) | cut -d ' ' -f 1) | grep -v $(VERSION) | cut -d ' ' -f 2 | sed -e 's|refs/tags/||g'))
	@test -n "$(TAG)" || ( echo no version tag at $(VERSION); exit 1 )
	$(eval FILE=$(shell make VERSION=$(TAG) package.distrib.$*.path))
	test -e $(FILE)
	rm -f $(DEPLOYZOR_PACKAGE_PATH) || true
	ln -sr $(FILE) $(DEPLOYZOR_PACKAGE_PATH)


# Get package distrib path
# `make package.distrib.foo.path`
#
package.distrib.%.path: COMPONENT=$*
package.distrib.%.path:
	@echo $(DEPLOYZOR_PACKAGE_PATH)

# Generic clean package and extraction
# `make package.clean.foo` clean package file and extraction
#
package.clean.%: COMPONENT=$*

# Generic package builder
# `make package.build.foo` build package file
#
package.build.%: COMPONENT=$*
package.build.%: package.clean.%


# Generic package distribution
# `make package.distrib.foo` distrib package file
#
package.distrib.%: COMPONENT=$*
package.distrib.%:
	@if $(_DEPLOYZOR_RELEASE) && [ "$(VERSION_TAG)" = "" ] ; then \
		echo ; \
		echo "Release flag is set but no tag was found for the commit $(VERSION_COMMIT)" >&2; \
		echo ; \
		exit 1; \
	fi; \
	mkdir -p $(DEPLOYZOR_DISTRIB_PACKAGE)
	mv $(DEPLOYZOR_PACKAGE_NAME) $(DEPLOYZOR_PACKAGE_PATH)

# Generic package extraction
# `make package.extract.foo` extract package file
#
package.extract.%: COMPONENT=$*
package.extract.%: package.build.%
	@if [ "$(DEPLOYZOR_PACKAGE_EXT)" = "zip" ]; then\
		unzip $(DEPLOYZOR_PACKAGE_NAME); \
	elif [ "$(DEPLOYZOR_PACKAGE_EXT)" = "rar" ]; then\
		unrar e $(DEPLOYZOR_PACKAGE_NAME); \
	else \
		tar xvf $(DEPLOYZOR_PACKAGE_NAME); \
	fi
	echo Extracted

.PHONY: package.filename.% package.clean.% package.build.% package.extract.% package.distrib.%
