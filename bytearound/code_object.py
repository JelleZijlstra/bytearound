"""

bytearound's representation of a code object.

"""
import inspect
import itertools
import types

from . import generator
from .ops import Instruction, Label
from . import parser


class ByteAround(object):
    """bytearound's representation of a Python code object."""
    _not_a_function = object()
    _POSSIBLE_PESSIMIZED_OBJECTS = map(str, (True, False, None, NotImplemented, Ellipsis))

    def __init__(self,
                 instructions=None,
                 filename='<string input>',
                 name='<string input>',
                 flags=0x0,
                 argnames=(),
                 docstring=_not_a_function,
                 firstlineno=1,
                 pessimized_names=None):
        self.filename = filename
        self.name = name
        if instructions is None:
            instructions = []
        self.instructions = instructions
        self.flags = flags
        self.argnames = argnames
        self.docstring = docstring
        self.firstlineno = firstlineno
        if pessimized_names is None:
            pessimized_names = {}
        self.pessimized_names = pessimized_names

    @classmethod
    def from_code(cls, co, is_function=True):
        """Creates a CodeObject object from a raw Python code object."""
        instructions = parser.parse(co)
        # if the code object is a function, the first element in co_consts is supposed to be
        # the docstring
        if is_function and co.co_consts:
            docstring = co.co_consts[0]
        else:
            docstring = cls._not_a_function
        argcount = co.co_argcount
        if co.co_flags & inspect.CO_VARARGS:
            argcount += 1
        if co.co_flags & inspect.CO_VARKEYWORDS:
            argcount += 1
        argnames = co.co_varnames[:argcount]

        # For round-trip compatibility, replicate a bug in CPython where names like None are
        # added to co_names even if only the objects themselves are used. For example, for
        # def f(): x = None, co_names will be ('None',). pessimized_names is a dictionary of
        # {name of pessimized object: name to insert it after or None}.
        pessimized_names = {}
        for name in cls._POSSIBLE_PESSIMIZED_OBJECTS:
            try:
                idx = co.co_names.index(name)
            except ValueError:
                pass
            else:
                if idx == 0:
                    pessimized_names[name] = None
                else:
                    pessimized_names[name] = co.co_names[idx - 1]

        return cls(
            instructions, co.co_filename, co.co_name, co.co_flags, argnames, docstring,
            co.co_firstlineno, pessimized_names
        )

    @classmethod
    def from_function(cls, fn):
        """Creates a ByteAround object from a function."""
        return cls.from_code(fn.func_code, is_function=True)

    def to_code(self, pessimize=False):
        """Computes a code object from this object.

        If pessimize is True, attempts to replicate CPython's behavior more exactly, even where it
        is slightly less efficient.

        """
        code, consts, cellvars, freevars, varnames, names, lnotab = generator.generate(
            self, pessimize=pessimize)
        lnotab = ''.join(map(chr, itertools.chain.from_iterable(lnotab)))
        codestring = ''.join(map(chr, code))
        argcount = len(self.argnames)
        if self.flags & inspect.CO_VARARGS:
            argcount -= 1
        if self.flags & inspect.CO_VARKEYWORDS:
            argcount -= 1
        return types.CodeType(
            argcount,
            len(varnames),  # nlocals
            generator.compute_stacksize(self),
            self.flags,
            codestring,
            tuple(consts),
            tuple(names),
            tuple(varnames),
            self.filename,
            self.name,
            self.firstlineno,
            lnotab,
            tuple(freevars),
            tuple(cellvars),
        )

    def is_function(self):
        """Whether this code object is for a function."""
        return self.docstring is not self._not_a_function

    def __setitem__(self, key, value):
        """Wrapper around writing to self.instructions, to automatically set line numbers.

        The goal is to allow the user to create Instruction objects without having to specify line
        numbers, and then set the correct line numbers when the users adds them using slice
        assignment.

        The approach taken here is to use linenos given in the instructions added to the code
        object if available, and else fall back to the linenos for the instructions that are
        currently nearest to it in the code object.

        """
        if isinstance(key, slice):
            current = self.instructions[key]
            if len(current) == len(value):
                specified_lineno = None
                for i, instr in enumerate(value):
                    if isinstance(instr, Instruction):
                        if instr.lineno is not None:
                            specified_lineno = instr.lineno
                        elif specified_lineno is not None:
                            instr.lineno = specified_lineno
                        else:
                            instr.lineno = _get_nearest_lineno(current, i)
                    else:
                        raise TypeError(
                            'Instructions can only contain Instruction and Label objects, not %s'
                            % value)
            else:
                if len(current) > 0:
                    specified_lineno = _get_nearest_lineno(current, 0)
                else:
                    start_index = 0 if key.start is None else key.start
                    if start_index < len(self.instructions):
                        specified_lineno = _get_nearest_lineno(self.instructions, start_index)
                    else:
                        specified_lineno = None

                for instr in value:
                    if isinstance(instr, Instruction):
                        if instr.lineno is not None:
                            specified_lineno = instr.lineno
                        elif specified_lineno is not None:
                            instr.lineno = specified_lineno
                    else:
                        raise TypeError(
                            'Instructions can only contain Instruction and Label objects, not %s'
                            % instr)

            self.instructions[key] = value
        else:
            if isinstance(value, Label):
                self.instructions[key] = value
            elif isinstance(value, Instruction):
                if value.lineno is None:
                    value.lineno = _get_nearest_lineno(self.instructions, key)
                self.instructions[key] = value
            else:
                raise TypeError(
                    'Instructions can only contain Instruction and Label objects, not %s' % value)

    def __getitem__(self, key):
        return self.instructions[key]

    def __iter__(self):
        return iter(self.instructions)

    def __len__(self):
        return len(self.instructions)

    def __str__(self):
        return 'ByteAround(%s)' % self.instructions

    def __repr__(self):
        return 'ByteAround(%s)' % ', '.join('%s=%r' % p for p in self.__dict__.iteritems())


def _get_nearest_lineno(lst, first_index):
    for elem in itertools.chain(lst[first_index:], reversed(lst[:first_index])):
        if not isinstance(elem, Label):
            return elem.lineno
    return None
