from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Any
import pandas as pd
from io import BytesIO

app = FastAPI()

# Allow frontend (Vite dev server) to talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/upload-spreadsheet")
async def upload_spreadsheet(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Unsupported file type. Use .csv, .xlsx, or .xls")

    contents = await file.read()

    try:
        if file.filename.lower().endswith(".csv"):
            df = pd.read_csv(BytesIO(contents))
        else:
            df = pd.read_excel(BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read spreadsheet: {e}")

    return {
        "filename": file.filename,
        "columns": list(df.columns),
        "rows": df.to_dict(orient="records"),
    }
