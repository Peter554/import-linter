from __future__ import annotations

from textwrap import dedent

import pytest
from grimp import ImportGraph

from importlinter.application.contract_utils import AlertLevel
from importlinter.application.output import console
from importlinter.contracts.public_api import PublicApiContract
from importlinter.domain.contract import InvalidContractOptions


class TestPublicApiContract:
    @staticmethod
    def _build_default_graph() -> ImportGraph:
        graph = ImportGraph()
        for module in (
            "mypackage",
            "mypackage.service",
            "mypackage.service.api",
            "mypackage.service.api.schemas",
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
    def _build_contract(**contract_options) -> PublicApiContract:
        all_options = {
            "modules": ("mypackage.service",),
            "public_modules": ("mypackage.service.api",),
            **contract_options,
        }
        return PublicApiContract(
            name="Public API contract",
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
                "mypackage.service.api",
                "mypackage.service.internal.deep",
                True,
                "Public modules can import private modules in the same unit",
            ),
            (
                "mypackage.outside",
                "mypackage.service.api",
                True,
                "Other modules can import a public module",
            ),
            (
                "mypackage.outside.sub",
                "mypackage.service.api.schemas",
                True,
                "Other modules can import descendants of a public module",
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
                True,
                "Imports out of the modules are not affected",
            ),
            (
                "mypackage.service.internal",
                "mypackage",
                True,
                "Imports of a parent package are not affected",
            ),
            (
                "mypackage.outside",
                "mypackage.service.internal",
                False,
                "Other modules cannot import a private module",
            ),
            (
                "mypackage.outside",
                "mypackage.service.internal.deep",
                False,
                "Other modules cannot import a descendant of a private module",
            ),
            (
                "mypackage.outside",
                "mypackage.service",
                False,
                "Other modules cannot import the module itself, as it's not public",
            ),
            (
                "mypackage",
                "mypackage.service.internal",
                False,
                "Parent packages cannot import a private module",
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
        # But the second location is also protected from other modules.
        graph.add_import(
            importer="mypackage.outside", imported="mypackage.adapters.service.client"
        )
        contract = self._build_contract(
            modules=("mypackage.service", "mypackage.adapters.service")
        )

        contract_check = contract.check(graph, verbose=False)

        assert not contract_check.kept
        assert contract_check.metadata["illegal_imports"] == [
            {
                "importer": "mypackage.outside",
                "imported": "mypackage.adapters.service.client",
                "line_numbers": (),
            }
        ]

    def test_public_modules_in_a_different_location(self):
        graph = self._build_default_graph()
        graph.add_import(importer="mypackage.outside", imported="mypackage.adapters.service")
        contract = self._build_contract(
            modules=("mypackage.service", "mypackage.adapters.service"),
            public_modules=("mypackage.adapters.service",),
        )

        contract_check = contract.check(graph, verbose=False)

        assert contract_check.kept

    def test_wildcard_modules(self):
        graph = self._build_default_graph()
        graph.add_import(importer="mypackage.outside", imported="mypackage.adapters.other")
        contract = self._build_contract(
            modules=("mypackage.adapters.*",),
            public_modules=("mypackage.adapters.service",),
        )

        contract_check = contract.check(graph, verbose=False)

        assert not contract_check.kept

    def test_wildcard_public_modules(self):
        graph = self._build_default_graph()
        graph.add_import(importer="mypackage.outside", imported="mypackage.adapters.other")
        contract = self._build_contract(
            modules=("mypackage.adapters",),
            public_modules=("mypackage.adapters.*",),
        )

        contract_check = contract.check(graph, verbose=False)

        assert contract_check.kept

    def test_imports_outside_the_root_packages_are_not_affected(self):
        graph = self._build_default_graph()
        graph.add_module("otherpackage")
        graph.add_import(importer="otherpackage", imported="mypackage.service.internal")
        contract = self._build_contract()

        contract_check = contract.check(graph, verbose=False)

        assert contract_check.kept

    def test_ignore_imports(self):
        graph = self._build_default_graph()
        graph.add_import(importer="mypackage.outside", imported="mypackage.service.internal")
        graph.add_import(importer="mypackage.outside.sub", imported="mypackage.service")
        contract = self._build_contract(
            ignore_imports=("mypackage.outside -> mypackage.service.internal",)
        )

        contract_check = contract.check(graph, verbose=False)

        assert not contract_check.kept
        assert contract_check.ignored_import_count == 1
        assert [
            (link["importer"], link["imported"])
            for link in contract_check.metadata["illegal_imports"]
        ] == [("mypackage.outside.sub", "mypackage.service")]

    def test_ignore_imports_with_wildcards(self):
        graph = self._build_default_graph()
        graph.add_import(importer="mypackage.outside", imported="mypackage.service.internal")
        graph.add_import(
            importer="mypackage.outside.sub", imported="mypackage.service.internal.deep"
        )
        contract = self._build_contract(
            ignore_imports=("mypackage.outside.** -> mypackage.service.internal.**",)
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
            ignore_imports=("mypackage.outside -> mypackage.service.internal",),
            unmatched_ignore_imports_alerting=alerting,
        )

        contract_check = contract.check(graph, verbose=False)

        assert contract_check.kept
        assert len(contract_check.warnings) == expected_warnings

    def test_metadata(self):
        graph = self._build_default_graph()
        graph.add_import(
            importer="mypackage.outside.sub",
            imported="mypackage.service.internal",
            line_number=4,
            line_contents="import internal",
        )
        graph.add_import(
            importer="mypackage.outside.sub",
            imported="mypackage.service.internal",
            line_number=9,
            line_contents="import internal",
        )

        contract_check = self._build_contract().check(graph, verbose=False)

        assert contract_check.metadata == {
            "illegal_imports": [
                {
                    "importer": "mypackage.outside.sub",
                    "imported": "mypackage.service.internal",
                    "line_numbers": (4, 9),
                }
            ],
        }

    def test_public_modules_must_be_within_modules(self):
        graph = self._build_default_graph()
        contract = self._build_contract(public_modules=("mypackage.outside",))

        with pytest.raises(
            ValueError,
            match=(
                "Public modules must be within the modules, but these are not: mypackage.outside."
            ),
        ):
            contract.check(graph, verbose=False)

    @pytest.mark.parametrize("option", ["modules", "public_modules"])
    def test_modules_must_exist(self, option):
        graph = self._build_default_graph()
        contract = self._build_contract(**{option: ("mypackage.service.missing",)})

        with pytest.raises(ValueError, match="Module 'mypackage.service.missing' does not exist."):
            contract.check(graph, verbose=False)

    @pytest.mark.parametrize("option", ["modules", "public_modules"])
    def test_modules_and_public_modules_are_required(self, option):
        with pytest.raises(InvalidContractOptions) as exc_info:
            self._build_contract(**{option: None})

        assert exc_info.value.errors == {option: "This is a required field."}

    def test_render_broken_contract(self):
        graph = self._build_default_graph()
        graph.add_import(
            importer="mypackage.outside.sub",
            imported="mypackage.service.internal",
            line_number=4,
            line_contents="import internal",
        )
        graph.add_import(
            importer="mypackage.outside",
            imported="mypackage.service.internal.deep",
            line_number=7,
            line_contents="import deep",
        )
        contract = self._build_contract(
            broken_contract_guidance="Use mypackage.service.api instead.\nMore info: http://docs"
        )
        contract_check = contract.check(graph, verbose=False)

        with console.capture() as capture:
            contract.render_broken_contract(contract_check)

        assert capture.get() == dedent(
            """\
            Imports into the modules are only allowed via the public modules:

            - mypackage.outside.sub -> mypackage.service.internal (l.4)

            - mypackage.outside -> mypackage.service.internal.deep (l.7)


            Use mypackage.service.api instead.
            More info: http://docs

            """
        )
