###############################################
#
#  Python packaging facility
#
#  Note. This is included from deployzor.mk and relies on targets and variables defined
#  therein. It can not be used on its own.
#
_DEPLOYZOR_RELEASE:=$(if $(findstring 1,$(DEPLOYZOR_RELEASE)),true,false)

DEPLOYZOR_DISTRIB_BASE?=./distrib
DEPLOYZOR_DISTRIB_PACKAGE?=$(DEPLOYZOR_DISTRIB_BASE)/$(DEPLOYZOR_PROJECT)-$(COMPONENT)
# Package naming
#
DEPLOYZOR_PACKAGE_EXT?=tar.gz
DEPLOYZOR_PACKAGE_NAME?=$(DEPLOYZOR_PROJECT)-$(COMPONENT)-$(VERSION).$(DEPLOYZOR_PACKAGE_EXT)
DEPLOYZOR_PACKAGE_PATH?=$(DEPLOYZOR_DISTRIB_PACKAGE)/$(DEPLOYZOR_PACKAGE_NAME)

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
