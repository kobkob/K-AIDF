# Dimension 2: Methodology-as-Code

**Points:** 20 (the checks below add up to 20)

The methodology lives in versioned, validated artifacts: the .kaidf/ scaffold, the mentor workflow state, the YAML specs and the phase deliverables.

| Check | Criterion | Points | Evidence required |
| --- | --- | --- | --- |
| `kaidf-scaffold` | .kaidf/ matches the generator scaffold | 6 | Directory tree of .kaidf/ compared with the generated scaffold of the same spec version. |
| `mentor-state-valid` | mentor-workflow.json is valid and current | 5 | .kaidf/mentor-workflow.json parses as JSON and its phase references exist. |
| `specs-validate` | All YAML specs pass kaidf-gen validate | 5 | Output of kaidf-gen validate for every spec in the repository. |
| `phase-artifacts-filled` | Phase deliverables are filled in, not left as scaffold | 4 | Deliverable files under docs/0N_*/ differ from the blank generator templates. |

Score each check as `pass`, `partial` or `fail` in `../audit-matrix.csv`. Record the evidence location in `auditor_notes`.
