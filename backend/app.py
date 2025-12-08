from typing import Any
from io import BytesIO
import math

import bpn_osm_and_kmeans
import elbow_method

import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/upload-spreadsheet")
async def upload_spreadsheet(
    number_of_groups: int = Form(..., gt=0),
    file: UploadFile = File(...),
) -> dict[str, Any]:

    if not file.filename.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    contents = await file.read()

    try:
        if file.filename.lower().endswith(".csv"):
            df = pd.read_csv(BytesIO(contents))
            df = df.dropna(axis=1, how="all").loc[:, (df != "").any()]
        else:
            df = pd.read_excel(BytesIO(contents))
            df = df.dropna(axis=1, how="all").loc[:, (df != "").any()]

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read spreadsheet: {e}")

    total_rows = len(df)

    if total_rows == 0:
        return {"filename": file.filename, "columns": list(df.columns), "groups": []}

    group_size = math.ceil(total_rows / number_of_groups)

    groups: list[list[dict[str, Any]]] = []
    start = 0

    addresses = df["Address"]  + " " + df["City"] + " " + df["State"]

    print("Calling geocode_addresses")
    # getting the latitude and longitutde of all the locations
    geocoded_data = bpn_osm_and_kmeans.geocode_addresses(addresses)
    print("geocoded_data: ", geocoded_data)
    
    kmeans_grp_data = bpn_osm_and_kmeans.get_groups(geocoded_data, number_of_groups)[0]
    cluster_labels = kmeans_grp_data[0]
    x = kmeans_grp_data[2]

    groups = [[] for _ in range(number_of_groups)]

    for i in range(len(geocoded_data)):
        location_dict = {"Location" : geocoded_data[i]["full_result"]}

        group = int(cluster_labels[i])

        groups[group].append(location_dict)
    
    # Elbow method for kmeans
    # elbow_method.elbow_method_graph(x)

    # Generating the kmeans graph
    # bpn_osm_and_kmeans.generate_kmeans_grouping_graph(geocoded_data, number_of_groups, cluster_labels)

    return {
        "filename": file.filename,
        "columns": list(df.columns),
        "groups": groups,
    }

