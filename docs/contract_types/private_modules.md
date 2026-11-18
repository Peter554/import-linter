## Private modules

*Type name:* `private_modules`

This contract scopes 'private' modules (ones named with a leading underscore) to their parent package.
Nothing outside that scope is allowed to import them or their descendants.

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
      <td><code>packages_with_private_modules</code></td>
      <td>No</td>
      <td>Limits the contract to the private modules inside these packages.
      Imports of those private modules are checked wherever they come from, including from outside modules.
    <br><br>
Supports <a href="index.md#wildcards">wildcards</a>.
        <br><br>
      For more guidance see <a href="#limiting-which-modules-are-treated-as-private">limiting which modules are treated as private</a>.
    </td>
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
  </tbody>
</table>

### Example contracts

=== "INI"
    ```ini
    [importlinter]
    root_package = foo

    [importlinter:contract:contract-one]
    name = Private modules everywhere
    type = private_modules

    [importlinter:contract:contract-two]
    name = Private modules in green
    type = private_modules
    packages_with_private_modules = foo.green
    ignore_imports =
        foo.blue -> foo.green._private
    ```

=== "TOML"
    ```toml
    [tool.importlinter]
    root_package = "foo"

    [[tool.importlinter.contracts]]
    name = "Private modules everywhere"
    type = "private_modules"

    [[tool.importlinter.contracts]]
    name = "Private modules in green"
    type = "private_modules"
    packages_with_private_modules = ["foo.green"]
    ignore_imports = [
        "foo.blue -> foo.green._private",
    ]
    ```

### Sample output

```text
Private modules
---------------

Private modules may only be imported from within their parent package:

- foo.orange -> foo.green._private (l.3)
```


## How privacy works

Modules starting with a leading underscore are treated as 'private', except for dunder modules (such as `__main__.py`).

A private module is scoped to its parent package.
Modules outside that parent package may not import it or its descendants.

#### Examples

| Importer                | Imported                       | Allowed? | Notes                                                                                                                  |
|-------------------------|--------------------------------|----------|------------------------------------------------------------------------------------------------------------------------|
| `foo._private`    | `foo.public`             | Yes      | Private modules can import public modules.                                                                             |
| `foo.public`      | `foo._private`           | Yes      | Private modules can be imported by siblings.                                                                           |
| `foo.green`       | `foo.green._private`     | Yes      | A package (`__init__.py`) may import its own private children.                                                         |
| `foo.public.blue` | `foo._private.green`     | Yes      | The importer is within `_private`'s parent package (`foo`), so it may import `_private` and its descendants.       |
| `foo.blue`        | `foo.green._private`     | No       | The importer is outside `_private`'s parent package (`foo.green`).                                               |
| `foo.blue`        | `foo._private._green`    | No       | Although `foo._private` is accessible, the importer is outside `_green`'s parent package (`foo._private`). |
| `foo.blue`        | `foo.green._private.red` | No       | The importer cannot import descendants of an inaccessible private module (`foo.green._private`).                   |

## Indirect imports

Only direct imports are checked. If `foo.blue` imports `foo.green.public`, which imports
`foo.green._private`, nothing is violated.

## Limiting which modules are treated as private

By default, this contract applies to every module included in [the top level configuration](../get_started/configure.md#top-level-configuration)
(that is, `root_package` or `root_packages`).

The optional `packages_with_private_modules` option narrows down which modules are treated as private.
Only private modules inside the listed packages (including their descendants) are checked. All modules in
`root_packages` will be prevented from importing those private modules according to the privacy rules.

### Examples

Let's say that `foo.blue` imports `foo.green._private`.
This table shows how the value of `packages_with_private_modules` affects whether that import is allowed.

| `packages_with_private_modules` | Is the import allowed? | Notes                                                                               |
|---------------------------------|------------------------|-------------------------------------------------------------------------------------|
| Not supplied                    | No                     | By default, `foo.green._private` is treated as private.                       |
| `["foo.green"]`           | No                     | `_private` is contained within the configured package, so it's treated as private.  |
| `["foo.blue"]`            | Yes                    | `foo.green._private` is not inside the configured package, so it isn't checked. |

!!! warning "Specifying packages that are themselves private"

    You are not allowed to include packages that are themselves private in this list.
    For example, `foo.green._private` and `foo._private.blue` are invalid `packages_with_private_modules`.

    This means you need to exercise caution when using wildcards in this option:
    the contract will be invalidated by a later addition of a private module, if it matches the wildcard.
    For example, `foo.*` is valid until `foo._helpers` is added.
    It's usually better to list the non-private ancestor instead (e.g. `foo` rather than `foo.*`).
