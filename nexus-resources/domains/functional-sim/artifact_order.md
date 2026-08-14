# Artifact reading order — functional-sim

<!-- Rendered from nexus.toml by nexus-render. Do not hand-edit. -->

## 1. sim.log
read first; extract the primary $error/$fatal message, the faulting simulation time, and the failing check/assertion name

## 2. waveform.fsdb
read second; at the faulting time, trace the failing signal back to its driver and capture the surrounding control state

<!-- rendered-from: 9803c5f7e4c68a37e493c02f24e3045f8eec49b83c24bc084668b69d0dc4a6ac -->
