# Borgy Process Agent

## Releases

Released packages are available on http://distrib.borgy.elementai.lan/python/borgy-process-agent/

## Build

The project uses deployzor to build and distrib the process agent.


To build pip package:
```
make
```

To simulate the distribution of the pip packages locally:
```
export DEPLOYZOR_DISTRIB_BASE=./distrib
make package.distrib.client package.distrib.server
```
