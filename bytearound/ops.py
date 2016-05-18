"""

Helper objects for representing bytecode.

"""

import opcode

_LABEL = -1  # pseudo-opcode for labels
_OPCODE_TO_CLS = {}

__all__ = ['cell_or_free', 'Instruction', 'Label']


class cell_or_free(object):
    """Enum to represent cell/free variables."""
    cell = 1
    free = 2


class Instruction(object):
    """A single bytecode instruction."""
    opcode = None  # subclasses should override

    def __init__(self, oparg=None, lineno=0):
        self.oparg = oparg
        self.lineno = lineno

    def __repr__(self):
        return '%s(%r, %s)' % (opcode.opname[self.opcode], self.oparg, self.lineno)

    def __eq__(self, other):
        if not isinstance(other, Instruction):
            return NotImplemented
        return self.opcode == other.opcode and self.oparg == other.oparg and self.lineno == other.lineno

    @classmethod
    def make(cls, opcode, oparg=None, lineno=0):
        cls = _OPCODE_TO_CLS[opcode]
        return cls(oparg=oparg, lineno=lineno)

    def is_jump(self):
        return self.opcode in opcode.hasjabs or self.opcode in opcode.hasjrel

    def has_argument(self):
        return self.opcode >= opcode.HAVE_ARGUMENT


class Label(Instruction):
    """A jump target.

    Inherits from instruction to make iterating over instructions easier.

    """
    opcode = _LABEL

    def __init__(self, i=None):
        super(Label, self).__init__()
        # index is just for ease of reference, Labels should always be compared by identity
        self.i = i

    def __repr__(self):
        return 'Label(%s)' % self.i

_OPCODE_TO_CLS[_LABEL] = Label


for name, value in opcode.opmap.iteritems():
    name = name.replace('+', '_')
    cls = type(name, (Instruction,), {
        'opcode': value
    })
    locals()[name] = cls
    __all__.append(name)
    _OPCODE_TO_CLS[value] = cls

del name, value, cls
