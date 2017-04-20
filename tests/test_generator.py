import opcode

from bytearound.generator import stack_effect_func_map, stack_effect_map


def test_no_missing_opcodes():
    handled_ops = set(stack_effect_map) | set(stack_effect_func_map)
    extra_ops = sorted(handled_ops - set(opcode.opmap.values()))
    assert not extra_ops, 'Maps include ops that do not exist: {}'.format(extra_ops)
    missing_ops = sorted(name for name, value in opcode.opmap.items() if value not in handled_ops)
    assert not missing_ops, 'Maps are missing some ops: {}'.format(missing_ops)
    dupe_ops = set(stack_effect_map) & set(stack_effect_func_map)
    assert not dupe_ops, 'Ops are handled in both maps: {}'.format(dupe_ops)


if __name__ == '__main__':
    test_no_missing_opcodes()
