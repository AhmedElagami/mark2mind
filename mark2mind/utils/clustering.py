from typing import List, Dict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics import silhouette_score

def cluster_chunk_trees(chunk_results: List[Dict], n_clusters: int = None) -> List[List[Dict]]:
    """
    Cluster chunk results into semantic groups using tags and heading paths.

    If n_clusters is not provided, it is automatically determined using silhouette score.

    Args:
        chunk_results: List of chunk_result dicts (must include 'tags' and optionally 'metadata.heading_path')
        n_clusters: Desired number of clusters (optional; if None, will auto-tune)

    Returns:
        List of clustered groups (each group is a list of chunk_result dicts)
    """
    def get_text(item):
        tags = " ".join(item.get("tags", []))
        heading = " ".join(item.get("metadata", {}).get("heading_path", []))
        return f"{heading} {tags}".strip()

    texts = [get_text(item) for item in chunk_results]

    if not any(texts):
        raise ValueError("No valid text found for clustering.")

    if len(texts) < 2:
        return [chunk_results]  # Only one cluster needed

    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(texts)

    # Dimensionality reduction if necessary
    if X.shape[1] > 100:
        svd = TruncatedSVD(n_components=50)
        X_reduced = svd.fit_transform(X)
    else:
        X_reduced = X

    # Auto-tune k if not given
    if n_clusters is None:
        max_k = min(10, len(texts))  # Limit search space
        best_k = 2
        best_score = -1

        for k in range(2, max_k + 1):
            try:
                model = KMeans(n_clusters=k, n_init="auto", random_state=42)
                labels = model.fit_predict(X_reduced)
                score = silhouette_score(X_reduced, labels)
                if score > best_score:
                    best_k = k
                    best_score = score
            except Exception:
                continue  # Handle any failure due to empty clusters, etc.

        n_clusters = best_k

    # Final clustering with best or given k
    kmeans = KMeans(n_clusters=n_clusters, n_init="auto", random_state=42)
    labels = kmeans.fit_predict(X_reduced)

    clustered = [[] for _ in range(n_clusters)]
    for idx, label in enumerate(labels):
        clustered[label].append(chunk_results[idx])

    return clustered
