"""Upload the tile archives to S3 (served through CloudFront).

Reads credentials from the standard AWS environment variables
(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION) and the bucket
name from LA_TILES_BUCKET.

    python prototype/upload_tiles.py [--check] [file ...]

Uploads both archives by default, or only the named ones (e.g. la-vector-v2.pmtiles).
--check only verifies the credentials can see the bucket.
CloudFront caches files for a day. When a file's contents change in a way the page depends
on, give it a new name (la-vector-v2 -> v3) and point index.html at it, so the live site
keeps working until the new page is merged; otherwise invalidate the path in CloudFront.
"""
import argparse
import os
import sys

FILES = ["la-raster.pmtiles", "la-vector-v2.pmtiles"]
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("files", nargs="*", default=FILES)
    args = ap.parse_args()
    bucket = os.environ.get("LA_TILES_BUCKET")
    missing = [v for v in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION") if not os.environ.get(v)]
    if not bucket or missing:
        sys.exit(f"Set LA_TILES_BUCKET and {', '.join(missing) or 'the AWS variables'} in the environment.")

    import boto3
    from boto3.s3.transfer import TransferConfig

    s3 = boto3.client("s3")
    listing = s3.list_objects_v2(Bucket=bucket, MaxKeys=20)
    print(f"bucket {bucket}: {[o['Key'] for o in listing.get('Contents', [])]}")
    if args.check:
        return

    config = TransferConfig(multipart_threshold=64 * 1024 ** 2, multipart_chunksize=64 * 1024 ** 2, max_concurrency=8)
    for name in args.files:
        path = os.path.join(HERE, "data", name)
        size = os.path.getsize(path)
        print(f"uploading {name} ({size / 1e6:.0f} MB)...", flush=True)
        s3.upload_file(path, bucket, name, Config=config, ExtraArgs={
            "ContentType": "application/octet-stream",
            "CacheControl": "public, max-age=86400",
        })
        head = s3.head_object(Bucket=bucket, Key=name)
        assert head["ContentLength"] == size, f"{name}: uploaded {head['ContentLength']} bytes, expected {size}"
        print(f"  ok, {head['ContentLength']:,} bytes, ETag {head['ETag']}")


if __name__ == "__main__":
    main()
