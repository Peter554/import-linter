## Independence

*Type name:* `independence`

Independence contracts check that a set of modules do not depend on each other.

They do this by checking that there are no imports in any direction between the modules, even indirectly.

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
      <td><code>modules</code></td>
      <td>Yes</td>
      <td>A list of modules/subpackages that should be independent of each other.
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
  </tbody>
</table>

### Example contracts


=== "INI"
    
    ```ini
    [importlinter:contract:my-independence-contract]
    name = My independence contract
    type = independence
    modules =
        mypackage.foo
        mypackage.bar
        mypackage.baz
    ignore_imports =
        mypackage.bar.green -> mypackage.utils
        mypackage.baz.blue -> mypackage.foo.purple
    ```

=== "TOML"
    ```toml
    [[tool.importlinter.contracts]]
    name = "My independence contract"
    type = "independence"
    modules = [
        "mypackage.foo",
        "mypackage.bar",
        "mypackage.baz",
    ]
    ignore_imports = [
        "mypackage.bar.green -> mypackage.utils",
        "mypackage.baz.blue -> mypackage.foo.purple",
    ]
    ```
