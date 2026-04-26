import io
import os
from pathlib import Path

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd
from botocore.exceptions import ClientError

from utils.logger import get_logger

logger = get_logger(__name__)

RAW_BUCKET = os.getenv("RAW_BUCKET_NAME")
LOCAL_RAW_PATH = os.getenv("LOCAL_RAW_PATH", "/tmp/crypto-pipeline-raw")


def _use_local() -> bool:
    return not RAW_BUCKET


def write_parquet(df: pd.DataFrame, s3_key: str) -> str:
    """Write DataFrame as Parquet to S3 or local filesystem. Returns the destination path."""
    table = pa.Table.from_pandas(df, preserve_index=False)

    if _use_local():
        local_path = Path(LOCAL_RAW_PATH) / s3_key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, local_path)
        logger.debug(f"Wrote local: {local_path}")
        return str(local_path)

    buf = io.BytesIO()
    pq.write_table(table, buf)
    buf.seek(0)

    s3 = boto3.client("s3")
    s3.put_object(Bucket=RAW_BUCKET, Key=s3_key, Body=buf.getvalue())
    dest = f"s3://{RAW_BUCKET}/{s3_key}"
    logger.debug(f"Wrote S3: {dest}")
    return dest


def read_parquet_if_exists(s3_key: str) -> pd.DataFrame | None:
    """Return existing Parquet file as a DataFrame, or None if it doesn't exist."""
    if _use_local():
        local_path = Path(LOCAL_RAW_PATH) / s3_key
        if not local_path.exists():
            return None
        return pd.read_parquet(local_path)

    s3 = boto3.client("s3")
    try:
        obj = s3.get_object(Bucket=RAW_BUCKET, Key=s3_key)
        buf = io.BytesIO(obj["Body"].read())
        return pd.read_parquet(buf)
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return None
        raise


def file_exists(s3_key: str) -> bool:
    """Check whether a file already exists — used to enforce idempotency."""
    if _use_local():
        return (Path(LOCAL_RAW_PATH) / s3_key).exists()

    s3 = boto3.client("s3")
    try:
        s3.head_object(Bucket=RAW_BUCKET, Key=s3_key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise
