"""

bytearound's representation of a code object.

"""
import inspect
import itertools
import types

from . import generator
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
