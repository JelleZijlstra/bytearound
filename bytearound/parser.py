"""

Helper functions for parsing code objects into bytearound objects.

"""
from collections import defaultdict
import itertools
import opcode

from . import ops


def parse(co):
    lineno_map = _parse_co_lnotab(co)
    i = 0
    code = co.co_code
    code_len = len(code)
    offset_to_instr = {}
    offset_to_label = defaultdict()
    offset_to_label.default_factory = lambda: ops.Label(len(offset_to_label))
    extended_arg = 0
    free_vars = co.co_cellvars + co.co_freevars

    while i < code_len:
        op = ord(code[i])
        lineno = lineno_map[i]
        oparg = None

        i += 1
        if op >= opcode.HAVE_ARGUMENT:
            raw_oparg = ord(code[i]) + ord(code[i + 1]) * 256 + extended_arg
            extended_arg = 0
            i += 2
            if op == opcode.EXTENDED_ARG:
                extended_arg = raw_oparg * 65536
                continue  # don't include EXTENDED_OPARG here, we'll regenerate it later

            if op in opcode.hascompare:
                oparg = raw_oparg
            elif op in opcode.hasconst:
                oparg = co.co_consts[raw_oparg]
            elif op in opcode.hasfree:
                varname = free_vars[raw_oparg]
                # store whether this is a cellvar or a freevar
                if raw_oparg < len(co.co_cellvars):
                    kind = ops.cell_or_free.cell
                else:
                    kind = ops.cell_or_free.free
                oparg = varname, kind
            elif op in opcode.hasjabs:
                oparg = offset_to_label[raw_oparg]
            elif op in opcode.hasjrel:
                oparg = offset_to_label[i + raw_oparg]
            elif op in opcode.haslocal:
                oparg = co.co_varnames[raw_oparg]
            elif op in opcode.hasname:
                oparg = co.co_names[raw_oparg]
            else:
                oparg = raw_oparg

        offset_to_instr[i] = ops.Instruction.make(op, oparg, lineno)

    return [p[1] for p in sorted(
        itertools.chain(offset_to_instr.items(), offset_to_label.items()),
        key=lambda item: item[0]
    )]


def _parse_co_lnotab(co):
    """Parses co_lnotab into a table {bytecode offset: line offset}."""
    out = {}
    current_addr = 0
    current_line = 0
    for addr_incr, line_incr in get_offsets_from_lnotab(co.co_lnotab):
        new_line = current_line + line_incr
        new_addr = current_addr + addr_incr

        for bytecode_offset in range(current_addr, new_addr):
            out[bytecode_offset] = current_line

        current_addr = new_addr
        current_line = new_line
    for bytecode_offset in range(current_addr, len(co.co_code) + 1):
        out[bytecode_offset] = current_line
    return out


def get_offsets_from_lnotab(lnotab):
    """Parses an lnotab string into (addr offset, line offset) pairs."""
    for offset in range(0, len(lnotab), 2):
        addr_incr = ord(lnotab[offset])
        line_incr = ord(lnotab[offset + 1])
        yield addr_incr, line_incr
