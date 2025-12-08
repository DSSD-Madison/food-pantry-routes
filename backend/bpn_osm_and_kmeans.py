import time
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import pandas as pd
from sklearn.cluster import KMeans
import numpy as np
import matplotlib.pyplot as plt
import matplotlib

def geocode_addresses(address_list):
  """
    Gives the latitudes and longitudes of a list of locations

    Args:
        address_list (<class 'pandas.core.series.Series'>): one-dimensional labeled array of location names

    Returns:
        list: List of dictionaries which contain information of the latitude and longitutde of each location
    """
  geolocator = Nominatim(user_agent = "BNNP_Flags",timeout = 10) #not including timeout = 10 was giving a lot of errors
  geocoded_locations=[]
  try:
    for address in address_list:
      address_temp = geolocator.geocode(address)
      if address_temp:
        print(f"Found, {address} at {address_temp.latitude} and {address_temp.longitude}")
        geocoded_locations.append({ "address": address,
                    "latitude": address_temp.latitude,
                    "longitude": address_temp.longitude,
                    "full_result": address_temp.address})
      else:
        print(f"{address} FAILED could not find address")
      time.sleep(1) #API Limit can max make 1 request per second
  except (GeocoderTimedOut, GeocoderUnavailable) as e:
            # Handle potential server errors or timeouts
            print(f"ERROR:   '{address}'  ({e})")
  return geocoded_locations

def get_groups(data, n_clusters):
  """
    Creates the clusters of locations

    Args:
        address_list (<class 'pandas.core.series.Series'>): one-dimensional labeled array of location names

    Returns:
        list: List of dictionaries which contain information of the latitude and longitutde of each location
    """

  x = []
  for i in data:
    x.append([i.get("latitude"),i.get("longitude")])
  x= np.array(x)


  # idk what random_state does but keep it for now
  kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
  kmeans.fit(x)


  cluster_labels = kmeans.labels_
  cluster_centers = kmeans.cluster_centers_

  return (cluster_labels, cluster_centers, x)

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
