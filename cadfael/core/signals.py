# coding: utf-8
# pylint: disable=W0621,C0103,R0903
from __future__ import unicode_literals, print_function


class Signal(object):
    """Simple signal mechanism to provide weak binding"""

    def __init__(self):
        """create a empty signal"""
        self.receivers = []

    def __call__(self, *args, **kwargs):
        """call all registered signal handlers for this signal"""
        retval = []
        for r in self.receivers:
            if r.filter(*args, **kwargs):
                retval.append((r.func, r.func(*args, **kwargs)))
        return retval


class receiver(object):
    """Decorator class to allow easy registration of signal handlers"""

    def __init__(self, signal, **kwargs):
        """create decorator object"""
        self.signal = signal
        self.kwargs = kwargs
        self.func = None
        signal.receivers.append(self)

    def filter(self, *args, **_):
        """filters the signal, allowing optional calling of receiver"""
        retval = True
        if len(args) < 1 or not isinstance(args[0], dict):
            if len(self.kwargs) > 0:
                raise ValueError('filtered receiver expects dict as first param')
        else:
            for k, v in self.kwargs.items():
                item = args[0]
                parts = k.split('__')
                for p in parts[:-1]:
                    item = item[p]
                k = parts[-1]
                if k not in item:
                    # this key isn't present
                    retval = False
                    break
                if isinstance(v, tuple):
                    # we have a list of options
                    if item[k] not in v:
                        # the value isn't present
                        retval = False
                        break
                elif item[k] != v:
                    # single value, but doens't match
                    retval = False
                    break
        return retval

    def __call__(self, func):
        self.func = func
        return func


#
# Define signals here, they are Signal object
#


# called once global arguments have been added to the parser
register_args = Signal()

# called after global arguments have been parsed, parses args object
parse_args = Signal()

# called when an inode is created; before added to the db
inode = Signal()
