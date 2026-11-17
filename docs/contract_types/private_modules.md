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
Supports <a href="../#wildcards">wildcards</a>.
        <br><br>
      For more guidance see <a href="#limiting-which-modules-are-treated-as-private">limiting which modules are treated as private</a>.
    </td>
    </tr>
    <tr>
      <td><code>ignore_imports</code></td>
      <td>No</td>
      <td>See <a href="../#options-used-by-multiple-contracts">shared options</a>.</td>
    </tr>
    <tr>
      <td><code>unmatched_ignore_imports_alerting</code></td>
      <td>No</td>
      <td>See <a href="../#options-used-by-multiple-contracts">shared options</a>.</td>
    </tr>
    <tr>
      <td><code>broken_contract_guidance</code></td>
      <td>No</td>
      <td>See <a href="../#options-used-by-multiple-contracts">shared options</a>.</td>
    </tr>
  </tbody>
</table>

## How privacy works

Modules starting with a leading underscore are treated as 'private', except for dunder modules (such as `__main__.py`).

A private module is scoped to its parent package.
Modules outside that parent package may not import it or its descendants.

#### Examples

| Importer                | Imported                       | Allowed? | Notes                                                                                                                  |
|-------------------------|--------------------------------|----------|------------------------------------------------------------------------------------------------------------------------|
| `mypackage._private`    | `mypackage.public`             | Yes      | Private modules can import public modules.                                                                             |
| `mypackage.public`      | `mypackage._private`           | Yes      | Private modules can be imported by siblings.                                                                           |
| `mypackage.green`       | `mypackage.green._private`     | Yes      | A package (`__init__.py`) may import its own private children.                                                         |
| `mypackage.public.blue` | `mypackage._private.green`     | Yes      | The importer is within `_private`'s parent package (`mypackage`), so it may import `_private` and its descendants.       |
| `mypackage.blue`        | `mypackage.green._private`     | No       | The importer is outside `_private`'s parent package (`mypackage.green`).                                               |
| `mypackage.blue`        | `mypackage._private._green`    | No       | Although `mypackage._private` is accessible, the importer is outside `_green`'s parent package (`mypackage._private`). |
| `mypackage.blue`        | `mypackage.green._private.red` | No       | The importer cannot import descendants of an inaccessible private module (`mypackage.green._private`).                   |

## Indirect imports

Only direct imports are checked. If `mypackage.blue` imports `mypackage.green.public`, which imports
`mypackage.green._private`, nothing is violated.

## Limiting which modules are treated as private

By default, this contract applies to every module in `root_packages`.

The optional `packages_with_private_modules` option narrows down which modules are treated as private.
Only private modules inside the listed packages (including their descendants) are checked. All modules in
`root_packages` will be prevented from importing those private modules according to the privacy rules.

The listed packages must not themselves be private, or be inside a private module. That is, no component of the
package name may start with an underscore (dunder names such as `__main__` aren't private, so are allowed).
For example, `mypackage.green` is valid, but `mypackage.green._private` and `mypackage._private.blue` are not.
To check the private modules inside `mypackage._private`, list an ancestor such as `mypackage` instead.

The same applies to packages matched by wildcards: if a wildcard expression matches a private package, or a package
inside a private module, the contract raises an error. This means that the result depends on the modules in your
package, not just on your configuration. For example, `mypackage.*` is valid until `mypackage._helpers` is added, and
`mypackage.**` is invalid as soon as there are any private modules. Where this happens, list the non-private ancestor
instead (e.g. `mypackage` rather than `mypackage.**`).

### Example import

Let's say that `mypackage.blue` imports `mypackage.green._private`.
This table shows how the value of `packages_with_private_modules` affects whether that import is allowed.

| `packages_with_private_modules` | Is the import allowed? | Notes                                                                               |
|---------------------------------|------------------------|-------------------------------------------------------------------------------------|
| Not supplied                    | No                     | By default, `mypackage.green._private` is treated as private.                       |
| `["mypackage.green"]`           | No                     | `_private` is contained within the configured package, so it's treated as private.  |
| `["mypackage.blue"]`            | Yes                    | `mypackage.green._private` is not inside the configured package, so it isn't checked. |

## Example contracts

=== "INI"
    ```ini
    [importlinter]
    root_package = mypackage

    [importlinter:contract:my-contract]
    name = Private modules
    type = private_modules
    packages_with_private_modules =
        mypackage.green
    ignore_imports =
        mypackage.blue -> mypackage.green._private
    ```

=== "TOML"
    ```toml
    [tool.importlinter]
    root_package = "mypackage"

    [[tool.importlinter.contracts]]
    name = "Private modules"
    type = "private_modules"
    packages_with_private_modules = ["mypackage.green"]
    ignore_imports = [
        "mypackage.blue -> mypackage.green._private",
    ]
    ```

## Sample output

```text
Private modules
---------------

Private modules may only be imported from within their parent package:

- mypackage.blue -> mypackage.green._private (l.3)
```
