from typing import List, Dict, Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics import silhouette_score

def cluster_chunk_trees(chunk_results: List[Dict], n_clusters: Optional[int] = None) -> List[List[Dict]]:
    """
    Deterministic clustering of chunk results into semantic groups using heading-paths and tags.
    - Always uses dense arrays for both silhouette and final KMeans (so they agree).
    - Stabilizes SVD with random_state.
    - Handles low-variance / degenerate cases cleanly.
    """

    def get_text(item: Dict) -> str:
        tags = " ".join(item.get("tags", [])) or ""
        paths = " ; ".join(item.get("metadata", {}).get("heading_paths_top", [])) or ""
        s = f"{paths} || {tags}".strip()
        return s if s else ""  # keep length alignment

    texts = [get_text(item) for item in chunk_results]

    # Guard rails
    if not any(texts):
        raise ValueError("No valid text found for clustering.")
    if len(texts) < 2:
        return [chunk_results]

    # Vectorize (keep it simple and deterministic)
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(texts)  # sparse CSR

    # Reduce / densify consistently
    # Always produce a DENSE 2D np.ndarray 'D' for both tuning and final fit.
    if X.shape[1] > 100:
        svd = TruncatedSVD(n_components=min(50, X.shape[1] - 1), random_state=42)
        D = svd.fit_transform(X)  # dense
    else:
        D = X.toarray()  # dense

    # Early exit for degenerate data (all points ~ same)
    if np.allclose(D.std(axis=0), 0, atol=1e-12):
        return [chunk_results]

    # Pick k if not provided
    if n_clusters is None:
        # silhouette requires at least 2 clusters and less than n_samples
        k_min, k_max = 2, min(10, len(texts) - 1)
        best_k, best_score = 2, -1.0

        for k in range(k_min, k_max + 1):
            try:
                model = KMeans(n_clusters=k, n_init=10, random_state=42)
                labels = model.fit_predict(D)
                # If kmeans collapsed to <2 unique labels, skip scoring
                if len(set(labels)) < 2:
                    continue
                score = silhouette_score(D, labels, metric="euclidean")
                if score > best_score:
                    best_k, best_score = k, score
            except Exception:
                # skip pathological ks
                continue

        n_clusters = best_k

    # Final clustering on the SAME dense matrix 'D'
    kmeans = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
    labels = kmeans.fit_predict(D)

    # Group in the original order (deterministic)
    clustered: List[List[Dict]] = [[] for _ in range(n_clusters)]
    for idx, label in enumerate(labels):
        clustered[int(label)].append(chunk_results[idx])
    return clustered
