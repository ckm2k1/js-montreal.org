# -*- coding: utf-8 -*-
#
# version_controller.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

import pkg_resources
from borgy_process_agent_api_server.models.version import Version  # noqa: E501

borgy_process_agent_version = pkg_resources.get_distribution('borgy_process_agent').version


def v1_version_get():  # noqa: E501
    """Return the process agent version

     # noqa: E501


    :rtype: Version
    """
    return Version.from_dict({
        'version': borgy_process_agent_version
    })
