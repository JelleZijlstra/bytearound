"""

bytearound is a library for parsing Python code objects into a more easily modifiable format.

"""
from code_object import ByteAround
from debug import check, check_recursive
from generator import ops
from objects import Instruction, Label, cell_or_free
