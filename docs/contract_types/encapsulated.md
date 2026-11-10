## Encapsulated modules

*Type name:* `encapsulated`

Encapsulated contracts treat a set of modules as a single unit, and prevent imports across its boundary
except in the ways you allow:

- The unit must not import any other module in your project.
- Other modules must not import the unit, except for its public modules.

The unit is made up of the listed `modules` and all of their descendants. The modules don't have to be next to each
other, so you can keep a feature together as one unit even when it is split across the layers of your project.

For example, a billing feature might be split between a data layer and a domain layer:

```text
mypackage/
    data/
        billing/
        orders/
    domain/
        billing/
            api.py
        orders/
```

If `mypackage.data.billing` and `mypackage.domain.billing` are encapsulated together, with
`mypackage.domain.billing.api` as their only public module, then:

- Modules in `mypackage.data.billing` and `mypackage.domain.billing` may import each other, in either direction.
- Neither may import anything else in `mypackage`, such as `mypackage.data.orders`.
- Modules outside the unit may import `mypackage.domain.billing.api` (and its descendants), but not the rest of the
  unit.

Parent packages of the unit are outside it, like any other module. In this example, `mypackage.data` may not import
`mypackage.data.billing`, so `mypackage/data/__init__.py` can't re-export anything from it.

By default these rules apply to every root package of your project. Imports of external packages are not affected.

To apply them to only part of your project, use the `scope` option, for example if the unit is allowed to use a shared
library in another root package. Only modules in the scope are considered: imports across the boundary with a module
outside the scope are ignored, in both directions.

Only direct imports are checked. An indirect import always begins or ends with a direct import across the boundary of
the unit, and that is what will be reported.

To allow exceptions, use `ignore_imports`.

**Examples:**

=== "INI"
    ```ini
    [importlinter]
    root_package = mypackage

    [importlinter:contract:orders-are-encapsulated]
    name = Orders are encapsulated
    type = encapsulated
    modules =
        mypackage.orders
    public_modules =
        mypackage.orders.api
    ```

    ```ini
    [importlinter]
    root_package = mypackage

    [importlinter:contract:billing-is-encapsulated]
    name = Billing is encapsulated
    type = encapsulated
    modules =
        mypackage.data.billing
        mypackage.domain.billing
    public_modules =
        mypackage.domain.billing.api
    ignore_imports =
        mypackage.checkout.views -> mypackage.domain.billing.models
        mypackage.domain.billing.tasks -> mypackage.notifications.email
    ```

    ```ini
    [importlinter]
    root_packages =
        mypackage
        sharedlibrary

    [importlinter:contract:shipping-is-encapsulated]
    name = Shipping is encapsulated
    type = encapsulated
    modules =
        mypackage.shipping
    public_modules =
        mypackage.shipping.api
    # Shipping may use sharedlibrary, so only consider mypackage.
    scope =
        mypackage
    ```

=== "TOML"

    ```toml
    [tool.importlinter]
    root_package = "mypackage"

    [[tool.importlinter.contracts]]
    name = "Orders are encapsulated"
    type = "encapsulated"
    modules = [
        "mypackage.orders",
    ]
    public_modules = [
        "mypackage.orders.api",
    ]
    ```

    ```toml
    [tool.importlinter]
    root_package = "mypackage"

    [[tool.importlinter.contracts]]
    name = "Billing is encapsulated"
    type = "encapsulated"
    modules = [
        "mypackage.data.billing",
        "mypackage.domain.billing",
    ]
    public_modules = [
        "mypackage.domain.billing.api",
    ]
    ignore_imports = [
        "mypackage.checkout.views -> mypackage.domain.billing.models",
        "mypackage.domain.billing.tasks -> mypackage.notifications.email",
    ]
    ```

    ```toml
    [tool.importlinter]
    root_packages = ["mypackage", "sharedlibrary"]

    [[tool.importlinter.contracts]]
    name = "Shipping is encapsulated"
    type = "encapsulated"
    modules = [
        "mypackage.shipping",
    ]
    public_modules = [
        "mypackage.shipping.api",
    ]
    # Shipping may use sharedlibrary, so only consider mypackage.
    scope = [
        "mypackage",
    ]
    ```

**Configuration options**

- `modules`: The modules that make up the unit. Descendants of each module are also part of the unit. The modules
  don't need to be next to each other.
  Each module must exist. Supports [wildcards](index.md#wildcards).
- `public_modules`: Modules within the unit that other modules are allowed to import. Descendants of each module are
  also public. Each public module must be within the unit. If this is omitted, other modules may not import the unit at
  all. (Optional.) Supports [wildcards](index.md#wildcards).
- `scope`: The modules that the contract considers. Descendants of each module are also in scope. Imports between
  the unit and a module that isn't in scope are ignored, in both directions. Each module must exist. If this is
  omitted, the scope is all the root packages. (Optional.) Supports [wildcards](index.md#wildcards).
- `ignore_imports`: See [shared options](index.md#options-used-by-multiple-contracts).
- `unmatched_ignore_imports_alerting`: See [shared options](index.md#options-used-by-multiple-contracts).
- `broken_contract_guidance`: See [shared options](index.md#options-used-by-multiple-contracts).
