"""

bytearound is a library for parsing Python code objects into a more easily modifiable format.

"""
from .code_object import ByteAround
from .debug import check, check_recursive
from . import ops
from .ops import Instruction, Label, cell_or_free
