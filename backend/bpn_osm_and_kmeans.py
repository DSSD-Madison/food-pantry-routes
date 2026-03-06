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
import requests
from scipy.spatial import distance_matrix
import math
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

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

    # print("Cluster Labels: ", cluster_labels)

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

  # Calling distance_matrix temporarily
  distance_matrix(geocode_address_data, n_clusters, cluster_labels)

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

def distance_matrix(geocode_address_data, n_clusters, cluster_labels):

    #Creating a cluster dictionary
    cluster_dict = {}

    for i in range(len(geocode_address_data)):
        coordinates = {}

        coordinates["latitude"] = geocode_address_data[i].get("latitude")
        coordinates["longitude"] = geocode_address_data[i].get("longitude")

        cluster_number = int(cluster_labels[i])
        if cluster_number not in cluster_dict:
            cluster_dict[cluster_number] = []

        cluster_dict[cluster_number].append(coordinates)
    
    # print("cluster_dict: ", cluster_dict)

    distance_matrices = {}

    #Creating a distance matrix for each group
    for cluster in cluster_dict:
        
        # Calling the OSRM API for the distances between locations 

        # One API call enough if we need to do the distance matrix for 100 or fewer locations
        if (len(cluster_dict[cluster]) <= 100):

            # Adding all the latitudes and longitudes to the string to make the url for the API call
            addresses_string = ""
            for i in cluster_dict[cluster]:
                lon = i["longitude"]
                lat = i["latitude"]
                addresses_string += f"{lon},{lat};"
            
            #remove the last semicolor
            addresses_string = addresses_string[:-1]

            # By default the json response gives duration (time in seconds) instead of distance(m), so we have to specify
            url = "http://router.project-osrm.org/table/v1/driving/" + addresses_string + "?annotations=distance"
            osrm_response = requests.get(url)

            # Check the HTTP status code
            if osrm_response.status_code != 200:
                raise Exception(f"OSRM API request failed with status code {osrm_response.status_code} for cluster {cluster}")

            try:
                data = osrm_response.json()
            except ValueError:
                raise Exception(f"OSRM API returned invalid JSON for cluster {cluster}")

            # Check the OSRM response has a valid code
            if data.get("code") != "Ok":
                raise Exception(f"OSRM API returned an error: {data.get('code')} - {data.get('message', 'No message provided')}")

            # Check the distances key actually exists
            if "distances" not in data:
                raise Exception(f"OSRM API response missing 'distances' key for cluster {cluster}")

            distance_data = data["distances"]

            # Check the matrix has the expected dimensions
            if len(distance_data) == 0:
                raise Exception(f"OSRM API returned an empty distance matrix for cluster {cluster}")

            distance_matrices[cluster] = distance_data

        # Split the distance matrix into parts if it is too big and rejoin it later
        else:
            cluster_size = len(cluster_dict[cluster])
            print("Number of points in the cluster: ", cluster_size)


            # Initializing the distance matrix for the cluster
            cluster_distance_matrix = []
            for i in range(cluster_size):
                cluster_distance_matrix.append([])
                for j in range(cluster_size):
                    cluster_distance_matrix[i].append(0)

            chunk_size = 100
            # Deciding how many smaller distance matrices to split into
            no_of_splits = math.ceil((cluster_size / chunk_size))

            total_smaller_dist_matrices = no_of_splits * no_of_splits

            # Looping through each smaller chunk
            for i in range(no_of_splits):
                for j in range(no_of_splits):
                    # Math to get the correct indicies for the row and column
                    current_split_no = i*no_of_splits + j

                    row_range_lim = chunk_size if (cluster_size - i*chunk_size) > chunk_size else (cluster_size - i*chunk_size)
                    start_row_index = 0 + i*chunk_size
                    end_row_index = row_range_lim + i*chunk_size

                    col_range_lim = chunk_size if (cluster_size - j*chunk_size) > chunk_size else (cluster_size - j*chunk_size)
                    start_col_index = 0 + j*chunk_size
                    end_col_index = col_range_lim + j*chunk_size
                    
                    # print(f"For split {current_split_no}, row_ranges: {start_row_index} - {end_row_index}, col_ranges: {start_col_index} - {end_col_index}")

                    row_str_list = []
                    for row_index in range(start_row_index,end_row_index):
                        row_str_list.append(f"{cluster_dict[cluster][row_index]['longitude']},{cluster_dict[cluster][row_index]['latitude']}")

                    col_str_list = []
                    for col_index in range(start_col_index,end_col_index):
                        col_str_list.append(f"{cluster_dict[cluster][col_index]['longitude']},{cluster_dict[cluster][col_index]['latitude']}")
                    
                    # We need the sources numbers and the destination numbers
                    indexes_in_string_rows = end_row_index - start_row_index
                    indexes_in_string_cols = end_col_index - start_col_index
                    col_indicies_url = list(range(indexes_in_string_cols))
                    for col_index in range(len(col_indicies_url)):
                        col_indicies_url[col_index] = col_indicies_url[col_index] + indexes_in_string_rows

                    # adding the sources and destinations to the url because osrm does only 100 locations at a time

                    sources_str = ";".join(map(str, range(indexes_in_string_rows)))
                    dest_str = ";".join(map(str, col_indicies_url))

                    if i == j: 
                        # Sources and destinations are the same, so just send coordinates once
                        addresses_string = ";".join(row_str_list)
                        url = "http://router.project-osrm.org/table/v1/driving/" + addresses_string + "?annotations=distance"
                    else:
                        # Creating the final list of latitudes and longitudes

                        # Sources and destinations differ, so send both and specify which is which
                        final_addresses_string = ";".join(row_str_list + col_str_list)
                        url = "http://router.project-osrm.org/table/v1/driving/" + final_addresses_string + "?annotations=distance" + "&sources=" + sources_str + "&destinations=" + dest_str                    

                    osrm_response = requests.get(url)

                    # Check the HTTP status code
                    if osrm_response.status_code != 200:
                        raise Exception(f"OSRM API request failed with status code {osrm_response.status_code} for cluster {cluster}")

                    try:
                        data = osrm_response.json()
                    except ValueError:
                        raise Exception(f"OSRM API returned invalid JSON for cluster {cluster}")

                    # Check the OSRM response has a valid code
                    if data.get("code") != "Ok":
                        raise Exception(f"OSRM API returned an error: {data.get('code')} - {data.get('message', 'No message provided')}")

                    # Check the distances key actually exists
                    if "distances" not in data:
                        raise Exception(f"OSRM API response missing 'distances' key for cluster {cluster}")

                    distance_data = data["distances"]

                    # Check the matrix has the expected dimensions
                    if len(distance_data) == 0:
                        raise Exception(f"OSRM API returned an empty distance matrix for cluster {cluster}")

                    # Looping through the returned data to put in the overall cluster distance matrix
                    for distance_li_index in range(len(distance_data)):
                        for distance_index in range(len(distance_data[distance_li_index])):
                            final_row_index = i * chunk_size + distance_li_index
                            final_col_index = j * chunk_size + distance_index

                            cluster_distance_matrix[final_row_index][final_col_index] = distance_data[distance_li_index][distance_index]
                    
            # Putting the final assembled distance matrix into the cluster dictionary
            distance_matrices[cluster] = cluster_distance_matrix


    print("distance matrices: ", distance_matrices)

# incomplete code for the OR-tools
def get_best_route():

    # creating the dictionary to pass to OR-tools

    data = {}
    data["distance_matrix"] = distance_matrix[0]
    data["num_vehicles"] = 1 # change num_vehicles to how many ever needed
    data["depot"] = 0 # index for the starting location

    # creating a routing index manager
    manager = pywrapcp.RoutingIndexManager(
        len(data["distance_matrix"]), data["num_vehicles"], data["depot"]
    )

    # create routing model
    routing = pywrapcp.RoutingModel(manager)

    # create and register a transit callback
    def distance_callback(from_index, to_index):

        # returning the distance between two nodes
        
        # converting from routing variable index to distance matrix NodeIndex
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)

        return data["distance_matrix"][from_node][to_node]
    
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)

    # defining cost of each arc
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Add Distance Constraint 
    dimension_name = "Distance"
    routing.AddDimension(
        transit_callback_index,
        0, # no slack
        3000, # vehicle maximum travel distance
        True, # start cumul to zero
        dimension_name
    )