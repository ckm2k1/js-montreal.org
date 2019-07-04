# Copyright 2019 ElementAI. All rights reserved.
#
# Metric utilities.


def type_name(instance):
    """
    Return the fully qualified name of the type for the passed instance.
    For example: `werkzeug.exceptions.NotFound`
    """
    module = ""
    if hasattr(instance, "__module__"):
        module = instance.__module__ + "."

    tpe = type(instance)
    if hasattr(tpe, "__qualname__"):
        return module + tpe.__qualname__
    elif hasattr(tpe, "__name__"):
        return module + tpe.__name__
    else:
        return str(tpe)


def sanitize_exception_message(exception):
    """
    Sanitize exception messages by removing linefeed characters
    and cleaning up whitespace characters.
    """
    message = str(exception).split()
    return " ".join(message)[:100]
