# Tax region validate

`orrery/tax-region` is a local, stateless validator for **tax-jurisdiction record
shapes**. Its initial static `sales-jurisdiction` profile requires uppercase
ISO country and subdivision codes plus a composite `jurisdiction_key` formatted
as `CC-RR` (for example `US-CA`). Extra fields are rejected. The profile digest
is deterministic and identifies the schema used for the result.

**Not now:** remittance, filing, payouts, rate lookup, or nexus determination.
Those stay in wallet and commerce epics. No tax API egress is used.

If the documented jurisdiction shape changes, update the static profile, its
version, tests, and this document together before publishing a new Star version.
No schema is fetched at validation time.
