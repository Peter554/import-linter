## Isolated

*Type name:* `isolated`

Isolated contracts prevent modules from making imports to code outside their boundary.

The `modules` form a single unit, made up of the listed modules and all of their descendants. The modules don't
need to be adjacent: for example, a feature split across a data layer and a domain layer can be one unit. Imports within
the unit are always allowed. The unit may not import any other module in the project, except for the modules in
`allowed_imports` (and their descendants), such as shared utilities.

Imports of external packages are not affected. To restrict those, use a [forbidden](forbidden.md) contract.

Only direct imports are checked. An indirect import has to begin with a direct import out of the unit, which is
reported instead. Imports *into* the unit are not checked: to restrict those, use a [protected](protected.md) contract.

## A unit split across several packages

In a layered project, a feature often doesn't live in one package:

```text
mypackage/
    data/
        billing/
    domain/
        billing/
```

With a `forbidden` contract, saying that billing may not import the rest of the project means listing the
whole project as forbidden, which also matches the other half of the unit. Imports between the two halves then need
ignoring, even though they aren't exceptions. An `isolated` contract can list both halves as one unit instead:

```ini
[importlinter:contract:billing]
name = Billing is isolated
type = isolated
modules =
    mypackage.data.billing
    mypackage.domain.billing
allowed_imports =
    mypackage.utils
```

The two halves can import each other freely. Neither can import the rest of the project, except for `mypackage.utils`.

## Comparison with forbidden

[Forbidden](forbidden.md) contracts can express the same rule, but only by listing what is *not* allowed.

| | `forbidden` | `isolated` |
|---|---|---|
| What is listed | The modules that are *not* allowed to be imported (`forbidden_modules`) | The modules that *are* allowed to be imported (`allowed_imports`) |
| Several modules | Each source module is checked against every forbidden module, so imports between the listed modules need ignoring | The modules form one unit, so imports between them are allowed |
| Indirect imports | Checked, unless `allow_indirect_imports` is set | Not checked: an indirect import always begins with a direct import out of the unit |
| External packages | May be forbidden | Not affected |

To say "billing may only import `mypackage.utils`", a `forbidden` contract needs `forbidden_modules = mypackage.**`
and ignores for the unit's own modules and for `mypackage.utils`. When a new package is added, the rule still holds.
With `isolated`, `allowed_imports` is the only list, and the rule is the same one.

`isolated` is also much faster for this kind of rule. A `forbidden` contract checks every pair of source and forbidden
modules, and `forbidden_modules = mypackage.**` multiplies out, while `isolated` only looks at the imports
that cross the boundary.

**Examples:**

=== "INI"
    ```ini
    [importlinter]
    root_package = mypackage

    [importlinter:contract:domain-is-isolated]
    name = The domain layer doesn't import anything else
    type = isolated
    modules =
        mypackage.domain
    ```

    ```ini
    [importlinter]
    root_package = mypackage

    [importlinter:contract:billing-is-isolated]
    name = Billing only imports shared utilities
    type = isolated
    modules =
        mypackage.data.billing
        mypackage.domain.billing
    allowed_imports =
        mypackage.utils
    ignore_imports =
        mypackage.domain.billing.service -> mypackage.checkout.models
    ```

=== "TOML"
    ```toml
    [tool.importlinter]
    root_package = "mypackage"

    [[tool.importlinter.contracts]]
    name = "The domain layer doesn't import anything else"
    type = "isolated"
    modules = ["mypackage.domain"]
    ```

    ```toml
    [tool.importlinter]
    root_package = "mypackage"

    [[tool.importlinter.contracts]]
    name = "Billing only imports shared utilities"
    type = "isolated"
    modules = [
        "mypackage.data.billing",
        "mypackage.domain.billing",
    ]
    allowed_imports = ["mypackage.utils"]
    ignore_imports = [
        "mypackage.domain.billing.service -> mypackage.checkout.models",
    ]
    ```

**Configuration options**

- `modules`: The modules that make up the unit. Descendants are included. Supports [wildcards](index.md#wildcards).
- `allowed_imports`: Modules that the unit is allowed to import, such as shared utilities. Descendants are included.
  These must be outside `modules`, although a parent package of the unit may be listed, which allows importing anything
  else in that package. Supports [wildcards](index.md#wildcards). (Optional.)
- `ignore_imports`: See [shared options](index.md#options-used-by-multiple-contracts). (Optional.)
- `unmatched_ignore_imports_alerting`: See [shared options](index.md#options-used-by-multiple-contracts). (Optional.)
- `broken_contract_guidance`: See [shared options](index.md#options-used-by-multiple-contracts). (Optional.)

**Sample output**

```text
Billing only imports shared utilities
-------------------------------------

Imports out of the modules are not allowed:

- mypackage.domain.billing.service -> mypackage.checkout.models (l.3)

- mypackage.data.billing.repository -> mypackage.accounts (l.12, 27)
```
