# Open Library R2+A1 split-edition routing LLM prompt v2

## Task

You are routing Open Library Edition records from a known heterogeneous
Open Library Work into a fixed set of human-defined components.

The project-level decision to split the predecessor has already been made by
human review.

Your task is NOT to decide whether the predecessor should be split.

Your task is NOT to invent new successor works.

Your task is only to decide, for each supplied Edition record, whether:

1. it belongs to exactly one of the supplied fixed components; or
2. the supplied evidence is insufficient to route it safely.

Return one routing decision for every supplied `edition_key`.

## Allowed routing decisions

Use exactly one of:

- `ASSIGN_COMPONENT`
- `HOLD_UNRESOLVED`

### ASSIGN_COMPONENT

Use `ASSIGN_COMPONENT` only when the Edition evidence is sufficient to assign
the publication to one of the supplied fixed `component_id` values.

When using `ASSIGN_COMPONENT`:

- return exactly one supplied `component_id`;
- route the Edition as a publication/manifestation-level unit;
- do not split one Edition among several components.

### HOLD_UNRESOLVED

Use `HOLD_UNRESOLVED` when:

- the title/subtitle is too generic;
- the supplied metadata conflicts;
- the Edition could plausibly belong to more than one component;
- the human remediation plan explicitly identifies the Edition or category as
  unresolved;
- or the evidence is otherwise insufficient for a safe routing decision.

For `HOLD_UNRESOLVED`, return an empty string for `component_id`.

## Critical granularity rule

An Edition may contain several literary works.

Do NOT route an omnibus or anthology to one of its constituent works merely
because that constituent title appears in the Edition metadata.

Route the Edition as a whole.

Examples:

- an omnibus containing five novels is one omnibus-level publication;
- a selected-fiction volume remains a selected-fiction volume;
- a collected-poems volume remains a collected-poems publication;
- a volume containing several tales should be routed to the appropriate
  collection/selection component, not separately to each tale.

The fixed component definitions supplied with the request determine the
allowed routing boundaries.

## Human component registry is authoritative

The supplied components are the current frozen human-remediated
component registry v2.

The project context also contains a frozen `human_resolution_plan` and
`human_resolution_note`. Those fields were written before registry v2 was
created and are retained as historical context. They may therefore omit a
component newly added in registry v2 or describe an earlier component
boundary.

When the older project-level resolution text and the supplied fixed component
registry v2 differ, the fixed component registry v2 is authoritative for this
routing task.

Do not attempt to reconstruct or guess any previous row-level LLM or human
routing decision. Route each supplied Edition afresh from the supplied Edition
metadata, project context, and fixed registry v2.

You may:

- assign an Edition to one supplied component; or
- hold it unresolved.

You may NOT:

- create a new component;
- merge supplied components;
- split a supplied component;
- change a component's meaning;
- reinterpret `PRIMARY_SUCCESSOR_HINT` as permission to reuse an existing
  project-work identifier.

`human_role_hint` is provenance about the component.

In particular:

- `DETACH` means detach the Edition from the erroneous predecessor grouping.
  It does NOT mean that the publication is outside the dissertation corpus.
- `EXCLUDE_APPARATUS` identifies material already judged by the human
  remediation plan to be catalogue/study/apparatus material.
- `PRIMARY_SUCCESSOR_HINT` records the human reviewer's operational preference
  only. It does not affect Edition routing unless the Edition evidence
  actually supports that component.

## Evidence rules

Use only the evidence supplied in the request.

Do not browse the web.

Do not use outside bibliographic knowledge.

Do not infer missing contents solely from general knowledge of the author.

Relevant evidence may include:

- Edition title
- Edition subtitle
- publication date
- publisher
- Edition author keys
- number of pages
- the frozen human resolution plan
- the fixed component labels and definitions
- patterns across the other Editions from the same Open Library Work

Publication dates are manifestation-level evidence. Do not treat them as
original intellectual-work dates unless the supplied routing definition
explicitly requires a particular manifestation.

## Conservative routing

Prefer `HOLD_UNRESOLVED` over a speculative assignment.

A generic author-name title with no informative subtitle should not be routed
solely because one component is common among nearby Editions.

However, repeated manifestations with highly consistent title/subtitle,
publisher, and other bibliographic evidence may be routed together when the
evidence clearly supports the same fixed component.

## Output requirements

Return exactly one object for every supplied `edition_key`.

Do not omit Editions.

Do not duplicate Editions.

For each Edition return:

- `edition_key`
- `routing_decision`
- `component_id`
- `llm_confidence`
- `llm_note`

Allowed confidence values:

- `HIGH`
- `MEDIUM`
- `LOW`

`llm_note` must briefly state the supplied evidence that determined the
routing.

Do not provide chain-of-thought or extended reasoning. Give only the concise
evidence basis needed to audit the classification.
