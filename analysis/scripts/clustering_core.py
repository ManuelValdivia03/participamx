"""Algoritmos numéricos del piloto, sin instalar dependencias adicionales.

Implementaciones NumPy de Ward (cadena de vecinos), Lloyd/k-means++, DBSCAN,
escaladores y métricas. Las fórmulas y sus límites se documentan en el piloto.
"""

from __future__ import annotations

import numpy as np

from clean_data import require


def fit_scaler(values, method):
    values = np.asarray(values, dtype=float)
    require(values.ndim == 2 and np.isfinite(values).all(), 'El escalador requiere una matriz finita.')
    if method == 'original':
        location, scale = np.zeros(values.shape[1]), np.ones(values.shape[1])
    elif method == 'standard':
        location, scale = values.mean(axis=0), values.std(axis=0, ddof=0)
    elif method == 'robust':
        location = np.median(values, axis=0)
        scale = np.percentile(values, 75, axis=0)-np.percentile(values, 25, axis=0)
    else:
        raise ValueError(f'Escalador desconocido: {method}')
    constant = scale <= 10*np.finfo(float).eps
    scale[constant] = 1.
    return dict(method=method, location=location.tolist(), scale=scale.tolist(), constant_columns=constant.tolist())


def transform(values, parameters):
    return (np.asarray(values, dtype=float)-np.asarray(parameters['location']))/np.asarray(parameters['scale'])


def inverse_transform(values, parameters):
    return np.asarray(values)*np.asarray(parameters['scale'])+np.asarray(parameters['location'])


def pairwise_distances(values):
    """Distancias euclídeas completas; no aproxima ni muestrea municipios."""
    values = np.asarray(values, dtype=float)
    norms = np.einsum('ij,ij->i', values, values)
    squared = np.maximum(0., norms[:, None]+norms[None, :]-2*values@values.T)
    np.fill_diagonal(squared, 0.)
    return np.sqrt(squared)


def ward_linkage(distances):
    """Ward euclídeo con actualización Lance–Williams y cadena recíproca."""
    n = len(distances)
    require(n >= 2 and distances.shape == (n, n) and np.isfinite(distances).all(), 'Distancias Ward no válidas.')
    work = distances**2
    np.fill_diagonal(work, np.inf)
    active, sizes, identifiers = np.ones(n, dtype=bool), np.ones(n, dtype=np.int64), np.arange(n)
    chain, raw = [], []
    for step in range(n-1):
        if not chain: chain.append(int(np.flatnonzero(active)[0]))
        while True:
            left = chain[-1]
            right = int(np.argmin(work[left]))
            if len(chain) >= 2 and right == chain[-2]: break
            # En empates se prefiere el vecino previo para cerrar la cadena.
            if len(chain) >= 2 and work[left, chain[-2]] == work[left, right]:
                right = chain[-2]
                break
            require(right not in chain, 'Ciclo no recíproco en cadena Ward.')
            chain.append(right)
        ni, nj, dij = sizes[left], sizes[right], work[left, right]
        raw.append([int(identifiers[left]), int(identifiers[right]), float(np.sqrt(max(0., dij))), int(ni+nj)])
        others = np.flatnonzero(active & (np.arange(n) != left) & (np.arange(n) != right))
        nk = sizes[others]
        updated = ((nk+ni)*work[left, others]+(nk+nj)*work[right, others]-nk*dij)/(nk+ni+nj)
        require((updated >= -1e-9*max(1., dij)).all(), 'Distancia Ward negativa fuera de tolerancia.')
        work[left, others] = work[others, left] = np.maximum(updated, 0.)
        work[right, :] = work[:, right] = np.inf
        work[left, left] = np.inf
        active[right], sizes[left], identifiers[left] = False, ni+nj, n+step
        chain = chain[:-2]
    # La cadena puede descubrir ramas disjuntas fuera de orden; ordena alturas y reetiqueta nodos.
    mapping, ordered = {i: i for i in range(n)}, []
    for old in sorted(range(n-1), key=lambda i: (raw[i][2], i)):
        left, right, height, size = raw[old]
        require(left in mapping and right in mapping, 'Orden topológico Ward inválido.')
        ordered.append([mapping[left], mapping[right], height, size])
        mapping[n+old] = n+len(ordered)-1
    result = np.asarray(ordered, dtype=float)
    require(np.diff(result[:, 2]).min(initial=0) >= -1e-10 and result[-1, 3] == n, 'Árbol Ward inconsistente.')
    return result


def cut_linkage(linkage, clusters):
    n = len(linkage)+1
    require(1 <= clusters <= n, 'Corte Ward no válido.')
    parents, representatives = np.arange(n), np.zeros(2*n-1, dtype=int)
    representatives[:n] = np.arange(n)
    def root(value):
        while parents[value] != value:
            parents[value] = parents[parents[value]]
            value = parents[value]
        return value
    for index, (left, right, _, _) in enumerate(linkage[:n-clusters]):
        a, b = root(representatives[int(left)]), root(representatives[int(right)])
        parents[max(a, b)] = min(a, b)
        representatives[n+index] = min(a, b)
    labels = np.array([root(i) for i in range(n)])
    return np.unique(labels, return_inverse=True)[1]


def kmeans_plus_plus(values, clusters, rng):
    n = len(values)
    centers = [values[int(rng.integers(n))].copy()]
    closest = np.sum((values-centers[0])**2, axis=1)
    for _ in range(1, clusters):
        if closest.sum() == 0:
            centers.append(values[len(centers) % n].copy())
        else:
            index = int(rng.choice(n, p=closest/closest.sum()))
            centers.append(values[index].copy())
        closest = np.minimum(closest, np.sum((values-centers[-1])**2, axis=1))
    return np.array(centers)


def kmeans(values, clusters, seed, n_init=10, max_iter=300):
    """Lloyd hasta asignaciones estables; devuelve la menor SSE de n_init."""
    values = np.asarray(values, dtype=float)
    require(np.isfinite(values).all() and 1 <= clusters <= len(values), 'Entrada K-Means no válida.')
    generator = np.random.default_rng(seed)
    best, initialization_records = None, []
    for initialization in range(n_init):
        initial_seed = int(generator.integers(0, 2**32-1))
        centers = kmeans_plus_plus(values, clusters, np.random.default_rng(initial_seed))
        previous, converged = None, False
        for iteration in range(1, max_iter+1):
            squared = np.sum((values[:, None, :]-centers[None, :, :])**2, axis=2)
            labels = squared.argmin(axis=1)
            counts = np.bincount(labels, minlength=clusters)
            if previous is not None and np.array_equal(labels, previous) and counts.min() > 0:
                converged = True
                break
            new_centers = np.array([values[labels == index].mean(axis=0) if counts[index] else centers[index]
                                    for index in range(clusters)])
            if (counts == 0).any():
                candidates = np.argsort(squared[np.arange(len(values)), labels])[::-1]
                for empty, candidate in zip(np.flatnonzero(counts == 0), candidates): new_centers[empty] = values[candidate]
            centers, previous = new_centers, labels.copy()
        squared = np.sum((values[:, None, :]-centers[None, :, :])**2, axis=2)
        labels = squared.argmin(axis=1)
        inertia = float(squared[np.arange(len(values)), labels].sum())
        initialization_records.append(dict(initialization=initialization, seed=initial_seed, inertia=inertia,
                                           iterations=iteration, converged=converged))
        if best is None or inertia < best['inertia']:
            best = dict(labels=labels.copy(), centers=centers.copy(), inertia=inertia, iterations=iteration,
                        converged=converged, selected_initialization=initialization)
    best['initializations'] = initialization_records
    return best


def dbscan(distances, eps, min_samples):
    """Vecindarios cerrados incluyen al propio punto; bordes por orden estable."""
    require(eps > 0 and min_samples >= 1, 'Parámetros DBSCAN no válidos.')
    n = len(distances)
    adjacent = distances <= eps
    core = adjacent.sum(axis=1) >= min_samples
    labels = np.full(n, -1, dtype=int)
    cluster = 0
    for start in range(n):
        if not core[start] or labels[start] != -1: continue
        labels[start] = cluster
        stack = [start]
        while stack:
            current = stack.pop()
            neighbors = np.flatnonzero(adjacent[current] & (labels == -1))
            labels[neighbors] = cluster
            stack.extend(neighbors[core[neighbors]].tolist())
        cluster += 1
    return labels, core


def adjusted_rand(left, right):
    require(len(left) == len(right), 'ARI requiere las mismas observaciones.')
    n = len(left)
    if n < 2: return np.nan
    _, a = np.unique(left, return_inverse=True)
    _, b = np.unique(right, return_inverse=True)
    contingency = np.zeros((a.max()+1, b.max()+1), dtype=np.int64)
    np.add.at(contingency, (a, b), 1)
    choose2 = lambda values: np.sum(values*(values-1)/2)
    agreements = choose2(contingency)
    rows, columns = choose2(contingency.sum(axis=1)), choose2(contingency.sum(axis=0))
    expected = rows*columns/(n*(n-1)/2)
    denominator = .5*(rows+columns)-expected
    return float((agreements-expected)/denominator) if denominator else 1.


def validation_metrics(values, labels, distances):
    """Silhouette exacto y Davies–Bouldin; NULL con causa cuando no aplican."""
    labels = np.asarray(labels)
    groups, encoded = np.unique(labels, return_inverse=True)
    n, k = len(labels), len(groups)
    if not 2 <= k < n:
        return dict(silhouette=np.nan, davies_bouldin=np.nan, metric_status='requires_2_to_n_minus_1_groups')
    counts = np.bincount(encoded)
    means = np.column_stack([distances[:, encoded == index].sum(axis=1)/counts[index] for index in range(k)])
    own = means[np.arange(n), encoded]*counts[encoded]/np.maximum(counts[encoded]-1, 1)
    means[np.arange(n), encoded] = np.inf
    other = means.min(axis=1)
    denominator = np.maximum(own, other)
    silhouette = np.divide(other-own, denominator, out=np.zeros(n), where=denominator > 0)
    silhouette[counts[encoded] == 1] = 0.
    centers = np.array([values[encoded == index].mean(axis=0) for index in range(k)])
    scatter = np.array([np.sqrt(np.sum((values[encoded == index]-centers[index])**2, axis=1)).mean() for index in range(k)])
    center_distances = pairwise_distances(centers)
    off_diagonal = ~np.eye(k, dtype=bool)
    if (center_distances[off_diagonal] <= 1e-14).any():
        db, status = np.nan, 'coincident_centroids_db_undefined'
    else:
        np.fill_diagonal(center_distances, np.inf)
        db = float(((scatter[:, None]+scatter[None, :])/center_distances).max(axis=1).mean())
        status = 'defined'
    return dict(silhouette=float(silhouette.mean()), davies_bouldin=db, metric_status=status)


def centroid_matching(reference, candidate):
    """Asignación exacta mínima por programación dinámica; K<=10 en el piloto."""
    costs = np.sum((reference[:, None, :]-candidate[None, :, :])**2, axis=2)
    k = len(reference)
    states = {0: (0., [])}
    for mask in range(1 << k):
        if mask not in states: continue
        cost, selected = states[mask]
        row = len(selected)
        if row == k: continue
        for column in range(k):
            if mask & (1 << column): continue
            new_mask, new_cost = mask | (1 << column), cost+costs[row, column]
            if new_mask not in states or new_cost < states[new_mask][0]: states[new_mask] = (new_cost, selected+[column])
    return np.array(states[(1 << k)-1][1])


def geometric_elbow(ks, sse, axis_mode='raw'):
    """Teorema 2.5, ecuación (4), arXiv:2502.00851v2; no adapta la SSE."""
    x, y = np.asarray(ks, dtype=float), np.asarray(sse, dtype=float)
    require(len(x) == len(y) and len(x) >= 3 and np.diff(x).min() > 0, 'Curva SSE no válida.')
    if np.diff(y).max() > 1e-10*max(1., y.max()): return None, [], 'nonmonotonic_sse'
    if axis_mode == 'sse_relative': y = y/y[0] if y[0] else y
    elif axis_mode == 'unit_axes':
        x = (x-x[0])/(x[-1]-x[0])
        y = (y-y.min())/(y.max()-y.min()) if y.max() > y.min() else y*0
    elif axis_mode != 'raw': raise ValueError('Escala de ejes no válida.')
    slopes = np.diff(y)/np.diff(x)
    rows = []
    for index in range(1, len(x)-1):
        before, after = slopes[index-1], slopes[index]
        eligible = after > before
        tangent = (before-after)/(1+before*after) if eligible else np.nan
        rows.append(dict(k=int(ks[index]), previous_slope=float(before), next_slope=float(after),
                         eligible=bool(eligible), tan_psi=float(tangent), axis_mode=axis_mode))
    valid = [row for row in rows if row['eligible']]
    return (min(valid, key=lambda row: row['tan_psi'])['k'] if valid else None), rows, 'defined' if valid else 'no_eligible_corner'


def pattern_decomposition(raw, labels):
    """Descompone separación en nivel medio y forma etaria/sexo, sin renombrar perfiles."""
    raw = np.asarray(raw)
    means = raw.mean(axis=1)
    shape = raw-means[:, None]
    overall, mean_level, mean_shape = raw.mean(axis=0), means.mean(), shape.mean(axis=0)
    between, level, shape_between = 0., 0., 0.
    for label in np.unique(labels):
        group = raw[labels == label]
        centroid = group.mean(axis=0)
        between += len(group)*np.sum((centroid-overall)**2)
        level += len(group)*raw.shape[1]*(centroid.mean()-mean_level)**2
        shape_between += len(group)*np.sum((centroid-centroid.mean()-mean_shape)**2)
    level_total = raw.shape[1]*np.sum((means-mean_level)**2)
    shape_total = np.sum((shape-mean_shape)**2)
    require(np.isclose(between, level+shape_between, rtol=1e-8, atol=1e-10), 'Descomposición nivel/forma no concilia.')
    return dict(between_level_share=float(level/between) if between else np.nan,
                between_shape_share=float(shape_between/between) if between else np.nan,
                level_explained=float(level/level_total) if level_total else np.nan,
                shape_explained=float(shape_between/shape_total) if shape_total else np.nan)
