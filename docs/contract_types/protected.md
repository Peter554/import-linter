## Protected modules

*Type name:* `protected`

Protected contracts prevent modules from being directly imported, except by modules in an allow-list.
By default, descendants of each module will be checked too.

For example, if `blue` is protected, and `green` is the only module in the allow list,
then no module other than `green` (and its descendants) will be allowed to import `blue` (and its descendants) directly.

External packages may also be protected. (Be sure to [configure Import Linter to include external packages](../get_started/configure.md#top-level-configuration)).

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
      <td><code>protected_modules</code></td>
      <td>Yes</td>
      <td>The modules that must not be imported except by the list of allowed importers.
      If <code>as_packages</code> is <code>True</code>, descendants of a protected module are also allowed to import each other.
      For example, in the <em>Simple protected contract</em> below, <code>foo.protected.green</code> is allowed to import
      <code>foo.protected.blue</code>, but <code>foo.red</code> and <code>foo.also_protected.yellow</code> are not.
    <br><br>
Supports <a href="index.md#wildcards">wildcards</a>.</td>
    </tr>
    <tr>
      <td><code>allowed_importers</code></td>
      <td>Yes</td>
      <td>The only modules allowed to import the target modules.
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
      <td><code>as_packages</code></td>
      <td>No</td>
      <td>Whether to treat the protected modules as packages. If <code>False</code>, each of the modules
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
    
    [importlinter:contract:simple-protected-contract]
    name = Simple protected contract
    type = protected
    protected_modules =
        foo.protected
        foo.also_protected
    allowed_importers =
        foo.allowed
        foo.also_allowed
    ```
    
    ```ini
    [importlinter]
    root_package = foo
    
    [importlinter:contract:models-can-only-be-imported-by-colors]
    name = Models can only be imported by colors direct descendant
    type = protected
    protected_modules =
        foo.**.models
    allowed_importers =
        foo.colors.*
    ignore_imports =
        foo.one.green -> foo.one.models
        foo.colors.red.bar -> foo.three.models
    as_packages = False
    ```

    ```ini
    [importlinter]
    root_package = foo
    include_external_packages = True
    
    [importlinter:contract:protected-boto]
    name = Boto can only be imported by foo.allowed
    type = protected
    protected_modules = boto
    allowed_importers = foo.allowed
    ```

=== "TOML"

    ```toml
    [tool.importlinter]
    root_package = "foo"

    [[tool.importlinter.contracts]]
    name = "Simple protected contract"
    type = "protected"
    protected_modules = [
        "foo.protected",
        "foo.also_protected",
    ]
    allowed_importers = [
        "foo.allowed",
        "foo.also_allowed",
    ]
    ```

    ```toml
    [tool.importlinter]
    root_package = "foo"

    [[tool.importlinter.contracts]]
    name = "Models can only be imported by colors direct descendant"
    type = "protected"
    protected_modules = [
        "foo.**.models",
    ]
    allowed_importers = [
        "foo.colors.*",
    ]
    ignore_imports = [
        "foo.one.green -> foo.one.models",
        "foo.colors.red.bar -> foo.three.models",
    ]
    as_packages = false
    ```

    ```toml
    [tool.importlinter]
    root_package = "foo"
    include_external_packages = true
    
    [[tool.importlinter.contracts]]
    name = "Boto can only be imported by foo.allowed"
    type = "protected"
    protected_modules = ["boto"]
    allowed_importers = ["foo.allowed"]
    ```
