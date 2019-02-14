# k8s deploy targets
#
DPZ_DEPLOY_K8S_ENV_LABEL_default=
DPZ_DEPLOY_K8S_CPU_REQ_default=100m
DPZ_DEPLOY_K8S_MEM_REQ_default=1Gi
DPZ_DEPLOY_K8S_NAMESPACE_default=
DPZ_DEPLOY_K8S_DOMAIN_default=
DPZ_DEPLOY_K8S_DOMAIN_dev=borgy-dev
DPZ_DEPLOY_K8S_DOMAIN_prod=borgy

DPZ_DEPLOY_LIST_VARS_K8S_default?=CPU_REQ MEM_REQ NAMESPACE DOMAIN

dpz_value_for=$(if $($1_$2_$3),$($1_$2_$3),$(if $($1_$2),$($1_$2),$(if $($1_$3),$($1_$3),$(if $($1),$($1),$(if $($1_default),$($1_default),$(error $1 value can not be resolved))))))

# Make sure that the k8s-deploy.template file exists
#
$(DPZ_COMPONENT_PREFIX_DIR)/deploy.k8s.template:
	@echo ""; echo "     " Expected \"$@\" is not found, can not deploy image.; echo ""; exit 1

# Replace the docker image name with the one that has been built/published
#
_deploy.k8s.template.%.yml: DPZ_COMPONENT=$*
_deploy.k8s.template.%.yml: $(DPZ_COMPONENT_PREFIX_DIR)/deploy.k8s.template DPZ_FORCE
	@# DPZ_DEPLOY_ENV should have been set externally
	@! test -z "$(DPZ_DEPLOY_ENV)" || (echo DPZ_DEPLOY_ENV is not set; exit 1)
	sed $(foreach iVar,$(call dpz_value_for,DPZ_DEPLOY_LIST_VARS_K8S,$(DPZ_COMPONENT)),-e 's|DPZ_DEPLOY_$(iVar)|$(call dpz_value_for,DPZ_DEPLOY_K8S_$(iVar),$(DPZ_COMPONENT),$(DPZ_DEPLOY_ENV))|g') \
		-e 's|DPZ_DEPLOY_ENV_LABEL|$(DPZ_DEPLOY_ENV)|g' < $< > $@

# Deployment is expected to be found in the cluster
# Note: this should be the one used in drone - unless maybe we check with the previously deployed
# template.
_deploy.k8s.action.%: DPZ_COMPONENT=$*
_deploy.k8s.action.%: K8S_NAMESPACE=$(call dpz_value_for,DPZ_DEPLOY_K8S_NAMESPACE,$(DPZ_COMPONENT))
_deploy.k8s.action.%: _deploy.k8s.template.%.yml image.publish.%
	@! test -z "$(DPZ_DEPLOY_ENV)" || (echo DPZ_DEPLOY_ENV is not set; exit 1)
	@! test -z "$(K8S_NAMESPACE)" || (echo K8S_NAMESPACE is not set; exit 1)
	@# If the deployment exists and is annotated with a template checksum matching the current template, only
	@# the image will be updated. Otherwise, the whole thing will be applied (kubectl apply) after having set
	@# the image name. Upon successful deployment, the deployzor/template-md5 annotation is updated with the
	@# md5 of the image-agnostic template (pre-sed).
	@which md5sum > /dev/null || (echo md5sum is required for deployment rule; exit 1)
	@set -e; kind=$$(awk '/^kind: (Deployment|DaemonSet|StatefulSet)/ { if (k != "") { print "Template file has more than one kind: ",k,"vs",$$2 > "/dev/stderr"; k=""; exit 1; } k=$$2; } END { if (!k) { print "No deployable kind found" > "/dev/stderr"; exit 1; } print tolower(k); }' $<); \
	kubectl_cmd="kubectl --context k8s-$(DPZ_DEPLOY_ENV) -n $(K8S_NAMESPACE)"; \
	template_md5=$$(md5sum $< | awk '{print $$1'}); \
	stored_md5=$$($$kubectl_cmd get $$kind/$(DPZ_COMPONENT) -o jsonpath='{.metadata.annotations.deployzor/template-md5}' || echo ""); \
	if [ "$$template_md5" = "$$stored_md5" ]; \
	then \
	  echo "$$kind template md5 matches, will only update the image name"; \
	  $$kubectl_cmd set image $$kind/$(DPZ_COMPONENT) $(DPZ_COMPONENT)=$(DPZ_DOCKER_FULL_IMAGE_NAME) --record; \
	else \
	  echo "$$kind template md5 does not match: it either does not exist or is out of date: will apply all over"; \
	  if (! grep "DPZ_DEPLOY_DOCKER_IMAGE" $< > /dev/null 2> /dev/null); then echo $$kind template missing DPZ_DEPLOY_DOCKER_IMAGE; exit 1; fi; \
	  sed -e 's|DPZ_DEPLOY_DOCKER_IMAGE|$(DPZ_DOCKER_FULL_IMAGE_NAME)|g' < $< > $@.yml; \
	  $$kubectl_cmd apply -f $@.yml; \
	  $$kubectl_cmd annotate --overwrite $$kind $(DPZ_COMPONENT) deployzor/template-md5=$$template_md5; \
	fi; \
	if (! timeout --preserve-status -k 10 1800 $$kubectl_cmd rollout status $$kind/$(DPZ_COMPONENT)); then echo Deployment failed; exit 1; fi;
	@rm -f $@.yml
	@echo Deployment succeeded

# Main deployment target
#   Pattern: deploy.k8s.{prod,dev}.component
#   Re-entering in Makefile:
#
# Examples:
# > make deploy.k8s.dev.COMPONENT_NAME
# > make deploy.k8s.prod.COMPONENT_NAME
deploy.k8s.%: DPZ_DEPLOY_ENV=$(word 1,$(subst ., ,$*))
deploy.k8s.%: DPZ_COMPONENT=$(word 2,$(subst ., ,$*))
deploy.k8s.%:
	@! test -z "$(DPZ_DEPLOY_ENV)" || (echo DPZ_DEPLOY_ENV is not set; echo $(DPZ_DEPLOY_ENV); exit 1)
	@! test -z "$(DPZ_COMPONENT)" || (echo DPZ_COMPONENT is not set; exit 1)
	@test "$(DPZ_DEPLOY_ENV)" != "prod" || test "$(DPZ_RELEASE)" = "1" || (echo DPZ_RELEASE should be set to 1 to deploy in prod; exit 1)
	$(MAKE) -f $(firstword $(MAKEFILE_LIST)) DPZ_DEPLOY_ENV=$(DPZ_DEPLOY_ENV) _deploy.k8s.action.$(DPZ_COMPONENT)


# 1. Tags the tip of the default branch on origin with the prod + prod-$${short commit id}} tags
# 2. Before moving the prod tag, tags the previous prod tag with prod-prev
#
# Depending on DPZ_USE_COMPONENT_PREFIX, all prod tags below (prod, prod-prev and prod-$${short commit id}) will be
# suffixed with  "_$(DPZ_COMPONENT)" or not. In the case of a single-component repo (e.g. the borgy governor),
# there will not be a suffix appended to the tags as it is implicitly the governor.
#
# First, fetch all branches and tags from origin. This will get the current origin/$(DPZ_GIT_DEFAULT_BRANCH) branch,
# whatever the local version of the branch is. If the prod$${component_suffix} tag is already at
# origin/$(DPZ_GIT_DEFAULT_BRANCH) there is nothing to do. Otherwise, tag the origin/$(DPZ_GIT_DEFAULT_BRANCH) as the
# new versioned prod (prod-$${short commit id}$${component_suffix}, move the prod-prev${{componen_suffix}} tag to
# prod$${component_suffix}}, the prod$${component_suffix} tag to origin/$(DPZ_GIT_DEFAULT_BRANCH) and force push
# the updated prod$${component_suffix}, prod-prev$${component_suffix} and prod-$${short commit id}$${component_suffix}
# tags to origin.
#
# To perform the actual deployment, the CI must watch the prod_$(DPZ_COMPONENT) and take action accordingly.
# To manually perform a deployment use the above deploy.k8s.% rule above
#
git.tag.prod.tip.%: DPZ_COMPONENT=$*
git.tag.prod.tip.%:
	@git fetch --tags origin
	@set -e; component_suffix=$(if $(findstring 1,$(DPZ_USE_COMPONENT_PREFIX)),_$(DPZ_COMPONENT)); \
	prod_tag=prod$${component_suffix}; \
	prev_tag=prod-prev$${component_suffix}; \
	origin_branch=origin/$(DPZ_GIT_DEFAULT_BRANCH); \
	origin_commit=`git rev-list -n 1 $${origin_branch} 2> /dev/null` || (echo "$${origin_branch} branch not found in origin"; exit 1); \
	prod_commit=`git rev-list -n 1 $${prod_tag} 2> /dev/null` || echo "$${prod_tag} was never set. Will create"; \
	if [ "$${origin_commit}" = "$${prod_commit}" ];\
	then \
	  echo $${prod_tag} already at tip of $${origin_branch}, nothing to do; \
	  exit;  \
	else \
	  commit_sha1=`git rev-parse --short $${origin_branch}`; \
	  sha1_tag=prod-$${commit_sha1}$${component_suffix}; \
	  git tag -f $${sha1_tag} $${origin_branch}; \
	  [ -z "$${prod_commit}" ] || git tag -f $${prev_tag} $${prod_tag}; \
	  git tag -f $${prod_tag} $${origin_branch}; \
	  git push -f origin refs/tags/$${sha1_tag} refs/tags/$${prod_tag}; \
	  [ -z "$${prod_commit}" ] || git push -f origin refs/tags/$${prev_tag}; \
	  echo $${origin_branch} version tagged as prod for $(DPZ_COMPONENT); \
	fi

define dpz_undefined_rule
$(1):
	@echo $$@ is undefined. $(2)
	exit 1
endef

$(if $(DPZ_COMPONENT),$(eval git.tag.prod.tip: git.tag.prod.tip.$(DPZ_COMPONENT) ;),$(eval $(call dpz_undefined_rule,git.tag.prod.tip,DPZ_COMPONENT needs to be set at inclusion time to have this default target)))

# 1. Tags the prod-$(VERSION)$${component_suffix} with the prod-$(VERSION)$${component}
# 2. Tags the prod$${component_suffix} with prod-prev$${component_suffix}
#
# This selects an already tagged production version
#
git.tag.prod.version.%: VERSION=$(word 1,$(subst ., ,$*))
git.tag.prod.version.%: DPZ_COMPONENT=$(word 2,$(subst ., ,$*))
git.tag.prod.version.%:
	@git fetch --tags origin
	@set -e; component_suffix=$(if $(findstring 1,$(DPZ_USE_COMPONENT_PREFIX)),_$(DPZ_COMPONENT)); \
	prod_tag=prod$${component_suffix}; \
	version_tag=prod-$(VERSION)$${component_suffix}; \
	prev_tag=prod-prev$${component_suffix}; \
	version_commit=`git rev-list -n 1 $${version_tag} 2> /dev/null` || (echo "tag not found: $${version_tag}"; exit 1); \
	prod_commit=`git rev-list -n 1 $${prod_tag} 2> /dev/null` || (echo "tag not found: $${prod_tag}"; exit 1); \
	if [ "$${version_commit}" = "$${prod_commit}" ];\
	then \
	  echo prod version for $(DPZ_COMPONENT) is already $(VERSION); \
	  exit; \
	else \
	  git tag -f $${prev_tag} $${prod_commit}; \
	  git tag -f $${prod_tag} $${version_commit}; \
	  git push -f origin refs/tags/$${prev_tag} refs/tags/$${prod_tag}; \
	  echo prod version $(VERSION) selected for $(DPZ_COMPONENT); \
	fi

# Shortcut rule to select the "prev" version in the rule above
#
git.tag.prod.revert.%: DPZ_COMPONENT=$*
git.tag.prod.revert.%: git.tag.prod.version.prev.% ;

$(if $(DPZ_COMPONENT),$(eval git.tag.prod.revert: git.tag.prod.version.prev.$(DPZ_COMPONENT) ;),$(eval $(call dpz_undefined_rule,git.tag.prod.revert,DPZ_COMPONENT needs to be set at inclusion time to have this default target)))

