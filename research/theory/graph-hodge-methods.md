# Declared edge-signal Hodge instrument

4 October 2026. This optional operator extends the [graph-operator research agenda](graph-operator-research-agenda.md). It does not replace the reference graphs, node-signal spectrum, temporal paths, or observation contracts. No production sources were analyzed to develop this instrument.

## Mathematical question and conventions

The input is a finite graph with one chosen orientation and one scalar coordinate per unordered edge. For an edge $i\to j$, define the incidence row $G_e$ by $-1$ at $i$ and $+1$ at $j$. Then $(Gp)_e=p_j-p_i$. A caller-declared triangular face $(a,b,c)$ supplies a boundary column $C_f$ following $a\to b\to c\to a$, with signs adjusted to the declared edge orientations. Every boundary edge must exist. Consequently $G^\top C=0$.

Under the unweighted Euclidean inner product, compute

$$p=\arg\min_p\|Gp-f\|_2^2,\qquad g=Gp,\qquad r=f-g.$$

When faces are explicitly declared, compute

$$z=\arg\min_z\|Cz-r\|_2^2,\qquad u=Cz,\qquad h=r-u.$$

Thus $f=g+u+h$, with orthogonal gradient, curl-edge, and harmonic components. Divergence is $-G^\top f$; the **face-curl observable** is $C^\top f$. This observable differs from the **curl-edge component** $u$. Harmonic means $G^\top h=0$ and $C^\top h=0$, relative to the declared complex. These are finite-dimensional cochain conventions, following the combinatorial treatment in [Jiang, Lim, Yao and Ye, sections 4.2–4.3](https://arxiv.org/html/0811.1067v2).

The implementation projects by least squares rather than constructing a dense edge Laplacian. The formal edge operator is $GG^\top+CC^\top$; its harmonic residual is checked without materializing that matrix. No continuous manifold or Laplace–Beltrami approximation is assumed.

## The complex is a declared modeling choice

`faces=None` leaves the two-cell model unspecified: only gradient and circulation are available. `faces=[]` explicitly chooses an empty two-cell complex: curl is zero and circulation is harmonic relative to that choice. Supplied faces split circulation according to their boundary span. The instrument never fills graph cliques automatically.

Expected squared energies illustrate the distinction; tiny floating residuals remain visible in computed output.

| Declared signal | Face model | Gradient | Circulation | Curl-edge | Harmonic |
|---|---|---:|---:|---:|---:|
| Any signal on a tree | Empty | Entire signal | 0 | 0 | 0 |
| Unit oriented triangle cycle | Unspecified | 0 | 3 | Unavailable | Unavailable |
| Same triangle cycle | Empty | 0 | 3 | 0 | 3 |
| Same triangle cycle | One triangular face | 0 | 3 | 3 | 0 |
| Unit four-edge cycle | Empty | 0 | 4 | 0 | 4 |

Changing only the face model changes the curl/harmonic partition without changing an observed action or signal. A triangle face does not authenticate a joint interaction. Longer unfilled cycles can remain harmonic even when other triangles are filled. Dependent face boundaries are permitted: their numerical rank, not their count, determines the curl-space dimension.

## Pure API and evidence boundaries

```python
decompose_edge_signal(
    node_ids,                        # list of unique bounded strings
    edges,                           # [{id, source, target, value}]
    faces=None,                      # [{id, nodes: [a, b, c]}], explicit loop order
    max_work=10_000_000,
    max_memory_bytes=16 * 1024**2,
)
```

The last three arguments are keyword-only. There are no file, database, network, model, extraction, or source-authentication operations. Extra fields, booleans as scalar values, self-edges, parallel/opposite edges, duplicate triangle supports, unknown endpoints, and missing face boundaries are rejected. The host must separately bind exact source objects, projection rules, population/window, signal units, measurement uncertainty, and code hash. A canonical input fingerprint is integrity over the supplied mathematical input; it is not upstream authenticity.

Canonicalization sorts node IDs and edge/face IDs while preserving orientations, face-loop order, and numeric representation. `1` and `1.0`, or omitted and empty faces, receive different hashes. The SHA256 payload uses compact sorted finite JSON encoded as UTF-8. Outputs retain the exact declared signal and canonical identities, with no source text or arbitrary metadata passthrough.

Node potentials use zero mean independently in each connected component; isolates receive zero. Relative component offsets are unidentifiable. Face-boundary coefficients use the minimum Euclidean norm; with dependent faces, coefficients were nonunique before this gauge choice. Neither gauge creates agent rank, role, hierarchy, or intrinsic face importance.

## Numerical availability and bounded execution

Limits are 128 nodes, 512 edges, 256 faces, 256 KiB canonical input, 1 MiB output, and absolute scalar magnitude $10^{100}$. Aggregate work and conservative workspace proxies are checked before numerical allocation, with no sampling or silent truncation. These proxies bound declared dense shapes; external LAPACK workspace and runtime are not hard process limits.

The optional NumPy backend converts numeric values to float64 after pinning the exact canonical input and uses least squares with `rcond=1e-12`. Input is divided by its maximum absolute value, or one for an exactly zero signal. If normalization loses a nonzero coordinate to underflow, the result is unavailable. Residual tolerances in these coordinates are $10^{-10}+10^{-9}$ times each reported reference scale. Backend versions, singular values, numerical ranks, tolerances, and normalization are recorded. Gradient rank must match the exact graph component count. Curl/harmonic dimensions are explicitly numerical, not an exact-rank certification for arbitrary ill-conditioned complexes.

Checks cover reconstruction, orthogonality, energy identities, component gauges, boundary closure, circulation divergence, gradient face curl, harmonic divergence/curl and edge-Laplacian residual. Conversion back to natural units must pass a normalized round-trip check. Missing backend, budget excess, solver failure, or failed validation returns `available=False` without partial decomposition. Energy underflow is marked unavailable rather than mislabeled zero; natural and normalized energy have separate availability flags. Zero-signal fractions are undefined; tiny rounding residuals and fractions marginally above one are not clipped. Bitwise reproducibility across numerical builds is not promised.

## Interpretation and next falsifiable probes

A net count construction $f_{ij}=A_{ij}-A_{ji}$ would cancel balanced reciprocal activity. The instrument does not perform this construction; any future host must preserve the underlying two directional counts and declare this loss. Mathematical circulation in reference counts does not establish delivered messages, repeated information, rumor, belief, semantic inconsistency, or causal influence. Temporal feasibility and source-linked emission checks remain separate.

Synthetic checks should first recover known signals on trees, filled triangles, unfilled cycles, disconnected graphs and superpositions; orientation reversal with value sign reversal must preserve potentials and energies. Subsequent source-bound probes should freeze extraction and populations, compare prespecified signal constructions and face declarations, and inspect ordinary alternatives. A large component that disappears under an equally defensible declaration weakens its interpretation as a stable observable. Any mechanism claim requires a separately designed intervention and a measured outcome; no automatic candidate promotion follows from this operator.
