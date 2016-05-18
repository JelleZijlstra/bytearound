**********
bytearound
**********

bytearound is a module for assembling and disassembling CPython 2.7.11 bytecode. It provides a
representation of bytecode that is easier to modify, create, and inspect than CPython's internal
representation and functionality for going back and forth between this representation and CPython
code objects.

An example of how to create code::

    from bytearound import ByteAround, Instruction, ops

    ba = ByteAround([
        ops.LOAD_CONST('Hello World!'),
        ops.PRINT_ITEM(),
        ops.PRINT_NEWLINE(),
        ops.LOAD_CONST(None),
        ops.RETURN_VALUE(),
    ])
    exec(ba.to_code())

And a simple modification::

    from bytearound import ByteAround

    def f():
        print 'Hello World!'

    ba = ByteAround.from_code(f.func_code)
    for instr in ba:
        if instr.oparg == 'Hello World!':
            instr.oparg = 'Goodbye World!'
    f.func_code = ba.to_code()
    f()

Design and limitations
----------------------

I designed and wrote bytearound to ensure that ``co == ByteAround.from_code(co).to_code()`` always
holds--that is, converting a Python code object to the bytearound representation and back should
give an identical code object. Ensuring that this invariant holds makes it easier to test the code for correctness. The function debug.check() exists to check this invariant.

Unfortunately, there are a number of quirks in the way that CPython generates code objects that
turn out to be hard to replicate. To replicate some of these, I added a ``pessimize=`` argument to
``ByteAround.to_code`` that attempts to faithfully replicate CPython even when not doing so would
be a little more efficient, and I created a custom comparison function that ignores a few other
known issues. However, it may not turn out to be possible to remove all minor differences using
these approaches. Known issues include:

* CPython computes some parts of the code object before it runs the peephole optimizer, which can
  cause co_stacksize to be too high (because the peephole optimizer can turn a series of opcodes
  building a tuple into a single LOAD_CONST opcode). The same issue can also affect the ordering
  of the co_consts field, apparently because the optimizer adds new constants to the end of the
  list. Similarly, mathematical operations on constants (e.g. 2 ** 32) may be optimized away by the
  peephole optimizer, possibly leaving behind unnecessary constants.
* When singleton objects like None and True are used in a function, CPython adds their name to the
  co_names field (unnecessarily, because the objects are loaded directly with LOAD_CONST) and adds
  the constants to the end of the co_consts list. (Normally, co_consts includes constants in order
  of their first appearance in the function.) However, some other usages of None as a constant are
  placed in co_consts in the right position.
* The code object for single-line generator expressions like (f(x) for x in y) has a nonempty
  co_lnotab field, but the co_lnotab for a function defined like "def f(x): print(x)" is empty. In
  some other circumstances CPython also generates an unnecessary 0 offset entry in co_lnotab.
* Large opargs (using EXTENDED_ARG) and large line number offsets are not well-tested and have
  some known issues, noted in the code.

bytearound has been tested only on Python 2.7.11. Previous releases in the 2.7 series should
mostly work, but some changes have been made during the series that impact code objects (e.g.
`issue 21523 <https://bugs.python.org/issue21523>`_).

Links
-----

* `compile.c source <https://github.com/python/cpython/blob/2.7/Python/compile.c>`_
* `dis.py source <https://github.com/python/cpython/blob/2.7/Lib/dis.py>`_
* `lnotab explanation <https://github.com/python/cpython/blob/2.7/Objects/lnotab_notes.txt>`_
* `issue 26549 <https://bugs.python.org/issue26549>`_ (cause of some of the issues described above)

Similar modules
---------------

* `byteplay <https://wiki.python.org/moin/ByteplayDoc>`_ (unmaintained, has bugs)
* `bytecode <https://github.com/haypo/bytecode>`_ (Python 3 only, does not implement stack size computation)
