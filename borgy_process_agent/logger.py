import time
import logging
import inspect
from typing import List, Callable, Union, Type, Tuple
from functools import wraps
from pprint import pformat

logger = None


def cls_methods(subject) -> List[Tuple[str, Callable]]:
    methods = [
        (name, obj)
        for name, kind, cls, obj in inspect.classify_class_attrs(subject)
        if kind == 'method' and cls == subject
    ] # yapf: disable
    return methods


def fmt(obj):
    return pformat(obj, 4, 80)


def wrap_callable(obj: Callable) -> Callable:

    @wraps(obj)
    def wrapper(*args, **kwargs):
        logger.debug(f'{obj.__name__} -- STARTED -- POS: {fmt(args)} KW: {fmt(kwargs)}')

        t = time.time()
        res = obj(*args, **kwargs)
        delta = time.time() - t
        delta = delta if delta >= 1 else round(delta * 1000, 4)

        logger.debug(f'{obj.__name__} -- FINISHED -- retval: {fmt(res)} -- {delta}ms')
        return res

    return wrapper


def func_logger(obj: Union[Callable, Type]) -> Union[Callable, Type]:
    """Logging decorator for dumping out
    function calls and their arguments.
    """
    if inspect.isclass(obj):
        methods = cls_methods(obj)
        for name, meth in methods:
            setattr(obj, name, wrap_callable(meth))
        return obj

    return wrap_callable(obj)


def configure(debug=False):
    global logger
    logging.basicConfig(format='[%(asctime)-15s] -- %(threadName)s: %(message)s',
                        datefmt='%m/%d/%Y %H:%M:%S',
                        level=logging.DEBUG if debug else logging.INFO)
    logger = logging.getLogger('main')
    return logger
