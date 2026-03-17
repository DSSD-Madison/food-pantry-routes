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


def normalize_cell_value(value: Any) -> Any:
    if pd.isna(value):
        return None

    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()

    return value


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: normalize_cell_value(value)
        for key, value in record.items()
    }


def insert_grouping_record(payload: dict[str, Any]) -> None:
    try:
        supabase.table("groupings").insert(payload).execute()
    except Exception as error:
        error_message = str(error)
        missing_best_routes_column = (
            "best_routes" in error_message
            and "column" in error_message.lower()
        )

        if not missing_best_routes_column:
            raise

        payload_without_best_routes = {
            key: value
            for key, value in payload.items()
            if key != "best_routes"
        }
        supabase.table("groupings").insert(payload_without_best_routes).execute()

@app.post("/upload-spreadsheet")
async def upload_spreadsheet(
    number_of_groups: int = Form(..., gt=0),
    clustering_method: str = Form("balanced_kmeans"),
    dbscan_min_samples: int = Form(2, gt=0),
    dbscan_epsilon_meters: int = Form(1500, gt=0),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    
    if file.filename == None: # Ensure a file was actually uploaded even though FastAPI should handle this case
        raise HTTPException(status_code=400, detail="No file uploaded")
    
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

    addresses = df["Address"]  + " " + df["City"] + " " + df["State"]

    print("Calling geocode_addresses")
    # getting the latitude and longitutde of all the locations
    geocoded_data = bpn_osm_and_kmeans.geocode_addresses(addresses)
    print("geocoded_data: ", geocoded_data)
    
    cluster_method = clustering_method.strip().lower()
    if cluster_method not in {"balanced_kmeans", "dbscan"}:
        raise HTTPException(status_code=400, detail="Unsupported clustering method")

    kmeans_grp_data = bpn_osm_and_kmeans.get_groups(
        geocoded_data,
        number_of_groups,
        method=cluster_method,
        dbscan_min_samples=dbscan_min_samples,
        dbscan_epsilon_meters=dbscan_epsilon_meters,
    )[0]
    cluster_labels = kmeans_grp_data

    group_count = len(set(int(label) for label in cluster_labels))
    groups = [[] for _ in range(group_count)]

    row_records = df.to_dict(orient="records")

    for i in range(len(geocoded_data)):
        location_dict = normalize_record(dict(row_records[i]))
        location_dict["Location"] = geocoded_data[i].get("full_result")
        location_dict["latitude"] = geocoded_data[i].get("latitude")
        location_dict["longitude"] = geocoded_data[i].get("longitude")
        location_dict["geocoded_address"] = geocoded_data[i].get("address")

        group = int(cluster_labels[i])

        groups[group].append(location_dict)

    best_routes = bpn_osm_and_kmeans.get_best_route(
        geocoded_data,
        group_count,
        cluster_labels,
    )
    
    # Elbow method for kmeans
    # elbow_method.elbow_method_graph(x)

    # Generating the kmeans graph
    # bpn_osm_and_kmeans.generate_kmeans_grouping_graph(geocoded_data, number_of_groups, cluster_labels)

    # Auto-save grouping to database
    try:
        insert_grouping_record({
            "filename": file.filename,
            "number_of_groups": group_count,
            "columns": list(df.columns),
            "groups": groups,
            "best_routes": best_routes,
        })
    except Exception as e:
        print(f"Warning: Failed to auto-save grouping to database: {str(e)}")

    return {
        "filename": file.filename,
        "columns": list(df.columns),
        "groups": groups,
        "best_routes": best_routes,
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
        "groups": list[list[dict]],
        "best_routes": dict | None
    }
    """
    try:
        payload = {
            "filename": data["filename"],
            "number_of_groups": data["number_of_groups"],
            "columns": data["columns"],
            "groups": data["groups"],
            "best_routes": data.get("best_routes"),
        }
        insert_grouping_record(payload)
        result = supabase.table("groupings").select("id").order("created_at", desc=True).limit(1).execute()
        
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
