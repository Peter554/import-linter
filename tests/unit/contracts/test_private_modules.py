from __future__ import annotations

from textwrap import dedent

import pytest
from grimp import ImportGraph

from importlinter.application.contract_utils import MissingImport
from importlinter.application.output import console
from importlinter.contracts.private_modules import PrivateModulesContract, _is_private_module
from importlinter.domain.contract import ContractCheck, InvalidContractOptions


def _build_contract(**contract_options) -> PrivateModulesContract:
    return PrivateModulesContract(
        name="Private modules",
        session_options={"root_packages": ["mypackage"]},
        contract_options=contract_options,
    )


def _build_graph(*imports: tuple[str, str]) -> ImportGraph:
    graph = ImportGraph()
    for module in (
        "mypackage",
        "mypackage.foo",
        "mypackage.foo._private",
        "mypackage.foo._private.child",
        "mypackage.foo._private.child.grandchild",
        "mypackage.foo.sibling",
        "mypackage.foo.sibling.child",
        "mypackage.foo.sibling.child.grandchild",
        "mypackage.foo.public",
        "mypackage.foobar",
        "mypackage.other",
        "mypackage.other.child",
    ):
        graph.add_module(module)
    for importer, imported in imports:
        graph.add_import(importer=importer, imported=imported)
    return graph


class TestIsPrivateModule:
    @pytest.mark.parametrize(
        "module, expected",
        [
            ("mypackage.foo._bar", True),
            ("mypackage._bar", True),
            ("mypackage.foo.bar", False),
            ("mypackage._foo.bar", False),  # Only the last component counts.
            ("mypackage.foo.bar_", False),
            ("mypackage.foo.__main__", False),
            ("mypackage.foo.__version__", False),
            ("mypackage.foo.__bar", True),  # Only dunder names are exempt.
            ("_mypackage", False),  # Top level modules have no parent to be private to.
        ],
    )
    def test_is_private_module(self, module, expected):
        assert _is_private_module(module) is expected


class TestPrivateModulesContractCheck:
    @pytest.mark.parametrize(
        "importer",
        [
            "mypackage.foo",  # Parent.
            "mypackage.foo.sibling",  # Sibling.
            "mypackage.foo.sibling.child",  # Child of sibling.
            "mypackage.foo.sibling.child.grandchild",  # Grandchild of sibling.
            "mypackage.foo._private.child",  # Child.
            "mypackage.foo._private.child.grandchild",  # Grandchild.
        ],
    )
    def test_legal_imports_of_private_module(self, importer):
        graph = _build_graph((importer, "mypackage.foo._private"))

        check = _build_contract().check(graph, verbose=False)

        assert check.kept

    @pytest.mark.parametrize(
        "importer",
        [
            "mypackage",  # Grandparent.
            "mypackage.other",  # Sibling of parent.
            "mypackage.other.child",  # Child of sibling of parent.
            "mypackage.foobar",  # Not a descendant of the parent, despite the shared name prefix.
        ],
    )
    def test_illegal_imports_of_private_module(self, importer):
        graph = _build_graph((importer, "mypackage.foo._private"))

        check = _build_contract().check(graph, verbose=False)

        assert not check.kept
        assert [
            (link["importer"], link["imported"]) for link in check.metadata["illegal_imports"]
        ] == [(importer, "mypackage.foo._private")]

    @pytest.mark.parametrize(
        "imported",
        ["mypackage.foo._private.child", "mypackage.foo._private.child.grandchild"],
    )
    def test_descendants_of_private_module_are_private_too(self, imported):
        graph = _build_graph(("mypackage.other", imported))

        check = _build_contract().check(graph, verbose=False)

        assert not check.kept

    def test_descendants_of_private_module_can_be_imported_from_parent(self):
        graph = _build_graph(
            ("mypackage.foo.sibling", "mypackage.foo._private.child.grandchild"),
        )

        check = _build_contract().check(graph, verbose=False)

        assert check.kept

    def test_nested_private_module_is_private_to_its_own_parent(self):
        graph = ImportGraph()
        graph.add_import(importer="mypackage.foo.other", imported="mypackage.foo._one._two")
        graph.add_import(importer="mypackage.foo._one.sibling", imported="mypackage.foo._one._two")

        check = _build_contract().check(graph, verbose=False)

        assert not check.kept
        assert [link["importer"] for link in check.metadata["illegal_imports"]] == [
            "mypackage.foo.other"
        ]

    def test_import_is_only_reported_once_when_several_private_modules_are_involved(self):
        graph = ImportGraph()
        graph.add_import(importer="mypackage.other", imported="mypackage.foo._one._two")

        check = _build_contract().check(graph, verbose=False)

        # The import is illegal for both mypackage.foo._one and mypackage.foo._one._two.
        assert len(check.metadata["illegal_imports"]) == 1

    def test_public_modules_are_unrestricted(self):
        graph = _build_graph(("mypackage.other", "mypackage.foo.public"))

        check = _build_contract().check(graph, verbose=False)

        assert check.kept

    def test_indirect_imports_are_not_considered(self):
        graph = _build_graph(
            ("mypackage.other", "mypackage.foo.public"),
            ("mypackage.foo.public", "mypackage.foo._private"),
        )

        check = _build_contract().check(graph, verbose=False)

        assert check.kept

    def test_reports_line_numbers(self):
        graph = _build_graph()
        graph.add_import(
            importer="mypackage.other",
            imported="mypackage.foo._private",
            line_number=3,
            line_contents="from mypackage.foo import _private",
        )
        graph.add_import(
            importer="mypackage.other",
            imported="mypackage.foo._private",
            line_number=9,
            line_contents="from mypackage.foo import _private",
        )

        check = _build_contract().check(graph, verbose=False)

        assert check.metadata["illegal_imports"] == [
            {
                "importer": "mypackage.other",
                "imported": "mypackage.foo._private",
                "line_numbers": (3, 9),
            }
        ]

    def test_packages_with_private_modules_limits_which_private_modules_are_checked(self):
        graph = _build_graph(
            ("mypackage.other", "mypackage.foo._private"),
            ("mypackage.foo", "mypackage.other._hidden"),
        )
        contract = _build_contract(packages_with_private_modules=["mypackage.other"])

        check = contract.check(graph, verbose=False)

        # Only the private module in mypackage.other is checked.
        assert [
            (link["importer"], link["imported"]) for link in check.metadata["illegal_imports"]
        ] == [("mypackage.foo", "mypackage.other._hidden")]

    def test_packages_with_private_modules_includes_descendants(self):
        graph = _build_graph(("mypackage.foobar", "mypackage.foo._private.child"))
        contract = _build_contract(packages_with_private_modules=["mypackage.foo"])

        check = contract.check(graph, verbose=False)

        assert not check.kept

    def test_packages_with_private_modules_checks_descendants_against_private_ancestors(self):
        # The child is public by name, but it inherits privacy from mypackage.foo._private.
        graph = _build_graph(
            ("mypackage.other", "mypackage.foo._private.child"),
            ("mypackage.foo.legal", "mypackage.foo._private.child"),
        )
        contract = _build_contract(packages_with_private_modules=["mypackage.foo"])

        check = contract.check(graph, verbose=False)

        assert [
            (link["importer"], link["imported"]) for link in check.metadata["illegal_imports"]
        ] == [("mypackage.other", "mypackage.foo._private.child")]

    @pytest.mark.parametrize(
        "packages, listed",
        (
            (["mypackage.foo._private"], "'mypackage.foo._private'"),
            (["mypackage.foo._private.child"], "'mypackage.foo._private.child'"),
            (["mypackage._private.foo._other"], "'mypackage._private.foo._other'"),
            (["mypackage.*._private"], "'mypackage.*._private'"),
            (["_mypackage"], "'_mypackage'"),
            (
                ["mypackage.foo", "mypackage.b._c", "mypackage._a"],
                "'mypackage._a', 'mypackage.b._c'",
            ),
        ),
    )
    def test_private_packages_with_private_modules_are_invalid(self, packages, listed):
        with pytest.raises(InvalidContractOptions) as exc_info:
            _build_contract(packages_with_private_modules=packages)

        assert exc_info.value.errors == {
            "packages_with_private_modules": (
                f"Packages cannot be private or inside a private module: {listed}. "
                "List an ancestor that isn't private instead."
            )
        }

    @pytest.mark.parametrize(
        "packages",
        (
            ["mypackage.foo"],
            ["mypackage.my_package"],
            ["mypackage.__main__"],
            ["mypackage.*"],
            ["mypackage.**"],
            ["mypackage.*.foo"],
        ),
    )
    def test_non_private_packages_with_private_modules_are_valid(self, packages):
        _build_contract(packages_with_private_modules=packages)

    def test_packages_with_private_modules_supports_wildcards(self):
        graph = _build_graph(("mypackage.other", "mypackage.foo._private"))
        contract = _build_contract(packages_with_private_modules=["mypackage.*"])

        check = contract.check(graph, verbose=False)

        assert not check.kept

    def test_private_module_outside_packages_with_private_modules_is_not_checked(self):
        graph = _build_graph(("mypackage.other", "mypackage.foo._private"))
        contract = _build_contract(packages_with_private_modules=["mypackage.other"])

        check = contract.check(graph, verbose=False)

        assert check.kept

    def test_packages_with_private_modules_that_do_not_exist_raises(self):
        graph = _build_graph()
        contract = _build_contract(packages_with_private_modules=["mypackage.nonexistent"])

        with pytest.raises(ValueError, match="mypackage.nonexistent"):
            contract.check(graph, verbose=False)

    @pytest.mark.parametrize(
        "expression, matched",
        (
            ("mypackage.foo.*", "'mypackage.foo._private'"),
            ("mypackage.foo.*.child", "'mypackage.foo._private.child'"),
            ("mypackage.**", "'mypackage.foo._private'"),
            ("mypackage.foo.**", "'mypackage.foo._private'"),
        ),
    )
    def test_wildcards_matching_private_packages_raise(self, expression, matched):
        graph = _build_graph()
        contract = _build_contract(packages_with_private_modules=[expression])

        with pytest.raises(ValueError) as exc_info:
            contract.check(graph, verbose=False)

        message = str(exc_info.value)
        assert f"The expression '{expression}'" in message
        assert matched in message

    def test_wildcards_matching_only_public_packages_are_valid(self):
        graph = _build_graph(("mypackage.other", "mypackage.foo._private"))
        contract = _build_contract(packages_with_private_modules=["mypackage.foo.sibling.*"])

        check = contract.check(graph, verbose=False)

        assert check.kept

    def test_unmatched_wildcard_raises(self):
        graph = _build_graph()
        contract = _build_contract(packages_with_private_modules=["mypackage.nope.*"])

        with pytest.raises(ValueError, match="did not match any modules"):
            contract.check(graph, verbose=False)

    def test_ignore_imports(self):
        graph = _build_graph(
            ("mypackage.other", "mypackage.foo._private"),
            ("mypackage.foobar", "mypackage.foo._private.child"),
        )
        contract = _build_contract(
            ignore_imports=["mypackage.other -> mypackage.foo._private"],
        )

        check = contract.check(graph, verbose=False)

        assert not check.kept
        assert check.ignored_import_count == 1
        assert [link["importer"] for link in check.metadata["illegal_imports"]] == [
            "mypackage.foobar"
        ]

    def test_ignore_imports_with_wildcards(self):
        graph = _build_graph(
            ("mypackage.other.child", "mypackage.foo._private.child"),
            ("mypackage.other.child", "mypackage.foo._private.child.grandchild"),
        )
        contract = _build_contract(
            ignore_imports=["mypackage.other.** -> mypackage.foo._private.**"]
        )

        check = contract.check(graph, verbose=False)

        assert check.kept
        assert check.ignored_import_count == 2

    def test_unmatched_ignore_imports_error_by_default(self):
        graph = _build_graph()
        contract = _build_contract(ignore_imports=["mypackage.other -> mypackage.foo._private"])

        with pytest.raises(MissingImport):
            contract.check(graph, verbose=False)

    @pytest.mark.parametrize(
        "alerting, expected_warnings",
        [
            ("none", 0),
            ("warn", 1),
        ],
    )
    def test_unmatched_ignore_imports_alerting(self, alerting, expected_warnings):
        graph = _build_graph()
        contract = _build_contract(
            ignore_imports=["mypackage.other -> mypackage.foo._private"],
            unmatched_ignore_imports_alerting=alerting,
        )

        check = contract.check(graph, verbose=False)

        assert check.kept
        assert len(check.warnings) == expected_warnings


def _build_docs_graph(importer: str, imported: str) -> ImportGraph:
    """
    Build a graph containing every module used in the examples in the docs, with a single import.
    """
    graph = ImportGraph()
    for module in (
        "mypackage",
        "mypackage.public",
        "mypackage.public.blue",
        "mypackage.blue",
        "mypackage.green",
        "mypackage.green._private",
        "mypackage.green._private.red",
        "mypackage._private",
        "mypackage._private.green",
        "mypackage._private._green",
    ):
        graph.add_module(module)
    graph.add_import(importer=importer, imported=imported, line_number=3, line_contents="-")
    return graph


class TestDocumentedExamples:
    """
    The tables in docs/contract_types/private_modules.md.
    """

    @pytest.mark.parametrize(
        "importer, imported, allowed",
        [
            ("mypackage._private", "mypackage.public", True),
            ("mypackage.public", "mypackage._private", True),
            ("mypackage.green", "mypackage.green._private", True),
            ("mypackage.public.blue", "mypackage._private.green", True),
            ("mypackage.blue", "mypackage.green._private", False),
            ("mypackage.blue", "mypackage._private._green", False),
            ("mypackage.blue", "mypackage.green._private.red", False),
        ],
    )
    def test_how_privacy_works(self, importer, imported, allowed):
        graph = _build_docs_graph(importer, imported)

        check = _build_contract().check(graph, verbose=False)

        assert check.kept is allowed

    @pytest.mark.parametrize(
        "packages_with_private_modules, allowed",
        [
            (None, False),
            (["mypackage.green"], False),
            (["mypackage.blue"], True),
        ],
    )
    def test_limiting_which_modules_are_treated_as_private(
        self, packages_with_private_modules, allowed
    ):
        graph = _build_docs_graph("mypackage.blue", "mypackage.green._private")
        options = {}
        if packages_with_private_modules is not None:
            options["packages_with_private_modules"] = packages_with_private_modules

        check = _build_contract(**options).check(graph, verbose=False)

        assert check.kept is allowed

    def test_sample_output(self):
        graph = _build_docs_graph("mypackage.blue", "mypackage.green._private")
        contract = _build_contract()
        check = contract.check(graph, verbose=False)

        with console.capture() as capture:
            contract.render_broken_contract(check)

        assert capture.get() == dedent(
            """\
            Private modules may only be imported from within their parent package:

            - mypackage.blue -> mypackage.green._private (l.3)

            """
        )


class TestPrivateModulesContractRender:
    def test_render_broken_contract(self):
        graph = _build_graph()
        graph.add_import(
            importer="mypackage.other",
            imported="mypackage.foo._private",
            line_number=3,
            line_contents="from mypackage.foo import _private",
        )
        graph.add_import(
            importer="mypackage.foobar",
            imported="mypackage.foo._private.child",
            line_number=1,
            line_contents="from mypackage.foo._private import child",
        )
        contract = _build_contract()
        check = contract.check(graph, verbose=False)

        with console.capture() as capture:
            contract.render_broken_contract(check)

        assert capture.get() == dedent(
            """\
            Private modules may only be imported from within their parent package:

            - mypackage.foobar -> mypackage.foo._private.child (l.1)

            - mypackage.other -> mypackage.foo._private (l.3)

            """
        )

    def test_render_broken_contract_guidance(self):
        contract = _build_contract(broken_contract_guidance="Use the public API instead.")
        check = ContractCheck(
            kept=False,
            metadata={
                "illegal_imports": [
                    {
                        "importer": "mypackage.other",
                        "imported": "mypackage.foo._private",
                        "line_numbers": (3,),
                    }
                ]
            },
        )

        with console.capture() as capture:
            contract.render_broken_contract(check)

        assert "Use the public API instead." in capture.get()
