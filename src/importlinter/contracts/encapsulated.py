from __future__ import annotations

from collections.abc import Callable

import grimp

from importlinter import Contract, ContractCheck, fields, output
from importlinter.application import contract_utils
from importlinter.domain import helpers
from importlinter.domain.imports import Module

from ._common import Link


class EncapsulatedContract(Contract):
    """
    Encapsulated contracts check that a set of modules is isolated from the rest of the project.

    The modules are treated as a single unit, made up of the listed modules and all of their
    descendants. Imports within the unit are always allowed. Imports across its boundary are not:

        - The unit must not import any other module in scope. (Imports of external packages
          are not affected.)
        - Other modules in scope must not import the unit, except for its public modules.

    Only direct imports are checked: an indirect import has to begin or end with a direct import
    across the boundary, which is reported instead.

    Configuration options:

        - modules:        The modules that make up the unit. Descendants are included too.
        - public_modules: Modules (and their descendants) within the unit that other modules are
                          allowed to import. (Optional.)
        - scope:          The modules (and their descendants) that the contract considers. Imports
                          across the boundary with a module that isn't in scope are ignored.
                          Defaults to the root packages. (Optional.)
        - ignore_imports: A set of ImportExpressions. These imports will be ignored: if the import
                          would cause a contract to be broken, adding it to the set will cause
                          the contract be kept instead. (Optional.)
        - unmatched_ignore_imports_alerting: Decides how to report when the expression in the
                          `ignore_imports` set is not found in the graph. Valid values are
                          "none", "warn", "error". Default value is "error".
        - broken_contract_guidance: Guidance explaining how to fix the contract if it's broken.
                          These are displayed after the contract's violations. (Optional.)
    """

    type_name = "encapsulated"

    modules = fields.SetField(subfield=fields.ModuleExpressionField())
    public_modules = fields.SetField(subfield=fields.ModuleExpressionField(), required=False)
    scope = fields.SetField(subfield=fields.ModuleExpressionField(), required=False)
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

        unit = self._get_modules_with_descendants(graph, self.modules)
        public = self._get_modules_with_descendants(graph, self.public_modules or ())
        private_public_modules = public - unit
        if private_public_modules:
            raise ValueError(
                "Public modules must be within the encapsulated modules, but these are not: "
                f"{', '.join(sorted(private_public_modules))}."
            )

        in_scope = self._build_scope_matcher(graph)

        outbound: list[Link] = []
        inbound: list[Link] = []
        for module in sorted(unit):
            for imported in sorted(graph.find_modules_directly_imported_by(module) - unit):
                if in_scope(imported):
                    outbound.append(self._build_link(graph, importer=module, imported=imported))
            if module in public:
                continue
            for importer in sorted(graph.find_modules_that_directly_import(module) - unit):
                if in_scope(importer):
                    inbound.append(self._build_link(graph, importer=importer, imported=module))

        return ContractCheck(
            kept=not (outbound or inbound),
            warnings=list(import_removal.warnings),
            ignored_import_count=import_removal.ignored_import_count,
            # Outbound: imports from the unit to other modules in the project.
            # Inbound: imports into the unit from anywhere other than a public module.
            metadata={"outbound": outbound, "inbound": inbound},
        )

    def render_broken_contract(self, check: ContractCheck) -> None:
        outbound: list[Link] = check.metadata["outbound"]
        inbound: list[Link] = check.metadata["inbound"]

        if outbound:
            output.print_error(
                "Imports out of the encapsulated modules are not allowed:", bold=False
            )
            output.new_line()
            self._render_links(outbound)

        if inbound:
            if self.public_modules:
                heading = (
                    "Imports into the encapsulated modules are only allowed "
                    "via the public modules:"
                )
            else:
                heading = "Imports into the encapsulated modules are not allowed:"
            output.print_error(heading, bold=False)
            output.new_line()
            self._render_links(inbound)

        contract_utils.render_broken_contract_guidance(self.broken_contract_guidance)  # type: ignore

    @staticmethod
    def _render_links(links: list[Link]) -> None:
        for link in links:
            line_numbers = ", ".join(map(str, link["line_numbers"]))
            output.print_error(
                f"- {link['importer']} -> {link['imported']} (l.{line_numbers})", bold=False
            )
            output.new_line()
        output.new_line()

    def _build_scope_matcher(self, graph: grimp.ImportGraph) -> Callable[[str], bool]:
        if self.scope:
            scope_modules = self._get_modules_with_descendants(graph, self.scope)
            return scope_modules.__contains__

        root_packages = [Module(name) for name in self.session_options["root_packages"]]
        return lambda name: any(Module(name).is_in_package(root) for root in root_packages)

    @staticmethod
    def _get_modules_with_descendants(graph: grimp.ImportGraph, expressions) -> set[str]:
        modules = helpers.module_expressions_to_modules(
            graph=graph,
            expressions=expressions,
            as_packages=True,
            raise_if_unmatched=True,
        )
        return {module.name for module in modules}

    @staticmethod
    def _build_link(graph: grimp.ImportGraph, importer: str, imported: str) -> Link:
        import_details = graph.get_import_details(importer=importer, imported=imported)
        return Link(
            importer=importer,
            imported=imported,
            line_numbers=tuple(detail["line_number"] for detail in import_details),
        )
