import matplotlib.pyplot as plt
import matplotlib
from sklearn.cluster import KMeans

def elbow_method_graph(x):
    # Elbow Method for optimal K
    # We will test K from 1 to 10
    max_k = 10
    inertia = []

    for k in range(1, max_k + 1):
        kmeans_test = KMeans(n_clusters=k, random_state=42, n_init=10)
        kmeans_test.fit(x)
        inertia.append(kmeans_test.inertia_)

    plt.figure(figsize=(10, 6))
    plt.plot(range(1, max_k + 1), inertia, marker='o')
    plt.title('Elbow Method for Optimal K')
    plt.xlabel('Number of Clusters (K)')
    plt.ylabel('Inertia')
    plt.xticks(range(1, max_k + 1))
    plt.grid(True)
    plt.show()