import itertools
import re
from typing import Iterable, List, Pattern, Set, Tuple

from grimp import DetailedImport, ImportGraph

from importlinter.domain.imports import (
    DirectImport,
    ImportExpression,
    Module,
    ModuleExpression,
)


class MissingImport(Exception):
    pass


def pop_imports(graph: ImportGraph, imports: Iterable[DirectImport]) -> List[DetailedImport]:
    """
    Removes the supplied direct imports from the graph.

    Returns:
        The list of import details that were removed, including any additional metadata.

    Raises:
        MissingImport if an import is not present in the graph.
    """
    removed_imports: List[DetailedImport] = []

    imports_to_remove = _dedupe_imports(imports)

    for import_to_remove in imports_to_remove:
        import_details = graph.get_import_details(
            importer=import_to_remove.importer.name,
            imported=import_to_remove.imported.name,
        )
        if not import_details:
            raise MissingImport(f"Ignored import {import_to_remove} not present in the graph.")

        graph.remove_import(
            importer=import_to_remove.importer.name,
            imported=import_to_remove.imported.name,
        )

        removed_imports.extend(import_details)

    return removed_imports


def import_expression_to_imports(
    graph: ImportGraph, expression: ImportExpression
) -> List[DirectImport]:
    """
    Returns a list of imports in a graph, given some import expression.

    Raises:
        MissingImport if an import is not present in the graph. For a wildcarded import expression,
        this is raised if there is not at least one match.
    """
    imports: Set[DirectImport] = set()
    matched = False

    importers = module_expression_to_modules(graph, expression.importer)
    importeds = module_expression_to_modules(graph, expression.imported)
    for importer, imported in itertools.product(importers, importeds):
        import_details = graph.get_import_details(importer=importer.name, imported=imported.name)

        if import_details:
            for individual_import_details in import_details:
                imports.add(
                    DirectImport(
                        importer=Module(individual_import_details["importer"]),
                        imported=Module(individual_import_details["imported"]),
                        line_number=individual_import_details["line_number"],
                        line_contents=individual_import_details["line_contents"],
                    )
                )
            matched = True

    if not matched:
        raise MissingImport(
            f"Ignored import expression {expression} didn't match anything in the graph."
        )

    return list(imports)


def module_expressions_to_modules(
    graph: ImportGraph, expressions: Iterable[ModuleExpression]
) -> Set[Module]:
    modules = set()
    for expression in expressions:
        modules |= module_expression_to_modules(graph, expression)
    return modules


def module_expression_to_modules(graph: ImportGraph, expression: ModuleExpression) -> Set[Module]:
    if not expression.has_wildcard_expression():
        return {Module(expression.expression)}

    pattern = _to_pattern(expression.expression)

    modules = set()
    for module in graph.modules:
        if pattern.match(module):
            modules.add(Module(module))

    return modules


def import_expressions_to_imports(
    graph: ImportGraph, expressions: Iterable[ImportExpression]
) -> List[DirectImport]:
    """
    Returns a list of imports in a graph, given some import expressions.

    Raises:
        MissingImport if an import is not present in the graph. For a wildcarded import expression,
        this is raised if there is not at least one match.
    """
    return list(
        set(
            itertools.chain(
                *(import_expression_to_imports(graph, expression) for expression in expressions)
            )
        )
    )


def resolve_import_expressions(
    graph: ImportGraph, expressions: Iterable[ImportExpression]
) -> Tuple[Set[DirectImport], Set[ImportExpression]]:
    """
    Find any imports in the graph that match the supplied import expressions.

    Returns tuple of:
        - Set of resolved imports.
        - Set of import expressions that didn't match any imports.
    """
    resolved_imports = set()
    unresolved_expressions = set()

    for expression in expressions:
        try:
            resolved_imports.update(import_expression_to_imports(graph, expression))
        except MissingImport:
            unresolved_expressions.add(expression)

    return (resolved_imports, unresolved_expressions)


def pop_import_expressions(
    graph: ImportGraph, expressions: Iterable[ImportExpression]
) -> List[DetailedImport]:
    """
    Removes any imports matching the supplied import expressions from the graph.

    Returns:
        The list of imports that were removed, including any additional metadata.
    Raises:
        MissingImport if an import is not present in the graph. For a wildcarded import expression,
        this is raised if there is not at least one match.
    """
    imports = import_expressions_to_imports(graph, expressions)
    return pop_imports(graph, imports)


def add_imports(graph: ImportGraph, import_details: List[DetailedImport]) -> None:
    """
    Adds the supplied import details to the graph.

    Intended to be the reverse of pop_imports, so the following code should leave the
    graph unchanged:

        import_details = pop_imports(graph, imports)
        add_imports(graph, import_details)
    """
    for details in import_details:
        assert isinstance(details["importer"], str)
        assert isinstance(details["imported"], str)
        assert isinstance(details["line_number"], int)
        assert isinstance(details["line_contents"], str)
        graph.add_import(
            importer=details["importer"],
            imported=details["imported"],
            line_number=details["line_number"],
            line_contents=details["line_contents"],
        )


def _dedupe_imports(imports: Iterable[DirectImport]) -> Iterable[DirectImport]:
    """
    Return the imports with the metadata and any duplicates removed.

    For example:

        _dedupe_imports([
            DirectImport(
                importer="blue",
                imported="green",
                line_number=1,
                line_contents="from blue import green.one",
            ),
            DirectImport(
                importer="blue",
                imported="green",
                line_number=3,
                line_contents="from blue import green.two",
            ),
        ]) == {
            DirectImport(
                importer="blue",
                imported="green",
            ),
        }

    This is to make it easy for the calling function to remove the set of imports from a graph
    without attempting to remove certain imports twice.
    """
    imports_without_metadata = {
        DirectImport(imported=i.imported, importer=i.importer) for i in imports
    }
    # Why don't we return a set here? Because we want to preserve the order to make it
    # more deterministic.
    return sorted(imports_without_metadata, key=lambda di: (di.importer.name, di.imported.name))


def _to_pattern(expression: str) -> Pattern:
    """
    Function which translates an import expression into a regex pattern.
    """
    pattern_parts = []
    for part in expression.split("."):
        if "*" == part:
            pattern_parts.append(part.replace("*", r"[^\.]+"))
        elif "**" == part:
            pattern_parts.append(part.replace("*", r"[^\.]+(?:\.[^\.]+)*?"))
        else:
            pattern_parts.append(part)
    return re.compile(r"^" + r"\.".join(pattern_parts) + r"$")
