"""

Helpers for debugging and testing code objects.

"""

import contextlib
import difflib
import dis
import re
import sys
import types

from . import code_object
from . import parser


_CODE_OBJECT_ATTRIBUTES = sorted(attr for attr in dir(types.CodeType) if not attr.startswith('_'))
_REMOVE_LOAD_CONST_NUM_RGX = re.compile(r'LOAD_CONST +\d+ ')


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
    for attr in _CODE_OBJECT_ATTRIBUTES:
        if attr != 'co_code':
            print attr, repr(getattr(co, attr))
    dis.dis(co)


def compare_code_objects(co1, co2):
    """Compare two code objects for equality, printing out any differences.

    This ignores some harmless differences that are commonly encountered with bytearound:
    - co_consts may be in a different order
    - co_lnotab may have unnecessary extra entries when generated by CPython

    """
    not_equal = set()
    different_due_to_const_rearrangement = False

    for attr in _CODE_OBJECT_ATTRIBUTES:
        value1 = getattr(co1, attr)
        value2 = getattr(co2, attr)
        if value1 != value2:
            print '%s is not equal' % attr
            if attr == 'co_consts' and different_due_to_const_rearrangement:
                continue
            if attr == 'co_code':
                disassembled1 = _disassemble_to_string(co1)
                disassembled2 = _disassemble_to_string(co2)
                if co1.co_consts != co2.co_consts and set(co1.co_consts) == set(co2.co_consts):
                    cleaned1 = _REMOVE_LOAD_CONST_NUM_RGX.sub(
                        'LOAD_CONST               N', disassembled1)
                    cleaned2 = _REMOVE_LOAD_CONST_NUM_RGX.sub(
                        'LOAD_CONST               N', disassembled2)
                    if cleaned1 == cleaned2:
                        print 'ignoring co_code difference due to const rearrangement'
                        different_due_to_const_rearrangement = True
                        continue
                diff = difflib.unified_diff(disassembled1.splitlines(), disassembled2.splitlines())
                print ''.join(line + '\n' for line in diff)
            elif attr == 'co_lnotab':
                lnotab1 = list(parser.get_offsets_from_lnotab(value1))
                lnotab2 = list(parser.get_offsets_from_lnotab(value2))
                if _simplify_lnotab(lnotab1) == _simplify_lnotab(lnotab2):
                    print 'ignoring co_lnotab difference that disappeared after simplification'
                    continue
                diff = difflib.unified_diff(map(str, lnotab1), map(str, lnotab2))
                print ''.join(line + '\n' for line in diff)
            else:
                print '%r != %r' % (value1, value2)
            not_equal.add(attr)

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


def _simplify_lnotab(pairs):
    """Simplifies an lnotab represented as a list of (addr_incr, code_incr) pairs."""
    # if there is just one pair and the line offset is 0, ignore it
    if len(pairs) == 1 and pairs[0][1] == 0:
        return []

    # collapse adjacent pairs if the line offset is 0
    prev_pair = None
    new_pairs = []
    for pair in pairs:
        if prev_pair is not None and pair[1] == 0 and pair[0] + prev_pair[0] < 256:
            new_pairs[-1] = (pair[0] + prev_pair[0], prev_pair[1])
        else:
            new_pairs.append(pair)
        prev_pair = pair
    return new_pairs
