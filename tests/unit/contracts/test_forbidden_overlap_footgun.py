"""
Demonstrations of a footgun in forbidden contracts: overlapping modules are silently skipped.

When a source module is inside a forbidden module (or vice versa), the pair is skipped, so a
contract whose source modules are all inside its forbidden modules is kept whatever the imports.
Using a wildcard, so that the forbidden modules are siblings of the source, works.

Each pattern has a contract without a wildcard, which is kept despite a violation (surprising),
and one with a wildcard, which is broken (as intended).
"""

import pytest
from grimp import ImportGraph

from importlinter.configuration import settings
from importlinter.contracts.forbidden import ForbiddenContract
from tests.adapters.timing import FakeTimer


@pytest.fixture(scope="module", autouse=True)
def configure():
    settings.configure(TIMER=FakeTimer())


def build_graph(modules: list[str], imports: list[tuple[str, str]]) -> ImportGraph:
    graph = ImportGraph()
    for module in modules:
        graph.add_module(module)
    for importer, imported in imports:
        graph.add_import(
            importer=importer, imported=imported, line_number=1, line_contents=f"import {imported}"
        )
    return graph


def build_contract(source_modules, forbidden_modules, ignore_imports) -> ForbiddenContract:
    return ForbiddenContract(
        name="Forbidden contract",
        session_options={"root_packages": ["mypackage"]},
        contract_options={
            "source_modules": source_modules,
            "forbidden_modules": forbidden_modules,
            "ignore_imports": ignore_imports,
            "allow_indirect_imports": "true",
        },
    )


class TestPublicApiPattern:
    """
    "mypackage.catalog may only be imported via mypackage.catalog.api."
    """

    @staticmethod
    def build_graph() -> ImportGraph:
        return build_graph(
            modules=[
                "mypackage",
                "mypackage.catalog",
                "mypackage.catalog.api",
                "mypackage.catalog.internal",
                "mypackage.other",
            ],
            imports=[
                # Allowed: the public API.
                ("mypackage.other", "mypackage.catalog.api"),
                # Violation: bypasses the public API.
                ("mypackage.other", "mypackage.catalog.internal"),
            ],
        )

    def test_without_wildcard_is_kept_despite_violation(self):
        # mypackage contains mypackage.catalog, so the pair is skipped and nothing is checked.
        contract = build_contract(
            source_modules=["mypackage"],
            forbidden_modules=["mypackage.catalog"],
            ignore_imports=["** -> mypackage.catalog.api"],
        )

        contract_check = contract.check(graph=self.build_graph(), verbose=False)

        assert contract_check.kept

    @pytest.mark.parametrize("wildcard", ["mypackage.*", "mypackage.**", "**"])
    def test_with_wildcard_is_broken(self, wildcard: str):
        # The wildcard includes other, which is checked. The modules that overlap the catalog,
        # such as the catalog itself, are skipped.
        contract = build_contract(
            source_modules=[wildcard],
            forbidden_modules=["mypackage.catalog"],
            ignore_imports=["** -> mypackage.catalog.api"],
        )

        contract_check = contract.check(graph=self.build_graph(), verbose=False)

        assert not contract_check.kept


class TestIsolatedPattern:
    """
    "mypackage.billing may not import anything else in mypackage, except mypackage.utils."
    """

    @staticmethod
    def build_graph() -> ImportGraph:
        return build_graph(
            modules=[
                "mypackage",
                "mypackage.billing",
                "mypackage.billing.invoices",
                "mypackage.other",
                "mypackage.utils",
            ],
            imports=[
                # Allowed: shared utilities.
                ("mypackage.billing.invoices", "mypackage.utils"),
                # Violation: imports something else in mypackage.
                ("mypackage.billing.invoices", "mypackage.other"),
            ],
        )

    def test_without_wildcard_is_kept_despite_violation(self):
        # mypackage.billing is inside mypackage, so the pair is skipped and nothing is checked.
        contract = build_contract(
            source_modules=["mypackage.billing"],
            forbidden_modules=["mypackage"],
            ignore_imports=["** -> mypackage.utils"],
        )

        contract_check = contract.check(graph=self.build_graph(), verbose=False)

        assert contract_check.kept

    @pytest.mark.parametrize("wildcard", ["mypackage.*", "mypackage.**", "**"])
    def test_with_wildcard_is_broken(self, wildcard: str):
        # The wildcard includes other, which is checked. The modules that overlap billing, such as
        # billing itself, are skipped.
        contract = build_contract(
            source_modules=["mypackage.billing"],
            forbidden_modules=[wildcard],
            ignore_imports=["** -> mypackage.utils"],
        )

        contract_check = contract.check(graph=self.build_graph(), verbose=False)

        assert not contract_check.kept
