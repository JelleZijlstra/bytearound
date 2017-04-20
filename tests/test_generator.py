import opcode

from bytearound.generator import stack_effect_map
from bytearound import ops


def test_no_missing_opcodes():
    # These are handled specially in generator.opcode_stack_effect
    special_stack_effect = {op.opcode for op in special_opcodes()}

    _extra_ops = sorted(set(stack_effect_map) - set(opcode.opmap.values()))
    _missing_ops = sorted(
        name for name, value in opcode.opmap.items()
        if value not in stack_effect_map and value not in special_stack_effect)
    if _extra_ops or _missing_ops:
        raise RuntimeError(
            'missing or extra ops, extra={} missing={}'.format(_extra_ops, _missing_ops))

def special_opcodes():
    # These are handled specially in generator.opcode_stack_effect
    yield ops.UNPACK_SEQUENCE
    yield ops.DUP_TOPX
    yield ops.BUILD_TUPLE
    yield ops.BUILD_LIST
    yield ops.BUILD_SET
    yield ops.RAISE_VARARGS
    yield ops.MAKE_FUNCTION
    yield ops.CALL_FUNCTION
    yield ops.CALL_FUNCTION_VAR
    yield ops.CALL_FUNCTION_KW
    yield ops.CALL_FUNCTION_VAR_KW
    yield ops.BUILD_SLICE
    yield ops.MAKE_CLOSURE
    yield ops.STOP_CODE  # Never emitted
