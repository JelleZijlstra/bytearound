__doc__ = """

Helper objects for representing bytecode.

"""

import opcode


class Instruction(object):
	"""A single bytecode instruction."""

	def __init__(self, opcode, oparg=None, lineno=0):
		self.opcode = opcode
		self.oparg = oparg
		self.lineno = lineno

	def __repr__(self):
		return 'Instruction(%s, %r, %s)' % (opcode.opname[self.opcode], self.oparg, self.lineno)

	def is_jump(self):
		return self.opcode in opcode.hasjabs or self.opcode in opcode.hasjrel


class Label(object):
	"""A jump target."""

	def __init__(self, i):
		self.i = i  # index is just for ease of reference, Labels should always be compared by identity

	def __repr__(self):
		return 'Label(%s)' % self.i


class cell_or_free(object):
	"""Enum to represent cell/free variables."""
	cell = 1
	free = 2