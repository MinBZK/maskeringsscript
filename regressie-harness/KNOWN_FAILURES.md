# Known failures: eleven strict expected failures

These faults are unresolved and are not approved behavior. A green run can
include all eleven `xfail` outcomes. The small gold set does not automatically
cover these gaps. This inventory describes the regex pass; later passes may
behave differently and provide no guarantee of correcting them.

[known_failures.json](known_failures.json) contains the complete input, current
output, desired output and test reference. Inventory tests verify the current
output; strict expected-failure tests continue to assert the desired behavior.
Dutch examples and output labels are intentional test data and remain unchanged.

| ID | Case | Current fault | Desired behavior |
| --- | --- | --- | --- |
| K01 | `ik woon 5701 En Helmond` | Postcode remains visible | Mask the postcode |
| K02 | `5701 En Helmond` | Postcode remains visible | Mask the postcode |
| K03 | `Postcode 2020 en huisnummer 14 ontbreken.` | `2020 en` is incorrectly masked as a postcode | Preserve the text |
| K04 | The same sentence starting with `Postcode:` | `2020 en` is incorrectly masked | Preserve the text |
| K05 | `Benoemd in 2020 ad interim.` | `2020 ad` is incorrectly masked | Preserve the text |
| K06 | `In 2020 ad hoc besloten.` | `2020 ad` is incorrectly masked | Preserve the text |
| K07 | `Geheugen 2000 MB` | Quantity and unit are incorrectly masked | Preserve the text |
| K08 | URL path containing `/3011AB/henkzwartendijk` | Rule order leaves a visible URL tail | Mask the complete URL |
| K09 | `3011 AB 12-14` | `-14` remains visible | Mask the complete postcode/house-number segment |
| K10 | `3011 AB 12/3` | `/3` remains visible | Mask the complete postcode/house-number segment |
| K11 | `3011 AB 12bis` | `12bis` remains visible | Mask the complete postcode/house-number segment |

This represents two recall issues, five precision issues and four cases with a
visible URL or house-number fragment. Each requires a separate source change
and assessment; improving the harness does not resolve them.

An unexpected pass fails the run. Review both the desired behavior and side
effects before removing the xfail and updating the inventory. A passing test
that characterizes an existing fault does not replace the desired-behavior test.
