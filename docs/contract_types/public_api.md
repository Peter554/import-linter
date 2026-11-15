## Public API

_Type name:_ `public_api`

Public API contracts prevent modules from being directly imported, except through their public API.

The `modules` form a single unit, made up of the listed modules and all of their descendants. The modules don't
need to be adjacent: for example, a feature split across a data layer and a domain layer can be one unit. Imports within
the unit are always allowed. Other modules in the project may only import the unit through its `public_modules`
(and their descendants).

For example, if `mypackage.billing` is the unit and `mypackage.billing.api` is its public module, then
`mypackage.checkout` can import `mypackage.billing.api` and `mypackage.billing.api.schemas`, but not
`mypackage.billing.models`.

Only direct imports are checked. An indirect import has to end with a direct import into the unit, which is reported
instead.

## A unit split across several packages

In a layered project, a feature often doesn't live in one package:

```text
mypackage/
    data/
        billing/
    domain/
        billing/
            api.py
```

Each half could be protected on its own, but that doesn't capture the real boundary: billing as a whole. A
`public_api` contract can list both halves as one unit:

```ini
[importlinter:contract:billing]
name = Billing is only imported via its API
type = public_api
modules =
    mypackage.data.billing
    mypackage.domain.billing
public_modules =
    mypackage.domain.billing.api
```

The two halves can import each other freely, and the rest of the project can only import billing through
`mypackage.domain.billing.api`.

## Comparison with protected

[Protected](protected.md) contracts have the same intent, but they approach it from the other direction.

|                      | `protected`                                                                                              | `public_api`                                                   |
| -------------------- | -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| What is allow-listed | The _importers_ (`allowed_importers`)                                                                    | The _importable modules_ (`public_modules`)                    |
| Several modules      | Each protected module is checked separately, so imports between them must also be in `allowed_importers` | The modules form one unit, so imports between them are allowed |
| External packages    | May be protected                                                                                         | Not supported: the modules must be in the project              |

Use `protected` when you know who the legitimate callers are, for example a module that only one package should use.
Use `public_api` when you know what the legitimate entry points are: the list of importers of a widely used module
can grow with every new caller, but its public API is small and changes rarely.

**Examples:**

=== "INI"
    ```ini
    [importlinter]
    root_package = mypackage

    [importlinter:contract:orders-public-api]
    name = Orders are only imported via their API
    type = public_api
    modules =
        mypackage.orders
    public_modules =
        mypackage.orders.api
    ```

    ```ini
    [importlinter]
    root_package = mypackage

    [importlinter:contract:billing-public-api]
    name = Billing is only imported via its API
    type = public_api
    modules =
        mypackage.data.billing
        mypackage.domain.billing
    public_modules =
        mypackage.domain.billing.api
        mypackage.domain.billing.exceptions
    ignore_imports =
        mypackage.checkout.views -> mypackage.domain.billing.models
    ```

=== "TOML"
    ```toml
    [tool.importlinter]
    root_package = "mypackage"

    [[tool.importlinter.contracts]]
    name = "Orders are only imported via their API"
    type = "public_api"
    modules = ["mypackage.orders"]
    public_modules = ["mypackage.orders.api"]
    ```

    ```toml
    [tool.importlinter]
    root_package = "mypackage"

    [[tool.importlinter.contracts]]
    name = "Billing is only imported via its API"
    type = "public_api"
    modules = [
        "mypackage.data.billing",
        "mypackage.domain.billing",
    ]
    public_modules = [
        "mypackage.domain.billing.api",
        "mypackage.domain.billing.exceptions",
    ]
    ignore_imports = [
        "mypackage.checkout.views -> mypackage.domain.billing.models",
    ]
    ```

**Configuration options**

- `modules`: The modules that make up the unit. Descendants are included. Supports [wildcards](index.md#wildcards).
- `public_modules`: The modules that other modules are allowed to import. Descendants are included. These must be
  within `modules`. Supports [wildcards](index.md#wildcards).
- `ignore_imports`: See [shared options](index.md#options-used-by-multiple-contracts). (Optional.)
- `unmatched_ignore_imports_alerting`: See [shared options](index.md#options-used-by-multiple-contracts). (Optional.)
- `broken_contract_guidance`: See [shared options](index.md#options-used-by-multiple-contracts). (Optional.)

**Sample output**

```text
Billing is only imported via its API
------------------------------------

Imports into the modules are only allowed via the public modules:

- mypackage.checkout.views -> mypackage.domain.billing.models (l.3)

- mypackage.reports -> mypackage.data.billing.repository (l.12, 27)
```
