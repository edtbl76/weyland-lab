# C4 Component — mother VM (k3s)

Level 3: the components inside the mother k3s node, grouped into three planes (AI/RAG serving · data mesh/lakehouse · platform/ops). Every view below is interactive — pan, zoom, and click to inspect; the dense planes (mesh, ops) are sliced into sub-zones you can drill into. The full explorer (with every sub-zone view) is at [likec4.weyland.lab](https://likec4.weyland.lab). Container view: [c4-container.md](c4-container.md).

## The three planes

```likec4-view
mother
```

## AI / RAG serving plane

```likec4-view
aiPlane
```

## Data mesh / lakehouse plane

The mesh plane splits into storage · query/BI · streaming · Tier-2 stores · feature-store/ML · governance — drill into each in the [explorer](https://likec4.weyland.lab).

```likec4-view
meshPlane
```

## Platform / ops plane

The ops plane splits into ingress/SSO/DNS · observability · delivery/governance · infra/tooling.

```likec4-view
opsPlane
```
