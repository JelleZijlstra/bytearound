"""

Helpers for generating code objects from bytearound objects.

"""

from collections import namedtuple
from itertools import islice
import opcode

from . import ops

_EXTENDED_ARG_LIMIT = 65536
_BYTE_LIMIT = 256


def generate(ba, pessimize=False):
    instrs_with_offsets = []
    label_to_offset = {}

    if ba.is_function():
        consts = _ConstsList(ba.docstring)
    else:
        consts = _ConstsList()
    cellvars = []
    freevars = []
    varnames = list(ba.argnames)
    names = []

    current_offset = 0
    consts_to_move = set()

    def _get_oparg(instr, current_offset):
        if instr.opcode in opcode.hascompare:
            return instr.oparg
        elif instr.opcode in opcode.hasconst:
            constant = instr.oparg
            if pessimize:
                if constant is None and not (ba.is_function() and consts.objs[0] is None):
                    consts_to_move.add(constant)
            return consts.add(constant)
        elif instr.opcode in opcode.hasfree:
            name, kind = instr.oparg
            if kind == ops.cell_or_free.cell:
                return _get_or_add(cellvars, name)
            else:
                freevar_idx = _get_or_add(freevars, name)
                # TODO what if this exceeds _EXTENDED_ARG_LIMIT
                oparg = len(cellvars) + freevar_idx
                assert oparg < _EXTENDED_ARG_LIMIT, 'TODO fix this'
                return oparg
        elif instr.opcode in opcode.hasjrel:
            # if we don't know where the label is yet, return -1
            # TODO: handle this case
            oparg = label_to_offset.get(instr.oparg, -1) - current_offset
            assert oparg < _EXTENDED_ARG_LIMIT, 'TODO fix this'
            return oparg
        elif instr.opcode in opcode.hasjabs:
            # if we don't know where the label is yet, return -1
            # TODO: handle this case
            oparg = label_to_offset.get(instr.oparg, -1)
            assert oparg < _EXTENDED_ARG_LIMIT, 'TODO fix this'
            return oparg
        elif instr.opcode in opcode.haslocal:
            return _get_or_add(varnames, instr.oparg)
        elif instr.opcode in opcode.hasname:
            return _get_or_add(names, instr.oparg)
        else:
            return instr.oparg

    # compute the offsets of all instructions, so we can generate the code
    # this is complicated by the fact that we can't know beforehand whether we'll need
    # EXTENDED_ARG, especially for jump offsets
    for instr in ba.instructions:
        if isinstance(instr, ops.Label):
            instrs_with_offsets.append((current_offset, instr))
            continue
        offset = current_offset
        current_offset += 1

        if instr.has_argument():
            current_offset += 2
            oparg = _get_oparg(instr, current_offset)
            while oparg >= _EXTENDED_ARG_LIMIT:
                current_offset += 3  # need EXTENDED_ARG
                oparg /= _EXTENDED_ARG_LIMIT
        instrs_with_offsets.append((offset, instr))

    code = []
    # Python emits these sorted by name, rather than by usage like co_names
    cellvars = sorted(cellvars)
    freevars = sorted(freevars)

    for current_offset, instr in instrs_with_offsets:
        if isinstance(instr, ops.Label):
            label_to_offset[instr] = current_offset

    if pessimize:
        for name, insert_after in ba.pessimized_names.iteritems():
            if name not in names:
                if insert_after is None:
                    names.insert(0, name)
                else:
                    try:
                        insert_index = names.index(insert_after) + 1
                    except ValueError:
                        continue  # just ignore it
                    else:
                        names.insert(insert_index, name)

    def _add_op(op, oparg):
        extended_arg = oparg / _EXTENDED_ARG_LIMIT
        rest_of_arg = oparg % _EXTENDED_ARG_LIMIT
        if extended_arg > 0:
            _add_op(opcode.EXTENDED_ARG, extended_arg)
        code.append(op)
        code.append(rest_of_arg % _BYTE_LIMIT)
        code.append(rest_of_arg / _BYTE_LIMIT)

    lnotab = []
    prev_lineno = prev_addr = 0

    for current_offset, instr in instrs_with_offsets:
        if isinstance(instr, ops.Label):
            continue
        if instr.lineno != prev_lineno:
            addr_offset = current_offset - prev_addr
            line_offset = instr.lineno - prev_lineno
            while addr_offset >= _BYTE_LIMIT:
                lnotab.append((_BYTE_LIMIT - 1, 0))
                addr_offset -= _BYTE_LIMIT
            while line_offset >= _BYTE_LIMIT:
                lnotab.append((addr_offset, _BYTE_LIMIT - 1))
                addr_offset = 0
                line_offset -= _BYTE_LIMIT
            if line_offset > 0 or addr_offset > 0:
                lnotab.append((addr_offset, line_offset))
            prev_lineno = instr.lineno
            prev_addr = current_offset

        if instr.has_argument():
            _add_op(instr.opcode, _get_oparg(instr, current_offset + 3))
        else:
            code.append(instr.opcode)

    if pessimize and not lnotab:
        # for one-line generator expressions, CPython generates a nonempty co_lnotab
        # replicate that behavior here
        if any(isinstance(instr, ops.FOR_ITER) for instr in ba.instructions):
            lnotab.append((6, 0))

    return code, consts.as_tuple(), cellvars, freevars, varnames, names, lnotab


def _get_or_add(lst, obj):
    try:
        return lst.index(obj)
    except ValueError:
        lst.append(obj)
        return len(lst) - 1


class _ConstsList(object):
    """Maintains a list of constants.

    Needed because co_consts can contain different objects that nonetheless compare equal when
    simply put in a list (e.g. 1 and 1.0). This objects keeps track of them by object identity.

    """
    def __init__(self, *args):
        self.obj_to_idx = {}
        self.objs = []

        for arg in args:
            self.add(arg)

    def add(self, obj):
        identity = id(obj)
        if identity in self.obj_to_idx:
            return self.obj_to_idx[identity]
        idx = len(self.objs)
        self.objs.append(obj)
        self.obj_to_idx[identity] = idx
        return idx

    def as_tuple(self):
        return tuple(self.objs)


# Stack size calculation
# Based heavily on CPython's code in compile.c (functions stackdepth, stackdepth_walk, and
# opcode_stack_effect).

stack_effect_map = {
    'BINARY_ADD': -1,
    'BINARY_AND': -1,
    'BINARY_DIVIDE': -1,
    'BINARY_FLOOR_DIVIDE': -1,
    'BINARY_LSHIFT': -1,
    'BINARY_MODULO': -1,
    'BINARY_MULTIPLY': -1,
    'BINARY_OR': -1,
    'BINARY_POWER': -1,
    'BINARY_RSHIFT': -1,
    'BINARY_SUBSCR': -1,
    'BINARY_SUBTRACT': -1,
    'BINARY_TRUE_DIVIDE': -1,
    'BINARY_XOR': -1,
    'BREAK_LOOP': 0,
    'BUILD_CLASS': -2,
    'BUILD_MAP': 1,
    'COMPARE_OP': -1,
    'CONTINUE_LOOP': 0,
    'DELETE_ATTR': -1,
    'DELETE_FAST': 0,
    'DELETE_GLOBAL': 0,
    'DELETE_NAME': 0,
    'DELETE_SLICE+0': -1,
    'DELETE_SLICE+1': -2,
    'DELETE_SLICE+2': -2,
    'DELETE_SLICE+3': -3,
    'DELETE_SUBSCR': -2,
    'DUP_TOP': 1,
    'END_FINALLY': -3,
    'EXEC_STMT': -3,
    'EXTENDED_ARG': 0,  # not listed in C
    'FOR_ITER': 1,
    'GET_ITER': 0,
    'IMPORT_FROM': 1,
    'IMPORT_NAME': -1,
    'IMPORT_STAR': -1,
    'INPLACE_ADD': -1,
    'INPLACE_AND': -1,
    'INPLACE_DIVIDE': -1,
    'INPLACE_FLOOR_DIVIDE': -1,
    'INPLACE_LSHIFT': -1,
    'INPLACE_MODULO': -1,
    'INPLACE_MULTIPLY': -1,
    'INPLACE_OR': -1,
    'INPLACE_POWER': -1,
    'INPLACE_RSHIFT': -1,
    'INPLACE_SUBTRACT': -1,
    'INPLACE_TRUE_DIVIDE': -1,
    'INPLACE_XOR': -1,
    'JUMP_ABSOLUTE': 0,
    'JUMP_FORWARD': 0,
    'JUMP_IF_FALSE_OR_POP': 0,
    'JUMP_IF_TRUE_OR_POP': 0,
    'LIST_APPEND': -1,
    'LOAD_ATTR': 0,
    'LOAD_CLOSURE': 1,
    'LOAD_CONST': 1,
    'LOAD_DEREF': 1,
    'LOAD_FAST': 1,
    'LOAD_GLOBAL': 1,
    'LOAD_LOCALS': 1,
    'LOAD_NAME': 1,
    'MAP_ADD': -2,
    'NOP': 0,  # not listed in C
    'POP_BLOCK': 0,
    'POP_JUMP_IF_FALSE': -1,
    'POP_JUMP_IF_TRUE': -1,
    'POP_TOP': -1,
    'PRINT_EXPR': -1,
    'PRINT_ITEM': -1,
    'PRINT_ITEM_TO': -2,
    'PRINT_NEWLINE': 0,
    'PRINT_NEWLINE_TO': -1,
    'RETURN_VALUE': -1,
    'ROT_FOUR': 0,
    'ROT_THREE': 0,
    'ROT_TWO': 0,
    'SETUP_EXCEPT': 0,
    'SETUP_FINALLY': 0,
    'SETUP_LOOP': 0,
    'SETUP_WITH': 4,
    'SET_ADD': -1,
    'SLICE+0': 0,
    'SLICE+1': -1,
    'SLICE+2': -1,
    'SLICE+3': -2,
    # 'STOP_CODE': ,  # omitted, never emitted
    'STORE_ATTR': -2,
    'STORE_DEREF': -1,
    'STORE_FAST': -1,
    'STORE_GLOBAL': -1,
    'STORE_MAP': -2,
    'STORE_NAME': -1,
    'STORE_SLICE+0': -2,
    'STORE_SLICE+1': -3,
    'STORE_SLICE+2': -3,
    'STORE_SLICE+3': -4,
    'STORE_SUBSCR': -3,
    'UNARY_CONVERT': 0,
    'UNARY_INVERT': 0,
    'UNARY_NEGATIVE': 0,
    'UNARY_NOT': 0,
    'UNARY_POSITIVE': 0,
    'WITH_CLEANUP': -1,
    'YIELD_VALUE': 0,
}
stack_effect_map = {opcode.opmap[opname]: value for opname, value in stack_effect_map.iteritems()}


def opcode_stack_effect(instr):
    """Computes the stack effect of a single instruction.

    Based on the CPython function of the same name. Some opcodes have more complicated behavior
    that is handled in compute_stacksize.

    """
    opcode = instr.opcode
    instr_typ = type(instr)
    try:
        return stack_effect_map[opcode]
    except KeyError:
        pass

    if instr_typ is ops.UNPACK_SEQUENCE:
        return instr.oparg - 1
    elif instr_typ is ops.DUP_TOPX:
        return instr.oparg
    elif instr_typ in (ops.BUILD_TUPLE, ops.BUILD_LIST, ops.BUILD_SET):
        return 1 - instr.oparg
    elif instr_typ in (ops.RAISE_VARARGS, ops.MAKE_FUNCTION):
        return -instr.oparg
    elif instr_typ in (ops.CALL_FUNCTION, ops.CALL_FUNCTION_VAR, ops.CALL_FUNCTION_KW,
                       ops.CALL_FUNCTION_VAR_KW):
        nargs = (((instr.oparg) % _BYTE_LIMIT) + 2 * ((instr.oparg) / _BYTE_LIMIT))
        if instr_typ == ops.CALL_FUNCTION:
            return -nargs
        elif instr_typ == ops.CALL_FUNCTION_VAR_KW:
            return -nargs - 2
        else:
            return -nargs - 1
    elif instr_typ == ops.BUILD_SLICE:
        if instr.oparg == 3:
            return -2
        else:
            return -1
    elif instr_typ == ops.MAKE_CLOSURE:
        return -instr.oparg - 1
    raise ValueError('cannot compute stack effect for opcode %s' % instr)


Block = namedtuple('Block', ['begin_idx'])


def compute_stacksize(ba):
    # first divide the code into blocks
    # every label starts a block and every instruction in hasjabs or hasjrel ends one
    label_to_block = {}
    idx_to_block = {}
    begin_block = Block(0)
    idx_to_block[0] = begin_block
    block_to_stack_effect = {}
    seen_blocks = set()

    for i, instr in enumerate(ba.instructions):
        if isinstance(instr, ops.Label):
            block = Block(i)
            label_to_block[instr] = block
            idx_to_block[i] = block
        elif instr.is_jump():
            idx_to_block[i + 1] = Block(i + 1)

    def cached_stack_effect_of_block(block):
        if block in block_to_stack_effect:
            return block_to_stack_effect[block]
        if block in seen_blocks:
            # assume that cycles have no net effect, following stackdepth() in compile.c
            return 0
        seen_blocks.add(block)
        value = stack_effect_of_block(block)
        seen_blocks.remove(block)
        block_to_stack_effect[block] = value
        return value

    def stack_effect_of_block(block):
        depth = 0
        max_depth = 0

        for i, instr in islice(enumerate(ba.instructions), block.begin_idx, None):
            if isinstance(instr, ops.Label):
                continue
            depth += opcode_stack_effect(instr)
            if depth > max_depth:
                max_depth = depth
            # Only jump instructions (or the end of the code) can end a block. Most jump
            # instructions are conditional, but JUMP_ABSOLUTE and JUMP_FORWARD always jump.
            # After a jump, there are two places execution can jump:
            # - the target block, which starts at the label pointed to by the jump
            # - the continuation block, right after the jump instruction (not applicable to
            #   non-conditional jumps)
            # We compute the stack effect of each of these to get the maximum possible stack
            # effect of this block.
            # Some instructions also produce a conditional depth delta: a change to stack depth
            # that is only applicable if one of the two next blocks is chosen. For example,
            # JUMP_IF_TRUE_OR_POP pops one value from the stack only if the continuation block is
            # entered. These are handled specially below.
            # This is based on stackdepth_walk() in CPython's compile.c.
            if instr.is_jump():
                # change in depth to apply to the depth from the target block
                if isinstance(instr, ops.FOR_ITER):
                    target_depth_delta = -2
                elif isinstance(instr, (ops.SETUP_FINALLY, ops.SETUP_EXCEPT)):
                    target_depth_delta = 3
                else:
                    target_depth_delta = 0
                if depth + target_depth_delta > max_depth:
                    max_depth = depth + target_depth_delta

                target_block = label_to_block[instr.oparg]
                target_depth = target_depth_delta + cached_stack_effect_of_block(target_block)
                if not isinstance(instr, (ops.JUMP_ABSOLUTE, ops.JUMP_FORWARD)):
                    if isinstance(instr, (ops.JUMP_IF_TRUE_OR_POP, ops.JUMP_IF_FALSE_OR_POP)):
                        continuation_depth_delta = -1
                    else:
                        continuation_depth_delta = 0

                    continuation_block = idx_to_block[i + 1]
                    continuation_depth = continuation_depth_delta + \
                        cached_stack_effect_of_block(continuation_block)
                    target_depth = max(continuation_depth, target_depth)

                return max(max_depth, depth + target_depth)
        return max_depth
    return stack_effect_of_block(begin_block)
