import os
import re
import sys

import torch
from enum import Enum
from typing import Dict, List, Tuple, Union

# Make the helper files in test/ importable
pytorch_test_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(pytorch_test_dir)
from torch.testing._internal.jit_utils import JitTestCase

if __name__ == '__main__':
    raise RuntimeError("This test file is not meant to be run directly, use:\n\n"
                       "\tpython test/test_jit.py TESTNAME\n\n"
                       "instead.")

class TestUnion(JitTestCase):
    def test_union_with_scalar_values(self):
        def fn(x: Union[int, float]) -> str:
            return "foo"

        self.checkScript(fn, (1,))
        self.checkScript(fn, (1.0,))

        scripted = torch.jit.script(fn)

        with self.assertRaisesRegex(RuntimeError, "Expected a member of"
                                    r" Union\[int, float\] but "
                                    "instead found type str"):
            scripted("1")

    def test_union_with_collections(self):
        def fn(x: Union[Dict[str, int], List[int]]) -> str:
            return "foo"

        self.checkScript(fn, ({"foo": 1, "bar": 2, "baz": 3},))
        self.checkScript(fn, ([1, 2, 3],))

        scripted = torch.jit.script(fn)

        with self.assertRaisesRegex(RuntimeError, "Expected a member of"
                                    r" Union\[Dict\[str, int\], "
                                    r"List\[int\]\] but instead found "
                                    r"type Dict\[str, str\]"):
            scripted({"foo": "bar", "baz": "qux"})

        with self.assertRaisesRegex(RuntimeError, "Expected a member of"
                                    r" Union\[Dict\[str, int\], "
                                    r"List\[int\]\] but instead found "
                                    r"type List\[str\]"):
            scripted(["foo", "bar", "baz"])

        with self.assertRaisesRegex(RuntimeError, "Expected a member of"
                                    r" Union\[Dict\[str, int\], "
                                    r"List\[int\]\] but instead found "
                                    "type str"):
            scripted("1")

    def test_union_with_enum(self):

        global Color

        class Color(Enum):
            RED = 1
            GREEN = 2

        def fn(x: Union[str, Color]) -> str:
            return "foo"

        self.checkScript(fn, (Color.RED,))
        self.checkScript(fn, ("red",))

        scripted = torch.jit.script(fn)

        with self.assertRaisesRegex(RuntimeError, "Expected a member of"
                            r" Union\[str, __torch__.jit.test_union."
                            r"Color\] but instead found type int"):
            scripted(1)

    def test_union_in_class_constructor(self):

        @torch.jit.script
        class A(object):    # noqa B903
            def __init__(self, x: Union[int, str]) -> None:
                self.x = x

        def fn(x: Union[str, int]) -> A:
            return A(x)

        self.assertEqual(fn("foo").x, "foo")
        self.assertEqual(fn(1).x, 1)

        scripted = torch.jit.script(fn)

        with self.assertRaisesRegex(RuntimeError, "Expected a member of"
                    r" Union\[str, int\] but instead found type "
                    r"List\[str\]"):
            scripted(["foo", "bar", "baz"])

    def test_union_return_type(self):
        def fn(x: int) -> Union[int, str]:
            return "foo"

        self.checkScript(fn, (1,))

    def test_union_return_type_with_same_type_branching(self):
        def fn(x: int) -> Union[int, str]:
            if x % 2:
                return "foo"
            else:
                return "bar"

        self.checkScript(fn, (1,))
        self.checkScript(fn, (8,))

    def test_union_return_type_with_different_type_branching(self):
        def fn(x: int) -> Union[int, str]:
            if x % 2:
                return "foo"
            else:
                return 1

        self.checkScript(fn, (1,))
        self.checkScript(fn, (8,))

    def test_union_as_annotation(self):
        def fn() -> Union[int, str]:
            x: Union[int, str] = "foo"
            return x

        self.checkScript(fn, ())

    def test_union_as_annotation_in_typed_container(self):
        def fn() -> None:
            l: List[Union[int, str]] = []
            u1: Union[int, str] = "foo"
            u2: Union[int, str] = 1
            l.append(u1)
            l.append(u2)

        self.checkScript(fn, ())

    def test_union_as_internal_tuple_type(self):
        def fn():
            t: Tuple[Union[int, str], Union[int, str]] = (1, "foo")
            return t

        self.checkScript(fn, ())

    def test_union_variable_can_be_reassigned(self):
        def fn() -> Union[int, str]:
            x: Union[int, str] = "foo"
            i: int = 1
            s: str = "bar"
            x = i
            x = s
            return x

        self.checkScript(fn, ())

    def test_union_does_not_replace_existing_annotated_type(self):
        def fn():
            x: List[int] = [1, 2, 3]
            x.append("foo")
            return x

        with self.assertRaisesRegex(RuntimeError, "Could not match type str"):
            scripted = torch.jit.script(fn)
            scripted()

    def test_union_does_not_replace_existing_union_annotated_type(self):
        def fn():
            x: List[Union[int, str]] = [1, "foo", 3]
            x.append(2.0)
            return x

        with self.assertRaisesRegex(RuntimeError, "Could not match type float"):
            scripted = torch.jit.script(fn)
            scripted()

    def test_union_does_not_replace_existing_annotated_type_with_empty_container(self):
        def fn():
            x: List[int] = []
            x.append("foo")
            return x

        with self.assertRaisesRegex(RuntimeError, "Could not match type str"):
            scripted = torch.jit.script(fn)
            scripted()

    def test_unions_of_unions_are_flattened(self):
        @torch.jit.script
        def fn_with_union(x: Union[int, str, float]) -> str:
            return "foo"

        @torch.jit.script
        def fn_with_nested_union(x: Union[Union[int, str], float]) -> str:
            return "foo"

        self.assertEqual(fn_with_union(1), fn_with_nested_union(1))

    def test_unions_of_a_single_argument_vanish(self):
        @torch.jit.script
        def fn_with_int(x: int) -> str:
            return "foo"

        @torch.jit.script
        def fn_with_union_of_int(x: Union[int]) -> str:
            return "foo"

        self.assertEqual(fn_with_int(1), fn_with_union_of_int(1))

    def test_union_redundant_arguments_are_skipped(self):
        @torch.jit.script
        def fn(x: Union[int, str]) -> str:
            return "foo"

        @torch.jit.script
        def redundant_fn(x: Union[int, str, int]) -> str:
            return "foo"

        self.assertEqual(fn(1), redundant_fn(1))

    def test_union_argument_order_is_ignored(self):
        @torch.jit.script
        def fn1(x: Union[int, str]) -> str:
            return "foo"

        @torch.jit.script
        def fn2(x: Union[str, int]) -> str:
            return "foo"

        self.assertEqual(fn1(1), fn2(1))

    def test_union_T_None_is_equivalent_to_optional_T(self):
        def fn(x: Union[int, None]) -> str:
            return "foo"

        self.checkScript(fn, (1,))

    def test_union_subclasses_larger_union(self):
        def fn() -> Union[int, str, torch.Tensor]:
            x: Union[int, str] = "foo"
            return x

        self.checkScript(fn, ())

    def test_union_with_type_coalescing(self):
        def fn(x: Union[List[int], int]) -> int:
            lst = [1, 2, 3]
            if isinstance(x, int):
                x = lst
            return lst[0]

        self.checkScript(fn, (1,))
        self.checkScript(fn, ([4, 5, 6],))

    def test_union_as_dict_key(self):
        def fn():
            x: Dict[Union[int, str], str] = {}
            x["foo"] = "bar"
            x[1] = 2
            return x[1]

        with self.assertRaisesRegex(RuntimeError, "only int, float, "
                                    "complex, Tensor and string keys "
                                    "are supported"):
            torch.jit.script(fn)

    def test_union_as_dict_value(self):
        def fn():
            x: Dict[str, Union[int, str]] = {}
            x["foo"] = "bar"
            x["baz"] = 2
            return x["baz"]

        self.checkScript(fn, ())

    def test_union_schema_matching_on_internal_type_schema_different_container_type(self):
        # We can't use `checkScript` here because Python doesn't allow
        # subscripted generics with class and instance checks. Instead,
        # we can compare the outputs of the Python version and the
        # TorchScript version. (The divergent line is the `isinstance`
        # check)

        def python_fn(x: Union[List[int], Dict[str, int]]) -> int:
            if isinstance(x, List):
                return x[0]
            return list(x.values())[0]

        @torch.jit.script
        def torchscript_fn(x: Union[List[int], Dict[str, int]]) -> int:
            if isinstance(x, List[int]):
                return x[0]
            return list(x.values())[0]

        list_input_ref = python_fn([1, 2, 3])
        list_input_out = torchscript_fn([1, 2, 3])
        self.assertEqual(list_input_ref, list_input_out)

        dict_input_ref = python_fn({"foo": 1, "bar": 2, "baz": 3})
        dict_input_out = torchscript_fn({"foo": 1, "bar": 2, "baz": 3})
        self.assertEqual(dict_input_ref, dict_input_out)

    def test_union_module_with_union_instance_variable(self):
        class M(torch.nn.Module):

            x: Union[int, str]

            def __init__(self, x: Union[int, str]):
                super().__init__()
                self.x: Union[int, str] = x

            def forward(self, y: Union[int, str]):
                self.x = y
                return self.x

        self.checkModule(M(2,), (1,))
        self.checkModule(M("bar"), ("foo",))

    def test_union_module_with_union_class_variable(self):
        class M(torch.nn.Module):
            x: Union[int, str] = "foo"

            def __init__(self, y: int):
                super().__init__()
                x = y

            def forward(self, z: str):
                x = z
                return x

        self.checkModule(M(1), ("foo",))

    # TODO: The following tests cannot be implemented because they rely
    # on constructs that are not yet implemented in TorchScript:
    #   - Union accepts child classes in place of parent classes
    #     (relies on polymorphism)
    #   - Union accepts aliased types (relies on aliased types)
    #   - IN-DEPTH Union subtyping (TorchScript has a fairly flat type
    #     hierarchy so far)
    #   - hasattr behavior (doesn't work for any type in TorchScript
    #     right now; filed a bug report)
