###############################################
#
#  Python packaging facility
#
#  Note. This is included from deployzor.mk and relies on targets and variables defined
#  therein. It can not be used on its own.
#
_DPZ_RELEASE:=$(if $(findstring 1,$(DPZ_RELEASE)),true,false)

DPZ_DISTRIB_BASE?=./distrib
DPZ_DISTRIB_PACKAGE?=$(DPZ_DISTRIB_BASE)/$(DPZ_PROJECT)-$(DPZ_COMPONENT)
# Package naming
#
DPZ_PACKAGE_EXT?=tar.gz
DPZ_PACKAGE_NAME?=$(DPZ_PROJECT)-$(DPZ_COMPONENT)-$(DPZ_VERSION).$(DPZ_PACKAGE_EXT)
DPZ_PACKAGE_PATH?=$(DPZ_DISTRIB_PACKAGE)/$(DPZ_PACKAGE_NAME)

# Get package filename
# `make package.filename.foo`
#
package.filename.%: DPZ_COMPONENT=$*
package.filename.%:
	@echo $(DPZ_PACKAGE_NAME)


# Generic package distribution for latest version
# `make package.distrib.foo.latest`
#
package.distrib.%.latest: DPZ_COMPONENT=$*
package.distrib.%.latest:
	@if $(_DPZ_RELEASE) && [ "$(DPZ_VERSION_TAG)" = "" ] ; then \
		echo ; \
		echo "Release flag is set but no tag was found for the commit $(DPZ_VERSION_COMMIT)" >&2; \
		echo ; \
		exit 1; \
	fi; \
	$(eval TAG=$(shell git show-ref --tags -d | grep $(shell git show-ref --tags -d | grep $(DPZ_VERSION) | cut -d ' ' -f 1) | grep -v $(DPZ_VERSION) | cut -d ' ' -f 2 | sed -e 's|refs/tags/||g'))
	@test -n "$(TAG)" || ( echo no version tag at $(DPZ_VERSION); exit 1 )
	$(eval FILE=$(shell make DPZ_VERSION=$(TAG) package.distrib.$*.path))
	test -e $(FILE)
	rm -f $(DPZ_PACKAGE_PATH) || true
	ln -sr $(FILE) $(DPZ_PACKAGE_PATH)


# Get package distrib path
# `make package.distrib.foo.path`
#
package.distrib.%.path: DPZ_COMPONENT=$*
package.distrib.%.path:
	@echo $(DPZ_PACKAGE_PATH)

# Generic clean package and extraction
# `make package.clean.foo` clean package file and extraction
#
package.clean.%: DPZ_COMPONENT=$*

# Generic package builder
# `make package.build.foo` build package file
#
package.build.%: DPZ_COMPONENT=$*
package.build.%: package.clean.%


# Generic package distribution
# `make package.distrib.foo` distrib package file
#
package.distrib.%: DPZ_COMPONENT=$*
package.distrib.%:
	@if $(_DPZ_RELEASE) && [ "$(DPZ_VERSION_TAG)" = "" ] ; then \
		echo ; \
		echo "Release flag is set but no tag was found for the commit $(DPZ_VERSION_COMMIT)" >&2; \
		echo ; \
		exit 1; \
	fi; \
	mkdir -p $(DPZ_DISTRIB_PACKAGE)
	mv $(DPZ_PACKAGE_NAME) $(DPZ_PACKAGE_PATH)

# Generic package extraction
# `make package.extract.foo` extract package file
#
package.extract.%: DPZ_COMPONENT=$*
package.extract.%: package.build.%
	@if [ "$(DPZ_PACKAGE_EXT)" = "zip" ]; then\
		unzip $(DPZ_PACKAGE_NAME); \
	elif [ "$(DPZ_PACKAGE_EXT)" = "rar" ]; then\
		unrar e $(DPZ_PACKAGE_NAME); \
	else \
		tar xvf $(DPZ_PACKAGE_NAME); \
	fi
	echo Extracted

.PHONY: package.filename.% package.clean.% package.build.% package.extract.% package.distrib.%
