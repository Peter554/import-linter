## Forbidden

*Type name:* `forbidden`

Forbidden contracts check that one set of modules is not imported by another set of modules.

By default, descendants of each module will be checked - so if `foo.one` is forbidden from importing `foo.two`, then
`foo.one.blue` will be forbidden from importing `foo.two.green`. Indirect imports will also be checked. This
descendant behaviour can be changed by setting `as_packages` to `False`: in that case, only explicitly listed modules will be
checked, not their descendants.

External packages may also be forbidden.  (Be sure to [configure Import Linter to include external packages](../get_started/configure.md#top-level-configuration)).

### Configuration options

<table>
  <thead>
    <tr>
      <th>Option</th>
      <th>Required?</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>source_modules</code></td>
      <td>Yes</td>
      <td>A list of modules that should not import the forbidden modules.
    <br><br>
Supports <a href="index.md#wildcards">wildcards</a>.</td>
    </tr>
    <tr>
      <td><code>forbidden_modules</code></td>
      <td>Yes</td>
      <td>A list of modules that should not be imported by the source modules. These may include
      root level external packages (i.e. <code>django</code>, but not <code>django.db.models</code>).
      If external packages are included, the top level configuration must have <code>include_external_packages = True</code>.
    <br><br>
Supports <a href="index.md#wildcards">wildcards</a>.</td>
    </tr>
    <tr>
      <td><code>ignore_imports</code></td>
      <td>No</td>
      <td>See <a href="index.md#options-used-by-multiple-contracts">shared options</a>.</td>
    </tr>
    <tr>
      <td><code>unmatched_ignore_imports_alerting</code></td>
      <td>No</td>
      <td>See <a href="index.md#options-used-by-multiple-contracts">shared options</a>.</td>
    </tr>
    <tr>
      <td><code>broken_contract_guidance</code></td>
      <td>No</td>
      <td>See <a href="index.md#options-used-by-multiple-contracts">shared options</a>.</td>
    </tr>
    <tr>
      <td><code>allow_indirect_imports</code></td>
      <td>No</td>
      <td>If <code>True</code>, allow indirect imports to forbidden modules without interpreting them
      as a reason to mark the contract broken.</td>
    </tr>
    <tr>
      <td><code>as_packages</code></td>
      <td>No</td>
      <td>Whether to treat the source and forbidden modules as packages. If <code>False</code>, each of the modules
      passed in will be treated as a module rather than a package. Default behaviour is <code>True</code> (treat modules as
      packages).</td>
    </tr>
  </tbody>
</table>

### Example contracts


=== "INI"

    ```ini
    [importlinter]
    root_package = foo
    
    [importlinter:contract:my-forbidden-contract]
    name = My forbidden contract (internal packages only)
    type = forbidden
    source_modules =
      foo.one
      foo.two
      foo.three.blue
    forbidden_modules =
      foo.four
      foo.five.green
    ignore_imports =
      foo.one.green -> foo.utils
      foo.two -> foo.four

    [importlinter:contract:forbidden-siblings]
    # This contract prevents foo.one from importing
    # anything from its siblings.
    name = Forbidden descendants contract
    type = forbidden
    source_modules =
      foo.one
    forbidden_modules =
      foo.*

    [importlinter:contract:forbidden-descendants]
    # This contract prevents foo.one from importing
    # anything from its descendants.
    # Note as_packages must be false, otherwise this contract would have no effect
    # due to the rules around overlapping modules.
    name = Forbidden descendants contract
    type = forbidden
    source_modules =
      foo.one
    forbidden_modules =
      foo.one.**
    as_packages = false
    ```

    ```ini
    [importlinter]
    root_package = foo
    include_external_packages = True
    
    [importlinter:contract:my-forbidden-contract]
    name = My forbidden contract (internal and external packages)
    type = forbidden
    source_modules =
      foo.one
      foo.two
    forbidden_modules =
      foo.three
      django
      requests
    ignore_imports =
      foo.one.green -> sqlalchemy
    ```

=== "TOML"
    ```toml
    [tool.importlinter]
    root_package = "foo"

    [[tool.importlinter.contracts]]
    name = "My forbidden contract (internal packages only)"
    type = "forbidden"
    source_modules = [
        "foo.one",
        "foo.two",
        "foo.three.blue",
    ]
    forbidden_modules = [
        "foo.four",
        "foo.five.green",
    ]
    ignore_imports = [
        "foo.one.green -> foo.utils",
        "foo.two -> foo.four",
    ]
    
    [[tool.importlinter.contracts]]
    # This contract prevents foo.one from importing
    # anything from its siblings.
    name = "Forbidden siblings contract"
    type = "forbidden"
    source_modules = [
      "foo.one",
    ]
    forbidden_modules = [
      "foo.*",
    ]

    [[tool.importlinter.contracts]]
    # This contract prevents foo.one from importing
    # anything from its descendants.
    # Note as_packages must be False, otherwise this contract would have no effect
    # due to the rules around overlapping modules.
    name = "Forbidden descendants contract"
    type = "forbidden"
    source_modules = [
      "foo.one",
    ]
    forbidden_modules = [
      "foo.one.**",
    ]
    as_packages = False
    ```

    ```toml
    [tool.importlinter]
    root_package = "foo"
    include_external_packages = true

    [[tool.importlinter.contracts]]
    name = "My forbidden contract (internal and external packages)"
    type = "forbidden"
    source_modules = [
        "foo.one",
        "foo.two",
    ]
    forbidden_modules = [
        "foo.three",
        "django",
        "requests",
    ]
    ignore_imports = [
        "foo.one.green -> sqlalchemy",
    ]
    ```

## Overlapping modules

Contracts may define `source_modules` and `forbidden_modules` that 'overlap':
either the same module is in both; or one module is a subpackage that contains the other.
This is handled differently depending on the value of `as_packages`:

- When `as_packages` is `True` (the default), the source module is allowed to import the forbidden module **if they share descendants**. For example,
`foo.one` will *not* be forbidden from importing `foo.one.blue`, or `foo.one` itself, even if
those modules are listed in `forbidden_modules`.
- When `as_packages` is `False`, a source module **is allowed to import itself**, even if it's listed in forbidden modules.  For example, a source module
`foo.one` will *not* be forbidden `foo.one`, even if those modules are listed in `forbidden_modules`.

This situation is most likely to occur when using wildcards.
