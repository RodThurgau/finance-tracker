"""CSV upload endpoint: preclean → detect → parse → upsert → summary."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from parsers import ing, paypal
from parsers.detect import Source, detect_source
from parsers.preclean import NoHeaderFound, preclean
from schemas import ImportPreviewRow, ImportPreviewSchema, ImportSummarySchema, RowErrorSchema
from services.upsert import upsert

router = APIRouter(prefix="/api/v1/import", tags=["import"])

# How many preamble lines to echo back in a NoHeaderFound error, so a wrong
# file is obvious without dumping the whole upload into the response.
PREAMBLE_LINES_IN_ERROR = 5

# How many parsed rows the preview endpoint returns — enough to eyeball
# correctness without shipping the whole file back over the wire.
PREVIEW_ROW_COUNT = 5

PARSERS = {Source.ING: ing, Source.PAYPAL: paypal}


def _preclean_or_422(raw: bytes):
    try:
        return preclean(raw)
    except NoHeaderFound as exc:
        preview = exc.scanned_lines[:PREAMBLE_LINES_IN_ERROR]
        detail = str(exc)
        if preview:
            detail += ". First lines of the file:\n" + "\n".join(preview)
        raise HTTPException(status_code=422, detail=detail) from exc


@router.post("/preview", response_model=ImportPreviewSchema)
async def preview_csv(file: UploadFile) -> ImportPreviewSchema:
    """Preclean, detect, and parse a file without writing anything to the
    database — lets the UI show what would be imported (source, discarded
    preamble, first rows, row-level errors) before the user commits.
    """
    raw = await file.read()
    precleaned = _preclean_or_422(raw)

    # detect_source uses the same signature match preclean already used to
    # find header_line, so it cannot fail here — same as in import_csv below.
    source = detect_source(precleaned.header_line)
    parsed = PARSERS[source].parse(precleaned)

    return ImportPreviewSchema(
        source=source.value,
        preamble_lines=precleaned.preamble_lines,
        rows=[
            ImportPreviewRow(
                date=txn.date,
                description=txn.description,
                amount=txn.amount,
                currency=txn.currency,
                counter_account=txn.counter_account,
                transaction_type=txn.transaction_type,
            )
            for txn in parsed.transactions[:PREVIEW_ROW_COUNT]
        ],
        total_rows=len(parsed.transactions),
        errors=[RowErrorSchema.model_validate(error) for error in parsed.errors],
    )


@router.post("/csv", response_model=ImportSummarySchema)
async def import_csv(file: UploadFile, db: Session = Depends(get_db)) -> ImportSummarySchema:
    raw = await file.read()
    precleaned = _preclean_or_422(raw)

    source = detect_source(precleaned.header_line)
    parsed = PARSERS[source].parse(precleaned)

    summary = upsert(db, source, parsed)
    db.commit()

    return ImportSummarySchema.model_validate(summary)
