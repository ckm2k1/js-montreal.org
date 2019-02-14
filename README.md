# Deployzor

Versionning/Docker Image Building/Deployment make utility.

## Usage Overview

`deployzor.mk` is typically included from a project-specific Makefile.

A project can be composed of one component (See [ElementAI/borgy-governor](https://github.com/ElementAI/borgy-governor)) or more (See [ElementAI/borgy](https://github.com/ElementAI/borgy)).

The makefile targets are applied on one component at time, and that component name is stored in the `DPZ_COMPONENT` variable.

A few make variables will influence (i.e. parameterize) the behavior of this utility. These variables are:

<dl>
  <dt>DPZ_PROJECT</dt>
  <dd>This variable MUST be non-empty otherwise the inclusion will fail. It is used as a namespace in the synthesized docker image name.</dd>

  <dt>DPZ_RELEASE</dt>
  <dd>If set to 1, define the release state. Default: <code>empty, thus false</code></dd>

  <dt>DPZ_DOCKER_REGISTRY_PROD</dt>
  <dd>Registry part of the synthesized docker image name for production. Default: <code>images.borgy.elementai.net</code></dd>

  <dt>DPZ_DOCKER_REGISTRY_VOLATILE</dt>
  <dd>Registry part of the synthesized docker image name for testing. Default: <code>volatile-images.borgy.elementai.net</code></dd>

  <dt>DPZ_DOCKER_REGISTRY</dt>
  <dd>Depending on DPZ_RELEASE value, the registry will be set to DPZ_DOCKER_REGISTRY_PROD when DPZ_RELEASE=1 else to DPZ_DOCKER_REGISTRY_VOLATILE. Default: <code>$DPZ_DOCKER_REGISTRY_VOLATILE</code></dd>

  <dt>DPZ_BASE_PATH</dt>
  <dd>All files (e.g. Dockerfile, templates, etc.) will be searched for starting in this directory. Default: empty, which is interpreted as the current working directory.</dd>

  <dt>DPZ_USE_COMPONENT_PREFIX</dt>
  <dd>If set to 1, all files (e.g. Dockerfile, templates, etc.) will be searched for inside the DPZ_COMPONENT subdirectory. This is especially useful if a source directory contains multiple components, each with their Dockerfile. Default: empty, thus false</dd>

  <dt>DPZ_ENABLE_BUILD_DEPENDENCY</dt>
  <dd>If set to 1, a build.[component] dependency is added to image.build.[component]. This allows the user to add a step (e.g. compilation, static page generation) before building the docker image. Default: empty, thus no dependency to build image.</dd>

  <dt>DPZ_GLOBAL_DOCKER_CONTEXT</dt>
  <dd>If set to 1, the docker context will be the root of the repo instead of the component directory. Useful if there are some files to add to the docker image which are not the component directory. Default: empty, thus docker context is the component subdirectory alone.</dd>
</dl>

### Multi-Component Example: borgy main repository

The main borgy repository is where many small services required for the system ended up. Here are the first few lines of the repository [Makefile](https://github.com/ElementAI/borgy/blob/master/Makefile):

```makefile
DPZ_PROJECT=borgy
DPZ_BASE_PATH=services
DPZ_USE_COMPONENT_PREFIX=1
include deployzor.mk

[...]
```

Which describes the following directory structure for 3 components, `borsh`, `dockerintrospectd` and `gpu-overview`, each with their `Dockerfile`. (This is not exhaustive)

```
.
├── README.md
├── deployzor.mk
├── Makefile
├── README.md
└── services
    ├── borsh
    │   └── Dockerfile
    ├── dockerintrospectd
    │   ├── Dockerfile
    │   ├── k8s-deploy.template
    │   └── src
    │       ├── dockerintrospectd.py
    │       └── requirements.txt
    └── gpu-overview
        ├── Dockerfile
        ├── html
        │   └── gpu-overview
        │       ├── gpu_servers_template_fu.py
        │       ├── index.html
        │       ├── jquery-3.2.1.min.js
        │       ├── plotly-latest.min.js
        │       └── vue.js
        └── k8s-deploy.template
```

### Single-Component Example: borgy-governor

The borgy governor is a single-component repository. Here are the first few lines of the repository [Makefile](https://github.com/ElementAI/borgy-governor/blob/master/Makefile):

```makefile
DPZ_PROJECT=borgy
include deployzor.mk

[...]
```

Which describes the following directory structure for a single component, without a `DPZ_BASE_PATH` which requires the `Dockerfile` and `k8s-deploy.template` to be in the root of the repo. (This is not exhaustive)

```
.
├── Dockerfile
├── docker_version.mk
├── governor
│   ├── dockerintrospectd_client.py
│   ├── __init__.py
│   ├── jsv.py
│   ├── k8s.py
│   ├── run.py
│   ├── setup.py
│   ├── uidmap_client.py
│   └── utils.py
├── k8s-deploy.template
├── Makefile
└── README.md
```

## Detailed Features

### Version Synthesis

The `DPZ_VERSION` variable can be set explicitly when invoking make. If unset, it will be synthesized according to the state of the repo.

* If clean, the short git hash is used as the `DPZ_VERSION`
* If not, a more detailed state description is used, i.e. username-githash-branch-timestamp

Notes:
* if the source tree is NOT clean, the `DPZ_VERSION` will change between invocations. It is likely that you will want to set the `DPZ_VERSION` explicitly (e.g. `make DPZ_VERSION=XXX ...`)

### Docker Related

Multiple targets and variable are available when using this makefile.

The Dockerfile used to build the image is the sum of the following:
* `DPZ_BASE_PATH` if non-empty
* `DPZ_COMPONENT` if `DPZ_USE_COMPONENT_PREFIX` is 1
* `Dockerfile`

The docker image name is: `DPZ_DOCKER_REGISTRY/DPZ_PROJECT/DPZ_COMPONENT:DPZ_VERSION` and is available as `DPZ_DOCKER_FULL_IMAGE_NAME` variable.

Example image name: `images.borgy.elementai.net/borgy/governor:jean-BM-227_get_gpuid-ef12918-20170912155052`

The version-less image name is available as `DPZ_DOCKER_IMAGE_NAME` variable.

#### Supported Targets

* `image.build.[component]`
    * Builds the image locally

* `image.publish.[component]`
    * First checks if the image exists in the registry. If so, stops
    * If it's been built locally, pushes it to the registry, then stops
    * Else, builds the image and pushes it to the registry

* `image.tag.latest.[component]`
    * First makes sure that the image is already published in the registry
    * Pulls the image locally (in case it was not built locally e.g. by drone)
    * Tags the published image with `latest` version
    * Pushes the tagged image in registry

* `image.run.[component]`
    * Builds image according to repo status
    * Runs given command in DPZ_CMD variable in image. The DPZ_CMD can be specified at the command line like in `make image.run.component_name DPZ_CMD='env'` or through extra Makefile rules.

* `image.run_volatile.[component]`
    * Builds image according to repo status
    * Runs given command in DPZ_CMD catching the return code
    * Deletes image
    * Exit with the previously catched return code

* `image.delete.[component]`
    * Deletes image

### K8S template target

*This is work in progress and is likely to change.*

Services that are deployed in kubernetes use a docker image name to start the appropriate container. This is often the only thing that changes from one deployment to the next. There is a facility to generate the deployment file from a template.

The target to do this is:

* `k8s-deploy.[component].yml`
    * Makes sure that a k8s-deploy.template file is found in the component directory (same location as the Dockerfile)
    * Makes sure the component's docker image is published
    * replaces the `DPZ_DOCKER_IMAGE` placeholder in the k8s-deploy.template file and saves in the in the current working directory under k8s-deploy.[component].yml

## Example Use Cases

### Publish an image based on the current state of the workspace

    make image.publish.[component]

### Publish a specific version of an image which exists locally

    make image.publish.[component] DPZ_VERSION=[version_string]

In this case, if the image is not found locally nor in the registry, it will not be built and the target will fail. (this allows use in a deploy make target)

### Force Build and publish an image with a specific version (to overwrite an image in the registry)

    make image.publish.[component] DPZ_FORCE_BUILD=1 DPZ_VERSION=[version_string]

### Build a temporary image, run a command in it and delete the image

    make image.volatile_run.[component] DPZ_CMD='command to run in container'`

### Use in an including makefile

The following can be used to build a makefile rule for a specific image/cmd:

    BANANE_CMD=/bin/bash -c "cd /something; python ./script.py"
    image.volatile_run.banane: DPZ_CMD=$(BANANE_CMD)

Then, at the command line:

    make image.volatile_run.banane

### Build an image and run a command in it

    make image.run.[pattern] DPZ_CMD='quoted command to run'

Rules can be built like for the image.volatile_run.[pattern] target.

### Build, publish and generate deployment file

    make k8s-deploy.[pattern].yml

## Pedantic Notes

* It is possible not to include `deployzor.mk` and use it as is as long as there is a Dockerfile in the current directory
     `make DPZ_PROJECT=my_project -f deployzor.mk image.build.xxx`
* As long as DPZ_USE_COMPONENT_PREFIX contains a 1, it is considered to be set


