from __future__ import annotations

from collections.abc import Iterable

import grimp

from importlinter.application import contract_utils, output
from importlinter.domain import fields, helpers
from importlinter.domain.contract import Contract, ContractCheck
from importlinter.domain.imports import ModuleExpression

from ._common import Link


class IsolatedContract(Contract):
    """
    Isolated contracts check that a set of modules doesn't import the rest of the project.

    The modules are treated as a single unit, made up of the listed modules and all of their
    descendants. The listed modules don't need to be adjacent: for example, a feature split
    across a data layer and a domain layer can form one unit. Imports within the unit are always
    allowed. The unit must not import any other module in the project, except for the modules it
    is allowed to import. (Imports of external packages are not affected.)

    Only direct imports are checked: an indirect import has to begin with a direct import out of
    the unit, which is reported instead. Imports into the unit are not checked.

    Configuration options:

        - modules:        The modules that make up the unit. Descendants are included too.
        - allowed_imports:  Modules (and their descendants) outside the unit that the unit is
                          allowed to import, such as shared utilities. (Optional.)
        - ignore_imports: A set of ImportExpressions. These imports will be ignored: if the import
                          would cause a contract to be broken, adding it to the set will cause
                          the contract be kept instead. (Optional.)
        - unmatched_ignore_imports_alerting: Decides how to report when the expression in the
                          `ignore_imports` set is not found in the graph. Valid values are
                          "none", "warn", "error". Default value is "error".
        - broken_contract_guidance: Guidance explaining how to fix the contract if it's broken.
                          These are displayed after the contract's violations. (Optional.)
    """

    type_name = "isolated"

    modules = fields.SetField(subfield=fields.ModuleExpressionField())
    allowed_imports = fields.SetField(subfield=fields.ModuleExpressionField(), required=False)
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

        modules: Iterable[ModuleExpression] = self.modules  # type: ignore
        allowed_imports: Iterable[ModuleExpression] = self.allowed_imports or ()  # type: ignore

        unit = _get_modules(graph, modules)
        # Check the allowed modules themselves, not their descendants: allowing a parent package of
        # the unit is fine, and means the unit may import anything else in that package.
        allowed_modules_inside_unit = (
            _get_modules(graph, allowed_imports, as_packages=False) & unit
        )
        if allowed_modules_inside_unit:
            raise ValueError(
                "Modules in allowed_imports must be outside the modules, but these are not: "
                f"{', '.join(sorted(allowed_modules_inside_unit))}."
            )
        allowed = _get_modules(graph, allowed_imports)

        root_packages = tuple(self.session_options["root_packages"])

        illegal_imports: list[Link] = []
        for module in sorted(unit):
            for imported in sorted(
                graph.find_modules_directly_imported_by(module) - unit - allowed
            ):
                if _is_in_project(imported, root_packages):
                    illegal_imports.append(_build_link(graph, importer=module, imported=imported))

        return ContractCheck(
            kept=not illegal_imports,
            warnings=list(import_removal.warnings),
            ignored_import_count=import_removal.ignored_import_count,
            metadata={"illegal_imports": illegal_imports},
        )

    def render_broken_contract(self, check: ContractCheck) -> None:
        output.print_error("Imports out of the modules are not allowed:", bold=False)
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


def _get_modules(
    graph: grimp.ImportGraph, expressions: Iterable[ModuleExpression], as_packages: bool = True
) -> set[str]:
    """
    Return the names of the modules matching the expressions.

    If as_packages is True, the descendants of the matching modules are returned too.
    """
    modules = helpers.module_expressions_to_modules(
        graph=graph,
        expressions=expressions,
        as_packages=as_packages,
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
