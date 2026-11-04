"""Crea el bucket local y su CORS. Se puede ejecutar varias veces sin efectos nuevos."""

import sys

from botocore.exceptions import BotoCoreError, ClientError

from app.config import get_settings
from app.storage import get_s3_client


def init_storage() -> None:
    settings = get_settings()
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") not in {"404", "NoSuchBucket"}:
            raise
        # S3 rechaza LocationConstraint en us-east-1 y lo exige en las demás Regiones.
        if settings.aws_region == "us-east-1":
            client.create_bucket(Bucket=settings.s3_bucket)
        else:
            client.create_bucket(
                Bucket=settings.s3_bucket,
                CreateBucketConfiguration={"LocationConstraint": settings.aws_region},  # type: ignore[typeddict-item]
            )
    client.put_bucket_cors(
        Bucket=settings.s3_bucket,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedOrigins": settings.cors_origins,
                    "AllowedMethods": ["GET", "PUT"],
                    "AllowedHeaders": ["content-type"],
                    "MaxAgeSeconds": 3000,
                }
            ]
        },
    )


def main() -> int:
    if get_settings().s3_endpoint_url is None:
        print("S3_ENDPOINT_URL vacío: este script es solo para el S3 local", file=sys.stderr)
        return 1
    try:
        init_storage()
    except (BotoCoreError, ClientError) as error:
        print(f"No se pudo preparar el bucket: {error}", file=sys.stderr)
        return 1
    print(f"Bucket listo: {get_settings().s3_bucket}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
