__doc__ = """

Helpers for debugging and testing code objects.

"""

import contextlib
import difflib
import dis
import sys
import types


_code_object_attributes = sorted(attr for attr in dir(types.CodeType) if not attr.startswith('_'))


def compare_code_objects(co1, co2):
    """Compare two code objects for equality, printing out any differences."""
    equal = True
    for attr in _code_object_attributes:
        value1 = getattr(co1, attr)
        value2 = getattr(co2, attr)
        if value1 != value2:
            print('%s is not equal' % attr)
            equal = False
            # maybe do something special for co_lnotab too
            if attr == 'co_code':
                disassembled1 = _disassemble_to_string(co1).splitlines()
                disassembled2 = _disassemble_to_string(co2).splitlines()
                diff = difflib.unified_diff(disassembled1, disassembled2)
                print(''.join(line + '\n' for line in diff))
            else:
                print('%r != %r' % (value1, value2))

    return equal


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
