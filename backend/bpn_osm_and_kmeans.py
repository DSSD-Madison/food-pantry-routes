import time
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from scipy.optimize import linear_sum_assignment
import pandas as pd
from sklearn.cluster import KMeans
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import json
import os
import time

CACHE_FILE = "geocode_cache.json"


def load_cache():
    """Load cache from file or return empty dict."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    """Write cache to disk."""
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def geocode_addresses(address_list):
    """
    Geocode a list of addresses with caching.
    Success entries keep the same format; failures are also cached.
    """
    geolocator = Nominatim(user_agent="BNNP_Flags", timeout=10)

    cache = load_cache()
    geocoded_locations = []

    try:
        for address in address_list:
            # 1. Check cache first
            if address in cache:
                entry = cache[address]

                # If previous attempt failed
                if entry.get("error"):
                    print(f"[CACHE-FAIL] {address} previously failed to geocode")
                else:
                    geocoded_locations.append(entry)
                    print(f"[CACHE] {address} -> {entry['latitude']}, {entry['longitude']}")

                continue

            # 2. Call geocoder if not cached
            address_temp = geolocator.geocode(address)

            if address_temp:
                # SUCCESS (same format as existing successful cache entries)
                entry = {
                    "address": address,
                    "latitude": address_temp.latitude,
                    "longitude": address_temp.longitude,
                    "full_result": address_temp.address,
                }

                print(f"[API] Found {address} at {entry['latitude']}, {entry['longitude']}")

            else:
                # FAILURE — NEW format but does NOT affect existing successful cache entries
                entry = {
                    "address": address,
                    "error": True,  # new flag so you know it failed
                }

                print(f"[API] FAILED: could not find {address}")

            # Save to cache (success or failure)
            cache[address] = entry
            save_cache(cache)

            geocoded_locations.append(entry)

            time.sleep(1)  # Nominatim 1 req/sec limit

    except (GeocoderTimedOut, GeocoderUnavailable) as e:
        print(f"ERROR: '{address}' ({e})")

    return geocoded_locations

def get_groups(data, n_clusters):
    x = np.array([[i["latitude"], i["longitude"]] for i in data])

    cluster_labels, cluster_centers = balanced_kmeans(x, n_clusters)

    return (cluster_labels, cluster_centers, x)

# def get_groups(data, n_clusters):
#   """
#     Creates the clusters of locations

#     Args:
#         address_list (<class 'pandas.core.series.Series'>): one-dimensional labeled array of location names

#     Returns:
#         list: List of dictionaries which contain information of the latitude and longitutde of each location
#     """

#   x = []
#   for i in data:
#     x.append([i.get("latitude"),i.get("longitude")])
#   x= np.array(x)


#   # idk what random_state does but keep it for now
#   kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
#   kmeans.fit(x)


#   cluster_labels = kmeans.labels_
#   cluster_centers = kmeans.cluster_centers_

#   return (cluster_labels, cluster_centers, x)

def generate_kmeans_grouping_graph(geocode_address_data, n_clusters, cluster_labels):

  # List of colors for different clusters
  cmap = matplotlib.colormaps['tab20']
  cluster_colors = [cmap(i / n_clusters) for i in range(n_clusters)]

  latitude = []
  longitude = []
  colors = []
  for i in range(len(geocode_address_data)):
    latitude.append(geocode_address_data[i].get("latitude"))
    longitude.append(geocode_address_data[i].get("longitude"))

    # adding the respective color to the colors list depending on the cluster it belongs to
    cluster = int(cluster_labels[i])
    color = cluster_colors[cluster]
    colors.append(color)

  # plt.plot(latitude,longitude,'o')
  plt.scatter(latitude, longitude, c=colors)
  plt.show()


def balanced_kmeans(x, n_clusters, random_state=42):
    """
    Balanced K-Means implemented via Hungarian assignment.
    Ensures cluster sizes differ by at most 1.
    """

    N = len(x)

    # Step 1: initial KMeans to get centroids
    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    kmeans.fit(x)
    centers = kmeans.cluster_centers_

    # Step 2: compute cost matrix (distance of each point to each center)
    cost = np.zeros((N, n_clusters))
    for c in range(n_clusters):
        diff = x - centers[c]
        cost[:, c] = np.sum(diff * diff, axis=1)

    # Step 3: balanced assignment target sizes
    base = N // n_clusters
    extra = N % n_clusters
    sizes = [base + (1 if i < extra else 0) for i in range(n_clusters)]

    # Step 4: build expanded cost matrix for Hungarian algorithm
    expanded_cost = np.repeat(cost, repeats=sizes, axis=1)

    # Solve assignment
    row_ind, col_ind = linear_sum_assignment(expanded_cost)

    # Convert expanded column index → original cluster index
    cluster_labels = np.zeros(N, dtype=int)
    pointer = []
    s = 0
    for c in range(n_clusters):
        pointer.append((c, s, s + sizes[c]))
        s += sizes[c]

    for r, expanded_col in zip(row_ind, col_ind):
        for c, lo, hi in pointer:
            if lo <= expanded_col < hi:
                cluster_labels[r] = c
                break

    # recompute cluster centers
    new_centers = np.zeros_like(centers)
    for c in range(n_clusters):
        pts = x[cluster_labels == c]
        new_centers[c] = pts.mean(axis=0)

    return cluster_labels, new_centers