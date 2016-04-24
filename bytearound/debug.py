__doc__ = """

Helpers for debugging and testing code objects.

"""

import contextlib
import difflib
import dis
import sys
import types

from . import code_object
from . import parser


_code_object_attributes = sorted(attr for attr in dir(types.CodeType) if not attr.startswith('_'))


def check_recursive(obj, seen=None):
    """Recursively checks a Python object."""
    if seen is None:
        seen = set()
    try:
        if obj in seen:
            return
        seen.add(obj)
    except TypeError:
        return  # non-hashable types are not interesting
    if isinstance(obj, types.CodeType):
        try:
            check(obj)
        except AssertionError as e:
            # TODO figure out if we can fix each minor incompatibility, for now just print
            print 'failed on %s: %s' % (obj, e)
        for constant in obj.co_consts:
            check_recursive(constant, seen=seen)
    else:
        if hasattr(obj, '__dict__'):
            for val in obj.__dict__.itervalues():
                check_recursive(val, seen=seen)
        for attr in ('im_func', 'func_code'):
            try:
                val = getattr(obj, attr)
            except AttributeError:
                pass
            else:
                check_recursive(val, seen=seen)


def check(co):
    """Checks that running ByteAround on the given code object does not change it."""
    if hasattr(co, 'func_code'):
        co = co.func_code
    assert compare_code_objects(co, code_object.ByteAround.from_code(co).to_code(pessimize=True)), \
        'check failed for %s' % co


def display_code_object(co):
    for attr in _code_object_attributes:
        if attr != 'co_code':
            print attr, repr(getattr(co, attr))
    dis.dis(co)


def compare_code_objects(co1, co2):
    """Compare two code objects for equality, printing out any differences."""
    not_equal = set()
    for attr in _code_object_attributes:
        value1 = getattr(co1, attr)
        value2 = getattr(co2, attr)
        if value1 != value2:
            print('%s is not equal' % attr)
            not_equal.add(attr)
            # maybe do something special for co_lnotab too
            if attr == 'co_code':
                disassembled1 = _disassemble_to_string(co1).splitlines()
                disassembled2 = _disassemble_to_string(co2).splitlines()
                diff = difflib.unified_diff(disassembled1, disassembled2)
                print(''.join(line + '\n' for line in diff))
            elif attr == 'co_lnotab':
                disassembled1 = map(str, parser.get_offsets_from_lnotab(value1))
                disassembled2 = map(str, parser.get_offsets_from_lnotab(value2))
                diff = difflib.unified_diff(disassembled1, disassembled2)
                print(''.join(line + '\n' for line in diff))
            else:
                print('%r != %r' % (value1, value2))

    return len(not_equal) == 0


def _disassemble_to_string(co):
    """Disassembles a code object using the dis module, saving the result in a string."""
    with _capture_stdout() as f:
        dis.dis(co)
    return f.read()


@contextlib.contextmanager
def _capture_stdout():
    """Context that captures data printed to stdout within it.

    Usage:

    with _capture_stdout() as f:
        print 'hello'

    output = f.read()  # "hello\n"

    """
    capturer = _Capturer()
    old_stdout = sys.stdout
    sys.stdout = capturer
    try:
        yield capturer
    finally:
        sys.stdout = old_stdout


class _Capturer(object):
    def __init__(self):
        self.data = []

    def write(self, line):
        self.data.append(line)

    def read(self):
        return ''.join(self.data)
