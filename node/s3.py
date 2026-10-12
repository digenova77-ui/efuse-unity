#!/usr/bin/env python3
"""s3.py — minimal S3 client for the Amsterdam object store.

Credentials come from the environment ONLY (never stored, never printed):
    DCLM_S3_KEY       the GK... access key id (shown once by object-init)
    DCLM_S3_SECRET    the 64-hex-char secret

Usage:
    s3.py ls   <bucket> [prefix]
    s3.py put  <bucket> <key> <local-file>
    s3.py get  <bucket> <key> <local-file>

Endpoint defaults to the Amsterdam lane; override with DCLM_S3_ENDPOINT.
"""
import os
import sys

ENDPOINT = os.environ.get("DCLM_S3_ENDPOINT", "http://45.76.33.16:3900")


def client():
    try:
        import boto3
    except ImportError:
        sys.exit("s3.py: boto3 not installed (bootstrap installs it via pip)")
    key = os.environ.get("DCLM_S3_KEY")
    secret = os.environ.get("DCLM_S3_SECRET")
    if not key or not secret:
        sys.exit("s3.py: set DCLM_S3_KEY and DCLM_S3_SECRET in the environment")
    return boto3.session.Session().client(
        "s3", endpoint_url=ENDPOINT, region_name="garage",
        aws_access_key_id=key, aws_secret_access_key=secret)


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: s3.py ls <bucket> [prefix] | put <bucket> <key> <file> | get <bucket> <key> <file>")
    cmd, bucket = sys.argv[1], sys.argv[2]
    c = client()
    if cmd == "ls":
        prefix = sys.argv[3] if len(sys.argv) > 3 else ""
        pag = c.get_paginator("list_objects_v2")
        for page in pag.paginate(Bucket=bucket, Prefix=prefix):
            for o in page.get("Contents", []):
                print(f"{o['Size']:>12}  {o['Key']}")
    elif cmd == "put":
        _, _, key, path = sys.argv[1:5]
        c.upload_file(path, bucket, key)
        print(f"put s3://{bucket}/{key}")
    elif cmd == "get":
        _, _, key, path = sys.argv[1:5]
        c.download_file(bucket, key, path)
        print(f"get s3://{bucket}/{key} -> {path}")
    else:
        sys.exit(f"unknown command: {cmd}")


if __name__ == "__main__":
    main()
