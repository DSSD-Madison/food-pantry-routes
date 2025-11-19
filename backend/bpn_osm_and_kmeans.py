

import time
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import pandas as pd


dataset = pd.read_excel("../../data.xlsx")
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


# OSRM Trip Optimization
import requests

def get_optimized_route(coordinates, start_coord=[42.995268, -89.514444]):
    """
    Use OSRM Trip API to get optimized route for a set of coordinates

    Args:
        coordinates: List of [lat, lon] pairs
        start_coord: [lat, lon] for starting point

    Returns:
        Returns optimized order, distance (km), and duration (minutes)
        dict with 'distance' (meters), 'duration' (seconds), 'waypoint_order', 'geometry'
    """
 
    # Add start coordinate as first point
    all_coords = [start_coord] + coordinates
  
    # OSRM expects lon,lat (not lat,lon)
    coord_strings = [f"{lon},{lat}" for lat, lon in all_coords]
    coords_param = ";".join(coord_strings)

    # Calling the TRIP service from ORSM. Use the coords as our parameter
    url = f"http://router.project-osrm.org/trip/v1/driving/{coords_param}"
    params = {
        "source": "first",  # Start at first coordinate
        "roundtrip": "true",  # Return to start
        "geometries": "geojson"  # Get route geometry
    }

    try:
        #send API request with params from above. time out error goes out at 30 secs.
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()  # immed throw error if there's error
        result = response.json()

        if result['code'] == 'Ok':
            trip = result['trips'][0] #the subtrip the waypoints belong to, always 0 since we do only one trip per cluster.
            waypoints = result['waypoints']

            # Get the optimized order (waypoint_index tells you the order)
            waypoint_order = [wp['waypoint_index'] for wp in waypoints]

            # Extract leg-by-leg distances and times
            legs_data = []
            for leg in trip['legs']:
                legs_data.append({
                    'distance_meters': leg['distance'],
                    'duration_seconds': leg['duration'],
                    'distance_km': round(leg['distance'] / 1000, 2),
                    'duration_minutes': round(leg['duration'] / 60, 2)
                })

            return {
                'distance_meters': trip['distance'],
                'duration_seconds': trip['duration'],
                'distance_km': round(trip['distance'] / 1000, 2),
                'duration_minutes': round(trip['duration'] / 60, 2),
                'waypoint_order': waypoint_order,
                'waypoints': waypoints,
                'legs': legs_data,
                'geometry': trip['geometry'],
                'status': 'success'
            }
        else:
            return {'status': 'error', 'message': result.get('message', 'Unknown error')}

    except Exception as e:
        return {'status': 'error', 'message': str(e)}


# Process each cluster and get optimized routes
cluster_routes = []
cluster_details = {}  # Store detailed info for Excel export

for cluster_id in range(N_CLUSTERS):
  
    # Get all points in this cluster
    cluster_mask = results_df['cluster'] == cluster_id
    cluster_points = results_df[cluster_mask].reset_index(drop=True)

    # Extract coordinates as [[lat, lon], [lat, lon], ...]
    coords = [[row['latitude'], row['longitude']] for _, row in cluster_points.iterrows()]

    if len(coords) == 0:
        print("  No points in this cluster")
        continue

    route_result = get_optimized_route(coords)

    if route_result['status'] == 'success':
        # detailed route information for Excel
        route_details = []
        waypoint_order = route_result['waypoint_order'] 
        legs = route_result['legs']

        # First entry is start location (index 0 in waypoint_order)
        route_details.append({
            'Stop Number': 0,
            'Location': 'START LOCATION',
            'Address': '1200 E Verona Ave Verona WI ',
            'Latitude': 42.995268,
            'Longitude': -89.514444,
            'Distance to Next (km)': legs[0]['distance_km'] if len(legs) > 0 else 0,
            'Time to Next (min)': legs[0]['duration_minutes'] if len(legs) > 0 else 0
        })

        # Add each stop in optimized order
        for i in range(1, len(waypoint_order)):
            # waypoint_order[i] tells us which original point this is
            # Subtract 1 because waypoint 0 is start location, waypoints 1+ are the actual stops
            original_index = waypoint_order[i] - 1

            if original_index >= 0 and original_index < len(cluster_points):
                point = cluster_points.iloc[original_index]
                leg_index = i  # The leg from this waypoint to the next

                route_details.append({
                    'Stop Number': i,
                    'Location': f'Stop {i}',
                    'Address': point['address'],
                    'Latitude': point['latitude'],
                    'Longitude': point['longitude'],
                    'Distance to Next (km)': legs[leg_index]['distance_km'] if leg_index < len(legs) else 0,
                    'Time to Next (min)': legs[leg_index]['duration_minutes'] if leg_index < len(legs) else 0
                })

        # Add final return to start location
        route_details.append({
            'Stop Number': len(waypoint_order),
            'Location': 'START LOCATION (Return)',
            'Address': '1200 E Verona Ave Verona WI ',
            'Latitude': 42.995268,
            'Longitude': -89.514444,
            'Distance to Next (km)': 0,
            'Time to Next (min)': 0
        })

        cluster_details[cluster_id] = pd.DataFrame(route_details)

        cluster_routes.append({
            'cluster_id': cluster_id,
            'num_stops': len(coords),
            'distance_km': route_result['distance_km'],
            'duration_minutes': route_result['duration_minutes'],
            'waypoint_order': route_result['waypoint_order'],
            'geometry': route_result['geometry']
        })
    else:
        print(f"  ERROR: {route_result['message']}")

    # Rate limiting to API calls
    time.sleep(1)

#Write to excel sheet 
output_file = 'route_optimization_results.xlsx'
with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
    # Summary sheet
    summary_df = pd.DataFrame(cluster_routes)
    summary_df = summary_df[['cluster_id', 'num_stops', 'distance_km', 'duration_minutes']]
    summary_df.columns = ['Cluster ID', 'Number of Stops', 'Total Distance (km)', 'Total Duration (min)']
    summary_df.to_excel(writer, sheet_name='Summary', index=False)

    # Add totals row to summary
    totals_row = pd.DataFrame([{
        'Cluster ID': 'TOTAL',
        'Number of Stops': summary_df['Number of Stops'].sum(),
        'Total Distance (km)': summary_df['Total Distance (km)'].sum(),
        'Total Duration (min)': summary_df['Total Duration (min)'].sum()
    }])

    # Individual cluster sheets
    for cluster_id, details_df in cluster_details.items():
        sheet_name = f'Cluster {cluster_id}'
        details_df.to_excel(writer, sheet_name=sheet_name, index=False)

print(f"Results exported to: {output_file}")

# elbow method
import matplotlib.pyplot as plt

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

latitude = []
longitude = []
for i in data:
  latitude.append(i.get("latitude"))
  longitude.append(i.get("longitude"))
plt.plot(latitude,longitude,'o')
plt.show()
