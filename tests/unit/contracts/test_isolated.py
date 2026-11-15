from __future__ import annotations

from textwrap import dedent

import pytest
from grimp import ImportGraph

from importlinter.application.contract_utils import AlertLevel
from importlinter.application.output import console
from importlinter.contracts.isolated import IsolatedContract
from importlinter.domain.contract import InvalidContractOptions


class TestIsolatedContract:
    @staticmethod
    def _build_default_graph() -> ImportGraph:
        graph = ImportGraph()
        for module in (
            "mypackage",
            "mypackage.service",
            "mypackage.service.api",
            "mypackage.service.internal",
            "mypackage.service.internal.deep",
            "mypackage.adapters",
            "mypackage.adapters.service",
            "mypackage.adapters.service.client",
            "mypackage.adapters.other",
            "mypackage.outside",
            "mypackage.outside.sub",
        ):
            graph.add_module(module)
        graph.add_module("django", is_squashed=True)
        return graph

    @staticmethod
    def _build_contract(**contract_options) -> IsolatedContract:
        all_options = {"modules": ("mypackage.service",), **contract_options}
        return IsolatedContract(
            name="Isolated contract",
            session_options={"root_packages": ["mypackage"]},
            # Passing None for an option omits it.
            contract_options={k: v for k, v in all_options.items() if v is not None},
        )

    @pytest.mark.parametrize(
        "importer,imported,contract_kept,description",
        [
            (
                "mypackage.service.internal",
                "mypackage.service.api",
                True,
                "Imports within the modules are allowed",
            ),
            (
                "mypackage.service",
                "mypackage.service.internal.deep",
                True,
                "Imports of descendants of the modules are allowed",
            ),
            (
                "mypackage.outside",
                "mypackage.service.internal",
                True,
                "Imports into the modules are not affected",
            ),
            (
                "mypackage.outside",
                "mypackage.adapters.other",
                True,
                "Unrelated imports are not affected",
            ),
            (
                "mypackage.service.internal",
                "django",
                True,
                "Imports of external packages are not affected",
            ),
            (
                "mypackage.service.internal",
                "mypackage.outside",
                False,
                "A module cannot import another module",
            ),
            (
                "mypackage.service.internal.deep",
                "mypackage.outside.sub",
                False,
                "A descendant of a module cannot import another module",
            ),
            (
                "mypackage.service.api",
                "mypackage.adapters.service",
                False,
                "A module cannot import a module in another package",
            ),
            (
                "mypackage.service.internal",
                "mypackage",
                False,
                "A module cannot import its parent package",
            ),
        ],
    )
    def test_imports(self, importer, imported, contract_kept, description):
        graph = self._build_default_graph()
        graph.add_import(importer=importer, imported=imported)
        contract = self._build_contract()

        contract_check = contract.check(graph, verbose=False)

        assert contract_check.kept == contract_kept, description

    def test_no_imports(self):
        contract_check = self._build_contract().check(self._build_default_graph(), verbose=False)

        assert contract_check.kept

    def test_modules_in_different_locations_form_one_unit(self):
        graph = self._build_default_graph()
        # Imports between the two locations are internal.
        graph.add_import(
            importer="mypackage.adapters.service.client", imported="mypackage.service.internal"
        )
        graph.add_import(
            importer="mypackage.service.internal", imported="mypackage.adapters.service"
        )
        # But the second location is also isolated from other modules.
        graph.add_import(
            importer="mypackage.adapters.service.client", imported="mypackage.outside"
        )
        contract = self._build_contract(
            modules=("mypackage.service", "mypackage.adapters.service")
        )

        contract_check = contract.check(graph, verbose=False)

        assert not contract_check.kept
        assert contract_check.metadata["illegal_imports"] == [
            {
                "importer": "mypackage.adapters.service.client",
                "imported": "mypackage.outside",
                "line_numbers": (),
            }
        ]

    def test_wildcard_modules(self):
        graph = self._build_default_graph()
        graph.add_import(importer="mypackage.adapters.other", imported="mypackage.outside")
        contract = self._build_contract(modules=("mypackage.adapters.*",))

        contract_check = contract.check(graph, verbose=False)

        assert not contract_check.kept

    @pytest.mark.parametrize(
        "importer,imported,allowed_imports,contract_kept,description",
        [
            (
                "mypackage.service.internal",
                "mypackage.outside",
                ("mypackage.outside",),
                True,
                "The unit can import an allowed module",
            ),
            (
                "mypackage.service.api",
                "mypackage.outside.sub",
                ("mypackage.outside",),
                True,
                "The unit can import a descendant of an allowed module",
            ),
            (
                "mypackage.service.internal",
                "mypackage.adapters.other",
                ("mypackage.adapters.*",),
                True,
                "Allowed modules support wildcards",
            ),
            (
                "mypackage.service.internal",
                "mypackage.adapters.other",
                ("mypackage.outside",),
                False,
                "The unit still cannot import modules that aren't allowed",
            ),
        ],
    )
    def test_allowed_imports(
        self, importer, imported, allowed_imports, contract_kept, description
    ):
        graph = self._build_default_graph()
        graph.add_import(importer=importer, imported=imported)
        contract = self._build_contract(allowed_imports=allowed_imports)

        contract_check = contract.check(graph, verbose=False)

        assert contract_check.kept == contract_kept, description

    def test_allowed_imports_does_not_allowed_imports_into_the_unit(self):
        graph = self._build_default_graph()
        graph.add_import(importer="mypackage.outside", imported="mypackage.service.internal")
        contract = self._build_contract(allowed_imports=("mypackage.outside",))

        contract_check = contract.check(graph, verbose=False)

        # Imports into the unit are not this contract's concern, whether or not they're allowed.
        assert contract_check.kept

    @pytest.mark.parametrize(
        "imported,contract_kept",
        [
            ("mypackage.adapters.other", True),
            ("mypackage.adapters", True),
            ("mypackage.outside", False),
        ],
    )
    def test_allowed_imports_of_a_parent_package_of_the_unit(self, imported, contract_kept):
        graph = self._build_default_graph()
        graph.add_import(importer="mypackage.adapters.service.client", imported=imported)
        contract = self._build_contract(
            modules=("mypackage.adapters.service",),
            allowed_imports=("mypackage.adapters",),
        )

        contract_check = contract.check(graph, verbose=False)

        assert contract_check.kept == contract_kept

    @pytest.mark.parametrize(
        "allowed_imports",
        [("mypackage.service.internal",), ("mypackage.service",), ("mypackage.service.*",)],
    )
    def test_allowed_imports_must_be_outside_modules(self, allowed_imports):
        graph = self._build_default_graph()
        contract = self._build_contract(allowed_imports=allowed_imports)

        with pytest.raises(
            ValueError,
            match="Modules in allowed_imports must be outside the modules",
        ):
            contract.check(graph, verbose=False)

    def test_imports_outside_the_root_packages_are_not_affected(self):
        graph = self._build_default_graph()
        graph.add_module("otherpackage")
        graph.add_import(importer="mypackage.service.internal", imported="otherpackage")
        contract = self._build_contract()

        contract_check = contract.check(graph, verbose=False)

        assert contract_check.kept

    def test_ignore_imports(self):
        graph = self._build_default_graph()
        graph.add_import(importer="mypackage.service.internal", imported="mypackage.outside")
        graph.add_import(importer="mypackage.service.api", imported="mypackage.outside.sub")
        contract = self._build_contract(
            ignore_imports=("mypackage.service.internal -> mypackage.outside",)
        )

        contract_check = contract.check(graph, verbose=False)

        assert not contract_check.kept
        assert contract_check.ignored_import_count == 1
        assert [
            (link["importer"], link["imported"])
            for link in contract_check.metadata["illegal_imports"]
        ] == [("mypackage.service.api", "mypackage.outside.sub")]

    def test_ignore_imports_with_wildcards(self):
        graph = self._build_default_graph()
        graph.add_import(importer="mypackage.service.internal", imported="mypackage.outside")
        graph.add_import(
            importer="mypackage.service.internal.deep", imported="mypackage.outside.sub"
        )
        contract = self._build_contract(
            ignore_imports=("mypackage.service.internal.** -> mypackage.outside.**",)
        )

        contract_check = contract.check(graph, verbose=False)

        assert not contract_check.kept
        assert contract_check.ignored_import_count == 1

    @pytest.mark.parametrize(
        "alerting,expected_warnings",
        [
            (AlertLevel.NONE.value, 0),
            (AlertLevel.WARN.value, 1),
        ],
    )
    def test_ignore_imports_unmatched_alerting(self, alerting, expected_warnings):
        graph = self._build_default_graph()
        contract = self._build_contract(
            ignore_imports=("mypackage.service.internal -> mypackage.outside",),
            unmatched_ignore_imports_alerting=alerting,
        )

        contract_check = contract.check(graph, verbose=False)

        assert contract_check.kept
        assert len(contract_check.warnings) == expected_warnings

    def test_metadata(self):
        graph = self._build_default_graph()
        graph.add_import(
            importer="mypackage.service.internal.deep",
            imported="mypackage.outside",
            line_number=7,
            line_contents="import outside",
        )
        graph.add_import(
            importer="mypackage.service.internal.deep",
            imported="mypackage.outside",
            line_number=9,
            line_contents="import outside",
        )

        contract_check = self._build_contract().check(graph, verbose=False)

        assert contract_check.metadata == {
            "illegal_imports": [
                {
                    "importer": "mypackage.service.internal.deep",
                    "imported": "mypackage.outside",
                    "line_numbers": (7, 9),
                }
            ],
        }

    @pytest.mark.parametrize("option", ["modules", "allowed_imports"])
    def test_modules_must_exist(self, option):
        graph = self._build_default_graph()
        contract = self._build_contract(**{option: ("mypackage.service.missing",)})

        with pytest.raises(ValueError, match="Module 'mypackage.service.missing' does not exist."):
            contract.check(graph, verbose=False)

    def test_modules_is_required(self):
        with pytest.raises(InvalidContractOptions) as exc_info:
            self._build_contract(modules=None)

        assert exc_info.value.errors == {"modules": "This is a required field."}

    def test_render_broken_contract(self):
        graph = self._build_default_graph()
        graph.add_import(
            importer="mypackage.service.internal.deep",
            imported="mypackage.outside",
            line_number=7,
            line_contents="import outside",
        )
        graph.add_import(
            importer="mypackage.service.api",
            imported="mypackage.adapters.other",
            line_number=2,
            line_contents="import other",
        )
        contract = self._build_contract(
            broken_contract_guidance="Use mypackage.utils instead.\nMore info: http://docs"
        )
        contract_check = contract.check(graph, verbose=False)

        with console.capture() as capture:
            contract.render_broken_contract(contract_check)

        assert capture.get() == dedent(
            """\
            Imports out of the modules are not allowed:

            - mypackage.service.api -> mypackage.adapters.other (l.2)

            - mypackage.service.internal.deep -> mypackage.outside (l.7)


            Use mypackage.utils instead.
            More info: http://docs

            """
        )
