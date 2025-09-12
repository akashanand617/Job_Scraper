#!/usr/bin/env python3
"""
AWS Lambda handler for LinkedIn Job Scraper
Handles both scheduled events and HTTP requests

Enhancements:
- Robust detection of HTTP vs scheduled events
- Environment-driven configuration for scraping parameters
- Optional S3 upload of batch results when JOBS_BUCKET is set
- Consistent UTC timestamps
"""

import os
import json
import asyncio
import uuid
from datetime import datetime, timezone
import traceback
from mangum import Mangum
from simple_api import app, run_analytics_task

# Create FastAPI handler for HTTP requests
mangum_handler = Mangum(app, lifespan="off")

# ----------------------------------------------------------------------------
# Environment-driven configuration (with sensible defaults)
# ----------------------------------------------------------------------------
KEYWORDS = os.getenv(
    "KEYWORDS",
    "AI OR Machine Learning OR Data Science OR Generative AI OR LLM OR Large Language Model OR Prompt Engineering OR Foundation Model OR Transformer OR RAG OR Reinforcement Learning With Human Feedback OR RLHF",
)
MAX_SHARDS = int(os.getenv("MAX_SHARDS", "126"))
TIME_FILTER = os.getenv("TIME_FILTER", "r3600")  # last 1 hour
DEFAULT_SIZE = int(os.getenv("BATCH_SIZE", "18"))
JOBS_BUCKET = os.getenv("JOBS_BUCKET")  # optional S3 bucket name


def is_http_event(event: dict) -> bool:
    """Detect API Gateway/Lambda URL/ALB events by shape."""
    if not isinstance(event, dict):
        return False
    request_context = event.get("requestContext", {})
    # REST API v1
    if "httpMethod" in event and "path" in event and "isBase64Encoded" in event:
        return True
    # HTTP API v2
    if event.get("version") == "2.0" and request_context:
        return True
    # Generic presence of http context
    if "http" in request_context:
        return True
    return False


def is_scheduled_event(event: dict) -> bool:
    """Detect EventBridge/CloudWatch scheduled events or manual batch invocations."""
    if not isinstance(event, dict):
        return False
    
    # Check for EventBridge/CloudWatch scheduled events
    source = event.get("source", "")
    detail_type = event.get("detail-type", "")
    if detail_type == "Scheduled Event" or source in ("aws.events", "aws.eventbridge.scheduler"):
        return True
    
    # Check for manual batch invocations (has batch_number and batch_size)
    if "batch_number" in event and "batch_size" in event:
        return True
    
    # Check for batch invocations nested in detail (EventBridge format)
    detail = event.get("detail", {})
    if isinstance(detail, dict) and "batch_number" in detail and "batch_size" in detail:
        return True
    
    return False

async def run_scheduled_scraping(batch_number: int, batch_size: int, job_id: str):
    """Run batch scraping task and optionally upload results to S3."""
    print(f"🚀 Running batch {batch_number}/{batch_size} | job_id={job_id}")
    tmp_path = "/tmp/analytics_historical_jobs.json"

    try:
        # Execute analytics task with environment-driven parameters
        await run_analytics_task(
            job_id=job_id,
            keywords=KEYWORDS,
            max_shards=MAX_SHARDS,
            time_filter=TIME_FILTER,
            exp_codes=None,  # All experience levels
            jt_codes=None,   # All job types
            wt_codes=None,   # All workplace types
            batch_size=batch_size,
            batch_number=batch_number,
            jobs_file=tmp_path,
        )

        # Optional: Upload result file to S3
        if JOBS_BUCKET:
            try:
                import boto3
                s3_client = boto3.client("s3")
                s3_key = f"jobs/hourly/{datetime.now(timezone.utc).date()}/batch_{batch_number}.json"
                s3_client.upload_file(tmp_path, JOBS_BUCKET, s3_key)
                print(f"📦 Uploaded to s3://{JOBS_BUCKET}/{s3_key}")
            except Exception as s3_err:
                print(f"⚠️ S3 upload failed: {s3_err}")

        print(f"✅ Scheduled scraping completed - Batch {batch_number}")
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": f"Scheduled scraping completed - Batch {batch_number}",
                "job_id": job_id,
                "batch_number": batch_number,
                "batch_size": batch_size,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }),
        }

    except Exception as e:
        print(f"❌ Scheduled scraping failed - Batch {batch_number}: {str(e)}")
        print("TRACE:")
        print(traceback.format_exc())
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": f"Scheduled scraping failed - Batch {batch_number}: {str(e)}",
                "job_id": job_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }),
        }

def handler(event, context):
    """Main Lambda handler - scheduled events to batch; all else to FastAPI."""
    try:
        # Log a concise summary of the event for debugging
        print("EVENT SUMMARY:")
        print(json.dumps({
            "keys": list(event.keys()) if isinstance(event, dict) else str(type(event)),
            "source": event.get("source") if isinstance(event, dict) else None,
            "detail_type": event.get("detail-type") if isinstance(event, dict) else None,
            "version": event.get("version") if isinstance(event, dict) else None,
        }))
    except Exception:
        pass

    if is_scheduled_event(event):
        print("📅 Scheduled event detected")
        src = event.get("detail") or event
        
        # Regular batch scraping event
        batch_number = int(src.get("batch_number", 1))
        batch_size = int(src.get("batch_size", DEFAULT_SIZE))
        job_id = getattr(context, "aws_request_id", str(uuid.uuid4()))
        try:
            return asyncio.run(run_scheduled_scraping(batch_number, batch_size, job_id))
        except Exception as e:
            print(f"❌ Top-level scheduled dispatch failed: {e}")
            print("TRACE:")
            print(traceback.format_exc())
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": f"Top-level scheduled dispatch failed: {str(e)}",
                    "job_id": job_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }),
            }

    # Default: treat as HTTP and route to FastAPI
    print("🌐 Non-scheduled event - routing to FastAPI")
    try:
        return mangum_handler(event, context)
    except RuntimeError as e:
        if "no current event loop" in str(e):
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return mangum_handler(event, context)
            finally:
                loop.close()
        else:
            raise

# For local testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
