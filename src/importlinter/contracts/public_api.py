from __future__ import annotations

from collections.abc import Iterable

import grimp

from importlinter.application import contract_utils, output
from importlinter.domain import fields, helpers
from importlinter.domain.contract import Contract, ContractCheck
from importlinter.domain.imports import ModuleExpression

from ._common import Link


class PublicApiContract(Contract):
    """
    Public API contracts check that a set of modules is only imported by the rest of the project
    through its public API.

    The modules are treated as a single unit, made up of the listed modules and all of their
    descendants. The listed modules don't need to be adjacent: for example, a feature split
    across a data layer and a domain layer can form one unit. Imports within the unit are always
    allowed. Other modules in the project must not import the unit, except for its public modules
    (and their descendants).

    Only direct imports are checked: an indirect import has to end with a direct import into the
    unit, which is reported instead. Imports out of the unit are not checked.

    Configuration options:

        - modules:        The modules that make up the unit. Descendants are included too.
        - public_modules: Modules (and their descendants) within the unit that other modules are
                          allowed to import.
        - ignore_imports: A set of ImportExpressions. These imports will be ignored: if the import
                          would cause a contract to be broken, adding it to the set will cause
                          the contract be kept instead. (Optional.)
        - unmatched_ignore_imports_alerting: Decides how to report when the expression in the
                          `ignore_imports` set is not found in the graph. Valid values are
                          "none", "warn", "error". Default value is "error".
        - broken_contract_guidance: Guidance explaining how to fix the contract if it's broken.
                          These are displayed after the contract's violations. (Optional.)
    """

    type_name = "public_api"

    modules = fields.SetField(subfield=fields.ModuleExpressionField())
    public_modules = fields.SetField(subfield=fields.ModuleExpressionField())
    ignore_imports = fields.SetField(subfield=fields.ImportExpressionField(), required=False)
    unmatched_ignore_imports_alerting = fields.EnumField(
        contract_utils.AlertLevel, default=contract_utils.AlertLevel.ERROR
    )
    broken_contract_guidance = fields.TextField(required=False)

    def check(self, graph: grimp.ImportGraph, verbose: bool) -> ContractCheck:
        import_removal = contract_utils.remove_ignored_imports_and_report(
            graph=graph,
            ignore_imports=self.ignore_imports,  # type: ignore
            unmatched_alerting=self.unmatched_ignore_imports_alerting,  # type: ignore
        )

        unit = _get_modules(graph, self.modules)  # type: ignore
        public = _get_modules(graph, self.public_modules)  # type: ignore
        public_modules_outside_unit = public - unit
        if public_modules_outside_unit:
            raise ValueError(
                "Public modules must be within the modules, but these are not: "
                f"{', '.join(sorted(public_modules_outside_unit))}."
            )

        root_packages = tuple(self.session_options["root_packages"])

        illegal_imports: list[Link] = []
        for module in sorted(unit - public):
            for importer in sorted(graph.find_modules_that_directly_import(module) - unit):
                if _is_in_project(importer, root_packages):
                    illegal_imports.append(_build_link(graph, importer=importer, imported=module))

        return ContractCheck(
            kept=not illegal_imports,
            warnings=list(import_removal.warnings),
            ignored_import_count=import_removal.ignored_import_count,
            metadata={"illegal_imports": illegal_imports},
        )

    def render_broken_contract(self, check: ContractCheck) -> None:
        output.print_error(
            "Imports into the modules are only allowed via the public modules:",
            bold=False,
        )
        output.new_line()
        illegal_imports: list[Link] = check.metadata["illegal_imports"]
        for link in illegal_imports:
            line_numbers = ", ".join(map(str, link["line_numbers"]))
            output.print_error(
                f"- {link['importer']} -> {link['imported']} (l.{line_numbers})",
                bold=False,
            )
            output.new_line()
        output.new_line()

        contract_utils.render_broken_contract_guidance(self.broken_contract_guidance)  # type: ignore


def _get_modules(graph: grimp.ImportGraph, expressions: Iterable[ModuleExpression]) -> set[str]:
    """
    Return the names of the modules matching the expressions, along with their descendants.
    """
    modules = helpers.module_expressions_to_modules(
        graph=graph,
        expressions=expressions,
        as_packages=True,
        raise_if_unmatched=True,
    )
    return {module.name for module in modules}


def _is_in_project(module: str, root_packages: tuple[str, ...]) -> bool:
    """
    Return whether the module is in one of the root packages, i.e. it isn't an external package.
    """
    return module in root_packages or module.startswith(
        tuple(f"{root}." for root in root_packages)
    )


def _build_link(graph: grimp.ImportGraph, importer: str, imported: str) -> Link:
    import_details = graph.get_import_details(importer=importer, imported=imported)
    return Link(
        importer=importer,
        imported=imported,
        line_numbers=tuple(detail["line_number"] for detail in import_details),
    )
