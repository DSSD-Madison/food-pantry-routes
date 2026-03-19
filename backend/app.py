from typing import Any
from io import BytesIO
import math
import os
from datetime import datetime

import bpn_osm_and_kmeans
import elbow_method

import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env file")

supabase: Client = create_client(supabase_url, supabase_key)

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
        else:
            df = pd.read_excel(BytesIO(contents))

        df = df.dropna(axis=1, how="all").loc[:, (df != "").any()]
        df = df.dropna(subset=["Address"])

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
    cluster_labels = kmeans_grp_data

    groups = [[] for _ in range(number_of_groups)]

    for i in range(len(geocoded_data)):
        location_dict = {"Location" : geocoded_data[i]["full_result"]}

        group = int(cluster_labels[i])

        groups[group].append(location_dict)
    
    # Elbow method for kmeans
    # elbow_method.elbow_method_graph(x)

    # Generating the kmeans graph
    bpn_osm_and_kmeans.generate_kmeans_grouping_graph(geocoded_data, number_of_groups, cluster_labels)

    return {
        "filename": file.filename,
        "columns": list(df.columns),
        "groups": groups,
    }


@app.post("/save-grouping")
async def save_grouping(
    data: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    """
    Save a grouping to Supabase database.
    Expected data format:
    {
        "filename": str,
        "number_of_groups": int,
        "columns": list[str],
        "groups": list[list[dict]]
    }
    """
    try:
        result = supabase.table("groupings").insert({
            "filename": data["filename"],
            "number_of_groups": data["number_of_groups"],
            "columns": data["columns"],
            "groups": data["groups"]
        }).execute()
        
        return {
            "success": True,
            "id": result.data[0]["id"],
            "message": "Grouping saved successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save grouping: {str(e)}")


@app.get("/groupings")
async def get_groupings() -> dict[str, Any]:
    """
    Retrieve all saved groupings from database, ordered by creation date (newest first).
    """
    try:
        result = supabase.table("groupings").select("*").order("created_at", desc=True).execute()
        return {
            "success": True,
            "groupings": result.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve groupings: {str(e)}")


@app.delete("/groupings/{grouping_id}")
async def delete_grouping(grouping_id: str) -> dict[str, Any]:
    """
    Delete a specific grouping by ID.
    """
    try:
        result = supabase.table("groupings").delete().eq("id", grouping_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Grouping not found")
            
        return {
            "success": True,
            "message": "Grouping deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete grouping: {str(e)}")

