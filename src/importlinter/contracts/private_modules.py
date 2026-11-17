from __future__ import annotations

import grimp

from importlinter.application import contract_utils, output
from importlinter.domain import fields, helpers
from importlinter.domain.contract import Contract, ContractCheck, InvalidContractOptions

from ._common import Link


class PrivateModulesContract(Contract):
    """
    Private modules contracts check that private modules are only imported from within their
    parent package.

    A module is private if the last component of its name starts with an underscore,
    e.g. mypackage.foo._bar. (Names like __main__ are not private.) The descendants of a private
    module are covered too.

    A private module may only be imported by its parent package (e.g. mypackage.foo) or by a
    descendant of its parent package, however deeply nested.

    The packages in packages_with_private_modules must not be private, or inside a private module:
    no component of their names may start with an underscore. This applies to any packages matched
    by wildcards too, so e.g. mypackage.** is only valid if mypackage contains no private modules;
    list mypackage instead. To check the private modules inside mypackage._private, list an
    ancestor such as mypackage instead.

    Configuration options:

        - packages_with_private_modules:
                          The packages whose private modules should be checked. Imports of any
                          other modules are not checked. If not supplied, the private modules in
                          all of the root packages are checked.
                          (Optional.)
        - ignore_imports: A set of ImportExpressions. These imports will be ignored: if the import
                          would cause a contract to be broken, adding it to the set will cause
                          the contract be kept instead. (Optional.)
        - unmatched_ignore_imports_alerting: Decides how to report when the expression in the
                          `ignore_imports` set is not found in the graph. Valid values are
                          "none", "warn", "error". Default value is "error".
        - broken_contract_guidance: Guidance explaining how to fix the contract if it's broken.
                          These are displayed after the contract's violations. (Optional.)
    """

    type_name = "private_modules"

    packages_with_private_modules = fields.SetField(
        subfield=fields.ModuleExpressionField(), required=False
    )
    ignore_imports = fields.SetField(subfield=fields.ImportExpressionField(), required=False)
    unmatched_ignore_imports_alerting = fields.EnumField(
        contract_utils.AlertLevel, default=contract_utils.AlertLevel.ERROR
    )
    broken_contract_guidance = fields.TextField(required=False)

    def validate(self) -> None:
        private_packages = sorted(
            expression.expression
            for expression in self.packages_with_private_modules or ()  # type: ignore
            if _has_private_component(expression.expression)
        )
        if private_packages:
            listed = ", ".join(repr(package) for package in private_packages)
            raise InvalidContractOptions(
                {
                    "packages_with_private_modules": (
                        f"Packages cannot be private or inside a private module: {listed}. "
                        "List an ancestor that isn't private instead."
                    )
                }
            )

    def check(self, graph: grimp.ImportGraph, verbose: bool) -> ContractCheck:
        import_removal = contract_utils.remove_ignored_imports_and_report(
            graph=graph,
            ignore_imports=self.ignore_imports,  # type: ignore
            unmatched_alerting=self.unmatched_ignore_imports_alerting,  # type: ignore
        )

        modules_to_check = self._get_modules_to_check_imports_of(graph)
        illegal_imports: set[tuple[str, str]] = set()
        for imported_module in sorted(modules_to_check):
            illegal_imports |= _find_illegal_imports(imported_module=imported_module, graph=graph)

        links = [
            _build_link(graph, importer=importer, imported=imported)
            for importer, imported in sorted(illegal_imports)
        ]
        return ContractCheck(
            kept=not links,
            warnings=list(import_removal.warnings),
            ignored_import_count=import_removal.ignored_import_count,
            metadata={"illegal_imports": links},
        )

    def _get_modules_to_check_imports_of(self, graph: grimp.ImportGraph) -> set[str]:
        if not self.packages_with_private_modules:
            return set(graph.modules)
        modules: set[str] = set()
        for expression in self.packages_with_private_modules:  # type: ignore
            matched = helpers.module_expression_to_modules(
                graph=graph,
                expression=expression,
                as_packages=False,
                raise_if_unmatched=True,
            )
            # Wildcards can match modules that the validation of literal names would reject.
            private_matches = sorted(
                module.name for module in matched if _has_private_component(module.name)
            )
            if private_matches:
                listed = ", ".join(repr(name) for name in private_matches)
                raise ValueError(
                    f"The expression '{expression}' in packages_with_private_modules matched "
                    f"packages that are private or inside a private module: {listed}. "
                    "Packages cannot be private or inside a private module. "
                    "List an ancestor that isn't private instead."
                )
            modules |= {module.name for module in matched}
            modules |= {
                descendant
                for module in matched
                for descendant in graph.find_descendants(module.name)
            }
        return modules

    def render_broken_contract(self, check: ContractCheck) -> None:
        output.print_error(
            "Private modules may only be imported from within their parent package:",
            bold=False,
        )
        output.new_line()
        links: list[Link] = check.metadata["illegal_imports"]
        for link in links:
            line_numbers = ", ".join(map(str, link["line_numbers"]))
            output.print_error(
                f"- {link['importer']} -> {link['imported']} (l.{line_numbers})",
                bold=False,
            )
            output.new_line()
        contract_utils.render_broken_contract_guidance(self.broken_contract_guidance)  # type: ignore


def _is_private_module(module: str) -> bool:
    """
    Return whether the last component of the module's name starts with an underscore, unless it's
    a dunder name (e.g. __main__).

    Top level modules are never private, as they have no parent package to be private to.
    """
    if "." not in module:
        return False
    return _is_private_name(module.rsplit(".", maxsplit=1)[-1])


def _has_private_component(module: str) -> bool:
    """
    Return whether any component of the module's name is private (see _is_private_name).

    Unlike _is_private_module, this includes the top level component.
    """
    return any(_is_private_name(component) for component in module.split("."))


def _is_private_name(name: str) -> bool:
    """
    Return whether a single module name component starts with an underscore, unless it's a dunder
    name (e.g. __main__).
    """
    return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def _find_illegal_imports(imported_module: str, graph: grimp.ImportGraph) -> set[tuple[str, str]]:
    """
    Return the (importer, imported) pairs that break the privacy rules for the imported module.

    These are the imports of the module from outside the parent package of its innermost private
    module (the module itself, or its closest private ancestor).

    The innermost private module has the strictest scope: anything within its parent package is
    also within the parent package of any private module further out. A module that is not
    private, and has no private ancestors, can be imported from anywhere.
    """
    parent = _get_parent_of_innermost_private_module(imported_module)
    if parent is None:
        return set()

    # The trailing dot prevents e.g. mypackage.foobar being treated as a descendant of
    # mypackage.foo.
    parent_prefix = f"{parent}."
    return {
        (importer, imported_module)
        for importer in graph.find_modules_that_directly_import(imported_module)
        if importer != parent and not importer.startswith(parent_prefix)
    }


def _get_parent_of_innermost_private_module(module: str) -> str | None:
    """
    Return the parent of the module's innermost private module, or None if there isn't one.
    """
    components = module.split(".")
    # Index 0 is the top level module, which is never private.
    for index in range(len(components) - 1, 0, -1):
        if _is_private_name(components[index]):
            return ".".join(components[:index])
    return None


def _build_link(graph: grimp.ImportGraph, importer: str, imported: str) -> Link:
    import_details = graph.get_import_details(importer=importer, imported=imported)
    return Link(
        importer=importer,
        imported=imported,
        line_numbers=tuple(detail["line_number"] for detail in import_details),
    )
