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
from sklearn.cluster import DBSCAN
from collections import defaultdict
from math import pi
import requests
from scipy.spatial import distance_matrix
import math
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

CACHE_FILE = "geocode_cache.json"
OSRM_RETRY_ATTEMPTS = 3
OSRM_RETRY_DELAY_SECONDS = 2
OSRM_TIMEOUT_SECONDS = 30
GEOLOCATOR_TIMEOUT = 10

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
    geolocator = Nominatim(user_agent="BNNP_Flags", timeout=GEOLOCATOR_TIMEOUT) # type: ignore

    cache = load_cache()
    geocoded_locations = []
    address = None

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

def dbscan_labels(data, minpts, epsilon_meters=200):
    x = []
    radians = pi/180
    for i in data:
        x.append([i.get("latitude") * radians, i.get("longitude") * radians])
    x = np.array(x)

    epsilon = epsilon_meters / 6371000
    db = DBSCAN(eps=epsilon, min_samples=minpts, metric="haversine").fit(x)
    return db.labels_


def remap_dbscan_labels(labels, x):
    unique_cluster_labels = sorted(label for label in set(labels) if label != -1)

    if not unique_cluster_labels:
        fallback_clusters = min(max(1, len(x) // 8), len(x))
        fallback_labels, _ = balanced_kmeans(x, fallback_clusters)
        return fallback_labels

    cluster_points = {
        label: x[np.array(labels) == label]
        for label in unique_cluster_labels
    }
    cluster_centers = {
        label: points.mean(axis=0)
        for label, points in cluster_points.items()
    }

    reassigned_labels = []
    for point, label in zip(x, labels):
        if label != -1:
            reassigned_labels.append(label)
            continue

        nearest_label = min(
            unique_cluster_labels,
            key=lambda cluster_label: np.sum((point - cluster_centers[cluster_label]) ** 2),
        )
        reassigned_labels.append(nearest_label)

    normalized_unique_labels = sorted(set(reassigned_labels))
    label_map = {
        label: index
        for index, label in enumerate(normalized_unique_labels)
    }

    return np.array([label_map[label] for label in reassigned_labels], dtype=int)


def get_groups(
    data,
    n_clusters,
    method="balanced_kmeans",
    dbscan_min_samples=2,
    dbscan_epsilon_meters=200,
):
    x = np.array([[i["latitude"], i["longitude"]] for i in data])

    if method == "dbscan":
        raw_labels = dbscan_labels(data, dbscan_min_samples, dbscan_epsilon_meters)
        cluster_labels = remap_dbscan_labels(raw_labels, x)
        unique_labels = sorted(set(cluster_labels.tolist()))
        cluster_centers = np.array([
            x[cluster_labels == label].mean(axis=0)
            for label in unique_labels
        ])
        return (cluster_labels, cluster_centers, x)

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


def fetch_osrm_distances(url, cluster, attempt_count=OSRM_RETRY_ATTEMPTS):
    last_error = None

    for attempt in range(1, attempt_count + 1):
        try:
            osrm_response = requests.get(url, timeout=OSRM_TIMEOUT_SECONDS)
        except requests.RequestException as error:
            last_error = Exception(
                f"OSRM request failed for cluster {cluster} on attempt "
                f"{attempt}/{attempt_count}: {error}"
            )
        else:
            if osrm_response.status_code == 200:
                try:
                    data = osrm_response.json()
                except ValueError as error:
                    raise Exception(
                        f"OSRM API returned invalid JSON for cluster {cluster}: {error}"
                    ) from error

                if data.get("code") != "Ok":
                    raise Exception(
                        f"OSRM API returned an error for cluster {cluster}: "
                        f"{data.get('code')} - {data.get('message', 'No message provided')}"
                    )

                if "distances" not in data:
                    raise Exception(
                        f"OSRM API response missing 'distances' key for cluster {cluster}"
                    )

                distance_data = data["distances"]
                if len(distance_data) == 0:
                    raise Exception(
                        f"OSRM API returned an empty distance matrix for cluster {cluster}"
                    )

                return distance_data

            last_error = Exception(
                f"OSRM API request failed with status code {osrm_response.status_code} "
                f"for cluster {cluster} on attempt {attempt}/{attempt_count}"
            )

            if osrm_response.status_code not in {429, 500, 502, 503, 504}:
                break

        if attempt < attempt_count:
            time.sleep(OSRM_RETRY_DELAY_SECONDS * attempt)

    raise last_error if last_error is not None else Exception(
        f"OSRM request failed for cluster {cluster}"
    )

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
        if len(cluster_dict[cluster]) < 2:
            distance_matrices[cluster] = [[0]]
            continue
        
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
            distance_matrices[cluster] = fetch_osrm_distances(url, cluster)

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

                    distance_data = fetch_osrm_distances(url, cluster)

                    # Looping through the returned data to put in the overall cluster distance matrix
                    for distance_li_index in range(len(distance_data)):
                        for distance_index in range(len(distance_data[distance_li_index])):
                            final_row_index = i * chunk_size + distance_li_index
                            final_col_index = j * chunk_size + distance_index

                            cluster_distance_matrix[final_row_index][final_col_index] = distance_data[distance_li_index][distance_index]
                    
            # Putting the final assembled distance matrix into the cluster dictionary
            distance_matrices[cluster] = cluster_distance_matrix

    print("distance matrices: ", distance_matrices)
    return(distance_matrices, cluster_dict)

def print_solution(data, manager, routing, solution):
    """Prints solution on console."""
    # print(f"Objective: {solution.ObjectiveValue()}")
    
    solution_data = {}

    max_route_distance = 0
    for vehicle_id in range(data["num_vehicles"]):
        if not routing.IsVehicleUsed(solution, vehicle_id):
            continue
        index = routing.Start(vehicle_id)
        plan_output = f"Route for vehicle {vehicle_id}:\n"
        route_distance = 0
        while not routing.IsEnd(index):
            plan_output += f" {manager.IndexToNode(index)} -> "
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_distance += routing.GetArcCostForVehicle(
                previous_index, index, vehicle_id
            )
        plan_output += f"{manager.IndexToNode(index)}\n"
        plan_output += f"Distance of the route: {route_distance}m\n"
        
        vehicle_data = {}
        vehicle_data["route_distance"] = route_distance
        vehicle_data["route_plan"] = plan_output

        solution_data[vehicle_id] = vehicle_data

        max_route_distance = max(route_distance, max_route_distance)

    return solution.ObjectiveValue(), solution_data, max_route_distance


def choose_open_route_endpoints(distance_matrix):
    max_distance = -1
    start_index = 0
    end_index = len(distance_matrix) - 1

    for row_index in range(len(distance_matrix)):
        for col_index in range(len(distance_matrix[row_index])):
            if row_index == col_index:
                continue

            current_distance = distance_matrix[row_index][col_index]
            if current_distance is None:
                continue

            if current_distance > max_distance:
                max_distance = current_distance
                start_index = row_index
                end_index = col_index

    return start_index, end_index

def convert_indicies_to_lat_and_long(cluster_routes, cluster_dict):
    
    path_data = {}
    
    # get latitude and longitude from geocode_address_data

    # looping through every route plan
    for cluster in cluster_routes:

        cluster_paths = {}

        cluster_data = cluster_routes[cluster]

        routes_data = cluster_data["routes_data"]
        
        # handling situation appropriately if no solution for that cluster
        if routes_data != "No solution found!":
            for route_id in routes_data:
                route_path = []

                route_plan_text = routes_data[route_id]["route_plan"]
                # removing the initial text
                route_plan_text = route_plan_text.split("\n")[1].strip()

                # For each route, now get the indicies of the location that corresponds to the index of the lat and long in the list of locations in the particular cluster in cluster_dict
                for location_index_str in route_plan_text.split("->"):
                    location_index = int(location_index_str.strip())

                    # adding the lat and long coordinates in order of their path in that cluster to cluster_path
                    route_path.append(cluster_dict[cluster][location_index])
                
                cluster_paths[route_id] = route_path
            
            path_data[cluster] = cluster_paths
        else:
            path_data[cluster] = "No Solution"
    
    return path_data


def get_best_route(geocode_address_data, n_clusters, cluster_labels):

    cluster_distance_matrix, cluster_dict = distance_matrix(geocode_address_data, n_clusters, cluster_labels)
    cluster_routes = {}

    for cluster in cluster_distance_matrix:

        cluster_data = {}

        if len(cluster_dict[cluster]) < 2:
            cluster_data["distance_matrix"] = [[0]]
            cluster_data["routes_data"] = {
                0: {
                    "route_distance": 0,
                    "route_plan": "Route for vehicle 0:\n 0\nDistance of the route: 0m\n",
                }
            }
            cluster_data["objective"] = 0
            cluster_data["max_route_distance"] = 0
            cluster_routes[cluster] = cluster_data
            continue

        # creating the dictionary to pass to OR-tools

        data = {}
        data["distance_matrix"] = cluster_distance_matrix[cluster]
        data["num_vehicles"] = 1 # change num_vehicles to how many ever needed
        start_index, end_index = choose_open_route_endpoints(data["distance_matrix"])
        data["starts"] = [start_index]
        data["ends"] = [end_index]

        # creating a routing index manager
        manager = pywrapcp.RoutingIndexManager(
            len(data["distance_matrix"]),
            data["num_vehicles"],
            data["starts"],
            data["ends"],
        )

        # create routing model
        routing = pywrapcp.RoutingModel(manager)

        # create and register a transit callback
        def distance_callback(from_index, to_index):

            # returning the distance between two nodes
            
            # converting from routing variable index to distance matrix NodeIndex
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)

            return int(round(data["distance_matrix"][from_node][to_node]))
        
        transit_callback_index = routing.RegisterTransitCallback(distance_callback)

        # defining cost of each arc
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        print("Works till defining the cost of each arc")

        # Add Distance Constraint 
        dimension_name = "Distance"
        routing.AddDimension(
            transit_callback_index,
            0, # no slack
            999999999, # vehicle maximum travel distance (setting it high temporarily)
            True, # start cumul to zero
            dimension_name
        )
        distance_dimension = routing.GetDimensionOrDie(dimension_name)
        distance_dimension.SetGlobalSpanCostCoefficient(100)

        # Setting first solution heuristic
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        search_parameters.time_limit.seconds = 30

        # Solve the problem
        print("Starting solver...")
        solution = routing.SolveWithParameters(search_parameters)
        print("Solver finished!")

        cluster_data["distance_matrix"] = data["distance_matrix"]

        # saving the solution if it exists in the dictionary
        if solution:                        
            objective, routes_data, max_route_distance = print_solution(data, manager, routing, solution)
            cluster_data["routes_data"] = routes_data
            cluster_data["objective"] = objective
            cluster_data["max_route_distance"] = max_route_distance
        else:
            cluster_data["routes_data"] = "No solution found!"
            cluster_data["objective"] = "N/A"
            cluster_data["max_route_distance"] = "N/A"
        
        cluster_routes[cluster] = cluster_data
    
    # print("Cluster Routes: ", cluster_routes)

    cluster_paths = convert_indicies_to_lat_and_long(cluster_routes, cluster_dict)

    print("cluster_paths: ", cluster_paths)

    return cluster_paths
