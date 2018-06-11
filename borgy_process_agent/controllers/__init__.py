# -*- coding: utf-8 -*-
#
# __init__.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

import types
import sys
import glob
from os.path import dirname, basename, isfile

modules = glob.glob(dirname(__file__) + "/*.py")
__all__ = [basename(f)[:-3] for f in modules if isfile(f)]


def getfunctions(module):
    fcts = []
    for _, fct in module.__dict__.items():
        if isinstance(fct, types.FunctionType):
            fcts.append(fct)
    return fcts


# For all modules, replace function in borgy_process_agent_api_server.controllers.*
def overwrite_api_controllers():
    for m in __all__:
        if m != '__init__':
            module_fullname = __name__ + '.' + m
            flask_module = 'borgy_process_agent_api_server.controllers.' + m
            __import__(module_fullname)
            __import__(flask_module)
            for fct in getfunctions(sys.modules[module_fullname]):
                setattr(sys.modules[flask_module], fct.__name__, fct)
