# Artifact reading order — formal-verif

<!-- Rendered from nexus.toml by nexus-render. Do not hand-edit. -->

## 1. violation_report
read first; extract the failing property name and the bound/depth at which it failed

## 2. counterexample_trace
read second; extract the variable assignment sequence that drives the property to failure

<!-- rendered-from: 9803c5f7e4c68a37e493c02f24e3045f8eec49b83c24bc084668b69d0dc4a6ac -->
