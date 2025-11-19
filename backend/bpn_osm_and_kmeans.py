

import time
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import pandas as pd


dataset = pd.read_excel("Flags_4_Food_data.xlsx")
addresses = dataset["Address"]  + " " + dataset["City"] + " " + dataset["State"]

def geocode_addresses(address_list):
  geolocator = Nominatim(user_agent = "BNNP_Flags",timeout = 10) #not including timeout = 10 was giving a lot of errors
  geocoded_locations=[]
  try:
    for address in address_list:
      if len(geocoded_locations) > 20: #remove only for testing
        break
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



data = geocode_addresses(addresses)
print(data)

from sklearn.cluster import KMeans
import numpy as np

x = []
for i in data:
  x.append([i.get("latitude"),i.get("longitude")])
x= np.array(x)

N_CLUSTERS = 5


# idk what random_state does but keep it for now
kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
kmeans.fit(x)


cluster_labels = kmeans.labels_
cluster_centers = kmeans.cluster_centers_


print(cluster_labels)
print(cluster_centers)


results_df = pd.DataFrame(data)
results_df['cluster'] = cluster_labels
print(results_df.head())

# elbow method
import matplotlib.pyplot as plt
import matplotlib

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

# List of colors for different clusters
# cluster_colors = ["blue", "green", "red", "purple", "cyan"]
print("Working till here 1")
cmap = matplotlib.colormaps['tab20']
cluster_colors = [cmap(i / N_CLUSTERS) for i in range(N_CLUSTERS)]
print("Working till here 2")

latitude = []
longitude = []
colors = []
for i in range(len(data)):
  latitude.append(data[i].get("latitude"))
  longitude.append(data[i].get("longitude"))

  # adding the respective color to the colors list depending on the cluster it belongs to
  cluster = int(cluster_labels[i])
  color = cluster_colors[cluster]
  colors.append(color)

# plt.plot(latitude,longitude,'o')
plt.scatter(latitude, longitude, c=colors)
plt.show()
