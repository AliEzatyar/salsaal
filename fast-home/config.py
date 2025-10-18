from os import environ as env
import boto3
from decouple import config

AWS_S3_REGION_NAME = config(
    "AWS_S3_REGION_NAME"
)  # change if your bucket is in another region
AWS_S3_SIGNATURE_VERSION = config("AWS_S3_SIGNATURE_VERSION")
AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME")

s3 = boto3.client(
    "s3",
    region_name=AWS_S3_REGION_NAME,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    config=boto3.session.Config(signature_version=AWS_S3_SIGNATURE_VERSION),
)
