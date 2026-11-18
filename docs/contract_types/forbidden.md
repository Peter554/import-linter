# Forbidden

_Type name:_ `forbidden`

Forbidden contracts check that one set of modules is not imported by another set of modules.

By default, descendants of each module will be checked - so if `mypackage.one` is forbidden from importing `mypackage.two`, then
`mypackage.one.blue` will be forbidden from importing `mypackage.two.green`. Indirect imports will also be checked. This
descendant behaviour can be changed by setting `as_packages` to `False`: in that case, only explicitly listed modules will be
checked, not their descendants.

External packages may also be forbidden. (Be sure to [configure Import Linter to include external packages](../get_started/configure.md#top-level-configuration)).

## Overlapping modules

Contracts may define `source_modules` and `forbidden_modules` that 'overlap':
either the same module is in both; or one module is a subpackage that contains the other.
This is handled differently depending on the value of `as_packages`:

- When `as_packages` is `True` (the default), imports **within the overlap** are allowed. The overlap is the inner module and
  its descendants. Imports between the overlap and the rest of the outer package are still forbidden. For example:
  - With source module `mypackage` and forbidden module `mypackage.one`, `mypackage.one` is allowed to import
    `mypackage.one.blue`, but `mypackage.two` is _not_ allowed to import `mypackage.one.blue`.
  - With source module `mypackage.one` and forbidden module `mypackage`, `mypackage.one.blue` is allowed to import `mypackage.one`,
    but is _not_ allowed to import `mypackage.two`.
- When `as_packages` is `False`, a source module **is allowed to import itself**, even if it's listed in forbidden modules. For example, a source module
  `mypackage.one` will _not_ be forbidden `mypackage.one`, even if those modules are listed in `forbidden_modules`.

Each source module is checked against each forbidden module separately, equivalent to if they were a separate contract. A wildcard is the same as listing the modules it matches manually.

This situation is most likely to occur when using wildcards. Because each pair is checked separately, a wildcard that
matches modules inside a forbidden module makes each of them a source module that is forbidden from importing the rest of it.
For example, with source modules `mypackage.**` and forbidden module `mypackage.one`, `mypackage.one.blue` is _not_ allowed to
import `mypackage.one.green`. To allow that, add an ignore:
`mypackage.one.** -> mypackage.one.**`. Alternatively, use `mypackage` as the source module, which doesn't forbid imports
within `mypackage.one`.

## Examples

=== "INI"

    ```ini
    [importlinter]
    root_package = mypackage

    [importlinter:contract:my-forbidden-contract]
    name = My forbidden contract (internal packages only)
    type = forbidden
    source_modules =
      mypackage.one
      mypackage.two
      mypackage.three.blue
    forbidden_modules =
      mypackage.four
      mypackage.five.green
    ignore_imports =
      mypackage.one.green -> mypackage.utils
      mypackage.two -> mypackage.four

    [importlinter:contract:forbidden-siblings]
    # This contract prevents mypackage.one from importing
    # anything from its siblings.
    name = Forbidden descendants contract
    type = forbidden
    source_modules =
      mypackage.one
    forbidden_modules =
      mypackage.*

    [importlinter:contract:forbidden-descendants]
    # This contract prevents mypackage.one from importing
    # anything from its descendants.
    # Note as_packages must be false, otherwise the descendants would also be forbidden
    # from importing each other.
    name = Forbidden descendants contract
    type = forbidden
    source_modules =
      mypackage.one
    forbidden_modules =
      mypackage.one.**
    as_packages = false
    ```

    ```ini
    [importlinter]
    root_package = mypackage
    include_external_packages = True

    [importlinter:contract:my-forbidden-contract]
    name = My forbidden contract (internal and external packages)
    type = forbidden
    source_modules =
      mypackage.one
      mypackage.two
    forbidden_modules =
      mypackage.three
      django
      requests
    ignore_imports =
      mypackage.one.green -> sqlalchemy
    ```

=== "TOML"

````toml
[tool.importlinter]
root_package = "mypackage"

    [[tool.importlinter.contracts]]
    name = "My forbidden contract (internal packages only)"
    type = "forbidden"
    source_modules = [
        "mypackage.one",
        "mypackage.two",
        "mypackage.three.blue",
    ]
    forbidden_modules = [
        "mypackage.four",
        "mypackage.five.green",
    ]
    ignore_imports = [
        "mypackage.one.green -> mypackage.utils",
        "mypackage.two -> mypackage.four",
    ]

    [[tool.importlinter.contracts]]
    # This contract prevents mypackage.one from importing
    # anything from its siblings.
    name = "Forbidden siblings contract"
    type = "forbidden"
    source_modules = [
      "mypackage.one",
    ]
    forbidden_modules = [
      "mypackage.*",
    ]

    [[tool.importlinter.contracts]]
    # This contract prevents mypackage.one from importing
    # anything from its descendants.
    # Note as_packages must be False, otherwise the descendants would also be forbidden
    # from importing each other.
    name = "Forbidden descendants contract"
    type = "forbidden"
    source_modules = [
      "mypackage.one",
    ]
    forbidden_modules = [
      "mypackage.one.**",
    ]
    as_packages = False
    ```

    ```toml
    [tool.importlinter]
    root_package = "mypackage"
    include_external_packages = true

    [[tool.importlinter.contracts]]
    name = "My forbidden contract (internal and external packages)"
    type = "forbidden"
    source_modules = [
        "mypackage.one",
        "mypackage.two",
    ]
    forbidden_modules = [
        "mypackage.three",
        "django",
        "requests",
    ]
    ignore_imports = [
        "mypackage.one.green -> sqlalchemy",
    ]
    ```

**Configuration options**

- `source_modules`: A list of modules that should not import the forbidden modules. Supports [wildcards](index.md#wildcards).
- `forbidden_modules`: A list of modules that should not be imported by the source modules. These may include
  root level external packages (i.e. `django`, but not `django.db.models`). If external packages are included,
  the top level configuration must have `include_external_packages = True`. Supports [wildcards](index.md#wildcards).
- `ignore_imports`: See [shared options](index.md#options-used-by-multiple-contracts).
- `unmatched_ignore_imports_alerting`: See [shared options](index.md#options-used-by-multiple-contracts).
- `allow_indirect_imports`: If `True`, allow indirect imports to forbidden modules without interpreting them
  as a reason to mark the contract broken. (Optional.)
- `as_packages`: Whether to treat the source and forbidden modules as packages. If `False`, each of the modules
  passed in will be treated as a module rather than a package. Default behaviour is `True` (treat modules as
  packages).
````
