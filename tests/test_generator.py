import opcode

from bytearound.generator import stack_effect_func_map, stack_effect_map


def test_no_missing_opcodes():
    handled_ops = set(stack_effect_map) | set(stack_effect_func_map)
    extra_ops = sorted(handled_ops - set(opcode.opmap.values()))
    missing_ops = sorted(name for name, value in opcode.opmap.items() if value not in handled_ops)
    if extra_ops or missing_ops:
        raise RuntimeError(
            'missing or extra ops, extra={} missing={}'.format(extra_ops, missing_ops))


if __name__ == '__main__':
    test_no_missing_opcodes()
