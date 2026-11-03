# ADR-0003: Hand-rolled Cube-style YAML over dbt MetricFlow

Status: accepted

## Context

The governed surface needs a declaration format. dbt MetricFlow is the
industry tool; a small bespoke YAML compiled by our own code is the
alternative.

## Decision

One YAML file (`src/tender_radar/semantic/layer.yaml`) declares metrics,
dimensions, and governance rules; `semantic/compiler.py` (~150 lines)
compiles requests to SQL and enforces the rules. dbt still owns all
transformations and tests; the YAML only governs what agents may query.

## Consequences

- The governance is legible: a reviewer opens one file and sees exactly what
  an agent can and cannot ask, including the currency guard, the value_type
  default, and the top-N rule on high-cardinality dimensions.
- Domain guards that matter here (refusing cross-currency sums; excluding
  framework ceilings from averages by default; the injectable clock) are
  first-class, where MetricFlow would push them into convention.
- Cost: we own the compiler, so its correctness is on us — hence 13
  dedicated governance tests. The YAML is not interoperable with BI tooling;
  if that need appears, MetricFlow is the migration path and the YAML maps
  onto it cleanly.
