"""
Benchmarks of contracts, using a fake graph.

When the tests are run normally (`--benchmark-disable`), each benchmark is run once and not timed,
so it is checked like any other test. To time them, use `just benchmark-local`.
"""

from __future__ import annotations

import random
from copy import deepcopy

import pytest
from grimp import ImportGraph

from importlinter.adapters.timing import SystemClockTimer
from importlinter.application import contract_utils
from importlinter.application.app_config import settings
from importlinter.contracts.acyclic_siblings import AcyclicSiblingsContract
from importlinter.contracts.forbidden import ForbiddenContract
from importlinter.contracts.independence import IndependenceContract
from importlinter.contracts.layers import LayersContract
from importlinter.contracts.private_modules import PrivateModulesContract
from importlinter.contracts.protected import ProtectedContract
from importlinter.domain.imports import ImportExpression, ModuleExpression

from . import graph as fake_graph


@pytest.fixture(scope="module", autouse=True)
def configure():
    settings.configure(TIMER=SystemClockTimer())


@pytest.fixture(scope="module")
def _kept_graph() -> ImportGraph:
    return fake_graph.build_graph()


@pytest.fixture
def graph(_kept_graph) -> ImportGraph:
    # Copy because the benchmarks add imports to the graph.
    return deepcopy(_kept_graph)


def _run_benchmark_with_fresh_graph(benchmark, contract, graph):
    """
    Benchmark checking the contract, using a fresh copy of the graph for each round.

    This is needed because checking a contract may mutate the graph: for example, the ignored
    imports are removed from it, and checking raises if an ignored import is missing. Making the
    copy is part of the setup, so isn't timed.

    Returns the contract check.
    """

    def setup():
        return (deepcopy(graph),), {}

    def run(graph_copy):
        return contract.check(graph_copy, verbose=False)

    # iterations must be 1 when passing setup.
    return benchmark.pedantic(run, setup=setup, rounds=20, iterations=1)


def test_remove_ignored_imports(_kept_graph, benchmark):
    # remove_ignored_imports mutates the graph, and raises if an import is missing, so each round
    # needs a fresh graph. Setup runs outside the timed region.
    def setup():
        graph = deepcopy(_kept_graph)
        imports_added = [
            ImportExpression(ModuleExpression(importer), ModuleExpression(imported))
            for importer, imported in fake_graph.add_imports(
                graph, importer_layer="data", imported_layer="domain", count=1000
            )
        ]
        return (graph, imports_added), {}

    def run(graph, imports_added):
        contract_utils.remove_ignored_imports(
            graph, imports_added, contract_utils.AlertLevel.ERROR
        )

    # iterations must be 1 when passing setup.
    benchmark.pedantic(run, setup=setup, rounds=20, iterations=1)


class TestForbidden:
    @staticmethod
    def _build_contract() -> ForbiddenContract:
        return ForbiddenContract(
            name="Data must not import anything else",
            session_options={"root_packages": [fake_graph.ROOT_PACKAGE]},
            contract_options={
                "source_modules": ["mypkg.data"],
                "forbidden_modules": ["mypkg.**"],
            },
        )

    def test_kept(self, graph, benchmark):
        contract = self._build_contract()
        contract_check = _run_benchmark_with_fresh_graph(benchmark, contract, graph)
        assert contract_check.kept

    def test_broken(self, graph, benchmark):
        # Add violations
        fake_graph.add_imports(graph, importer_layer="data", imported_layer="domain", count=100)

        contract = self._build_contract()
        contract_check = _run_benchmark_with_fresh_graph(benchmark, contract, graph)
        assert not contract_check.kept


class TestProtected:
    @staticmethod
    def _build_contract() -> ProtectedContract:
        return ProtectedContract(
            name="Application must only be imported by the plugins",
            session_options={"root_packages": [fake_graph.ROOT_PACKAGE]},
            contract_options={
                "protected_modules": ["mypkg.application"],
                "allowed_importers": ["mypkg.plugins"],
            },
        )

    def test_kept(self, graph, benchmark):
        contract = self._build_contract()
        contract_check = _run_benchmark_with_fresh_graph(benchmark, contract, graph)
        assert contract_check.kept

    def test_broken(self, graph, benchmark):
        # Add violations
        fake_graph.add_imports(
            graph, importer_layer="domain", imported_layer="application", count=100
        )

        contract = self._build_contract()
        contract_check = _run_benchmark_with_fresh_graph(benchmark, contract, graph)
        assert not contract_check.kept


class TestLayers:
    @staticmethod
    def _build_contract() -> LayersContract:
        return LayersContract(
            name="Application, domain and data are layered",
            session_options={"root_packages": [fake_graph.ROOT_PACKAGE]},
            contract_options={
                "layers": [
                    "mypkg.plugins",
                    "mypkg.application",
                    "mypkg.domain",
                    "mypkg.data",
                ],
            },
        )

    def test_kept(self, graph, benchmark):
        contract = self._build_contract()
        contract_check = _run_benchmark_with_fresh_graph(benchmark, contract, graph)
        assert contract_check.kept

    def test_broken(self, graph, benchmark):
        # Add violations
        fake_graph.add_imports(graph, importer_layer="data", imported_layer="domain", count=100)

        contract = self._build_contract()
        contract_check = _run_benchmark_with_fresh_graph(benchmark, contract, graph)
        assert not contract_check.kept


class TestIndependence:
    @staticmethod
    def _build_contract() -> IndependenceContract:
        return IndependenceContract(
            name="Plugins are independent",
            session_options={"root_packages": [fake_graph.ROOT_PACKAGE]},
            contract_options={
                "modules": ["mypkg.plugins.red", "mypkg.plugins.green", "mypkg.plugins.blue"],
            },
        )

    def test_kept(self, graph, benchmark):
        contract = self._build_contract()
        contract_check = _run_benchmark_with_fresh_graph(benchmark, contract, graph)
        assert contract_check.kept

    def test_broken(self, graph, benchmark):
        # Add violations
        fake_graph.add_imports(
            graph, importer_layer="plugins.red", imported_layer="plugins.green", count=100
        )

        contract = self._build_contract()
        contract_check = _run_benchmark_with_fresh_graph(benchmark, contract, graph)
        assert not contract_check.kept


class TestPrivateModules:
    @pytest.fixture
    def graph(self, graph) -> ImportGraph:
        """
        Add a private package to each layer, with a module for each module in the layer.

        Each module imports its private counterpart, which is legal as it's within the parent
        package of the private module.
        """
        for layer in fake_graph._LAYERS:
            for number in range(fake_graph.MODULES_PER_LAYER):
                importer = fake_graph.module_name(layer, number)
                imported = f"{fake_graph.ROOT_PACKAGE}.{layer}._internal.{number:03d}"
                fake_graph.add_module(graph, imported)
                graph.add_import(
                    importer=importer,
                    imported=imported,
                    line_number=1,
                    line_contents=f"import {imported}",
                )
        return graph

    @staticmethod
    def _build_contract() -> PrivateModulesContract:
        return PrivateModulesContract(
            name="Private modules are private",
            session_options={"root_packages": [fake_graph.ROOT_PACKAGE]},
            contract_options={},
        )

    def test_kept(self, graph, benchmark):
        contract = self._build_contract()
        contract_check = benchmark(contract.check, graph, verbose=False)
        assert contract_check.kept

    def test_broken(self, graph, benchmark):
        # Add violations: modules in the domain layer importing the private modules of the data
        # layer.
        for number in range(100):
            imported = f"{fake_graph.ROOT_PACKAGE}.data._internal.{number:03d}"
            graph.add_import(
                importer=fake_graph.module_name("domain", number),
                imported=imported,
                line_number=2,
                line_contents=f"import {imported}",
            )

        contract = self._build_contract()
        contract_check = benchmark(contract.check, graph, verbose=False)
        assert not contract_check.kept


class TestAcyclicSiblings:
    @staticmethod
    def _build_contract() -> AcyclicSiblingsContract:
        return AcyclicSiblingsContract(
            name="There are no cycles between siblings",
            session_options={"root_packages": [fake_graph.ROOT_PACKAGE]},
            contract_options={"ancestors": ["mypkg"]},
        )

    def test_kept(self, graph, benchmark):
        contract = self._build_contract()
        contract_check = _run_benchmark_with_fresh_graph(benchmark, contract, graph)
        assert contract_check.kept

    def test_broken(self, graph, benchmark):
        # Add violations. The domain already imports the data layer, so this makes a cycle.
        fake_graph.add_imports(graph, importer_layer="data", imported_layer="domain", count=100)

        contract = self._build_contract()
        contract_check = _run_benchmark_with_fresh_graph(benchmark, contract, graph)
        assert not contract_check.kept


class TestPublicAPIPattern:
    """
    Benchmarks of "this package is only imported via its public API", using the protected and
    forbidden contracts.

    Neither contract can name a public API, so it is written as ignored imports.
    """

    _CATALOG = f"{fake_graph.ROOT_PACKAGE}.catalog"
    _API = f"{_CATALOG}.api"

    @pytest.fixture
    def kept_graph(self, graph) -> ImportGraph:
        """
        Add a catalog package to the graph, which is only imported via its api.

        The catalog has an api module and 100 other modules, mypkg.catalog.00 to mypkg.catalog.99.
        The api imports each of the other modules once, and is imported by 100 modules in each of
        the domain and application layers. The importing modules are chosen at random, but are the
        same every time.
        """
        fake_graph.add_module(graph, self._API)
        for number in range(100):
            imported = f"{self._CATALOG}.{number:02d}"
            fake_graph.add_module(graph, imported)
            graph.add_import(
                importer=self._API,
                imported=imported,
                line_number=1,
                line_contents=f"import {imported}",
            )

        random_generator = random.Random(0)
        for layer in ("domain", "application"):
            for number in random_generator.sample(range(fake_graph.MODULES_PER_LAYER), 100):
                graph.add_import(
                    importer=fake_graph.module_name(layer, number),
                    imported=self._API,
                    line_number=1,
                    line_contents=f"import {self._API}",
                )
        return graph

    @pytest.fixture
    def broken_graph(self, kept_graph) -> ImportGraph:
        """
        Add 100 imports of modules in the catalog that aren't the api, by modules in the domain layer.

        The importing modules are chosen at random, but are the same every time.
        """
        random_generator = random.Random(1)
        for number in random_generator.sample(range(fake_graph.MODULES_PER_LAYER), 100):
            imported = f"{self._CATALOG}.{random_generator.randrange(100):02d}"
            kept_graph.add_import(
                importer=fake_graph.module_name("domain", number),
                imported=imported,
                line_number=2,
                line_contents=f"import {imported}",
            )
        return kept_graph

    @staticmethod
    def _build_protected_contract() -> ProtectedContract:
        return ProtectedContract(
            name="Catalog is only imported via its api",
            session_options={"root_packages": [fake_graph.ROOT_PACKAGE]},
            contract_options={
                "protected_modules": ["mypkg.catalog"],
                "allowed_importers": [],
                "ignore_imports": [
                    # Public API
                    "** -> mypkg.catalog.api",
                ],
            },
        )

    @staticmethod
    def _build_forbidden_contract(source_modules: str) -> ForbiddenContract:
        return ForbiddenContract(
            name="Catalog is only imported via its api",
            session_options={"root_packages": [fake_graph.ROOT_PACKAGE]},
            contract_options={
                "allow_indirect_imports": "True",
                "source_modules": [source_modules],
                "forbidden_modules": ["mypkg.catalog"],
                "ignore_imports": [
                    # Public API
                    "** -> mypkg.catalog.api",
                ],
            },
        )

    def test_protected_kept(self, kept_graph, benchmark):
        contract = self._build_protected_contract()
        contract_check = _run_benchmark_with_fresh_graph(benchmark, contract, kept_graph)
        assert contract_check.kept

    def test_protected_broken(self, broken_graph, benchmark):
        contract = self._build_protected_contract()
        contract_check = _run_benchmark_with_fresh_graph(benchmark, contract, broken_graph)
        assert not contract_check.kept

    # The source modules expressions are equivalent: as_packages is true by default, so the
    # descendants of the matched modules are added, and each expression ends up selecting every
    # module in mypkg. (** also matches mypkg itself, but that overlaps with the forbidden module
    # so is skipped.) They differ only in the cost of expanding the expression.
    #
    # "mypkg" isn't one of the choices: a source module that contains the forbidden module
    # overlaps with it, so is never checked, and the contract would be kept whatever the imports.
    @pytest.mark.parametrize(
        "source_modules",
        ["**", "mypkg.*", "mypkg.**"],
        ids=["all_modules", "direct_children", "all_descendants"],
    )
    def test_forbidden_kept(self, kept_graph, benchmark, source_modules):
        contract = self._build_forbidden_contract(source_modules)
        contract_check = _run_benchmark_with_fresh_graph(benchmark, contract, kept_graph)
        assert contract_check.kept

    # See test_forbidden_kept: these source modules expressions are equivalent.
    @pytest.mark.parametrize(
        "source_modules",
        ["**", "mypkg.*", "mypkg.**"],
        ids=["all_modules", "direct_children", "all_descendants"],
    )
    def test_forbidden_broken(self, broken_graph, benchmark, source_modules):
        contract = self._build_forbidden_contract(source_modules)
        contract_check = _run_benchmark_with_fresh_graph(benchmark, contract, broken_graph)
        assert not contract_check.kept
