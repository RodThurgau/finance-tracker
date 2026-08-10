"""CSV upload endpoint: preclean → detect → parse → upsert → summary."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from parsers import ing, paypal
from parsers.detect import Source, detect_source
from parsers.preclean import NoHeaderFound, preclean
from schemas import ImportSummarySchema
from services.upsert import upsert

router = APIRouter(prefix="/api/v1/import", tags=["import"])

# How many preamble lines to echo back in a NoHeaderFound error, so a wrong
# file is obvious without dumping the whole upload into the response.
PREAMBLE_LINES_IN_ERROR = 5

PARSERS = {Source.ING: ing, Source.PAYPAL: paypal}


@router.post("/csv", response_model=ImportSummarySchema)
async def import_csv(file: UploadFile, db: Session = Depends(get_db)) -> ImportSummarySchema:
    raw = await file.read()

    try:
        precleaned = preclean(raw)
    except NoHeaderFound as exc:
        preview = exc.scanned_lines[:PREAMBLE_LINES_IN_ERROR]
        detail = str(exc)
        if preview:
            detail += ". First lines of the file:\n" + "\n".join(preview)
        raise HTTPException(status_code=422, detail=detail) from exc

    source = detect_source(precleaned.header_line)
    parsed = PARSERS[source].parse(precleaned)

    summary = upsert(db, source, parsed)
    db.commit()

    return ImportSummarySchema.model_validate(summary)
