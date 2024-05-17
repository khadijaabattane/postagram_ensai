import logging
import boto3
from boto3.dynamodb.conditions import Key
import os
import json
import uuid
from pathlib import Path
from botocore.exceptions import ClientError

bucket = os.getenv("BUCKET")
s3_client = boto3.client('s3', config=boto3.session.Config(signature_version='s3v4'))
logger = logging.getLogger("uvicorn")

def getSignedUrl(filename: str,filetype: str, postId: str, user):

    filename = f'{uuid.uuid4()}{Path(filename).name}'
    object_name = f"{user}/{postId}/{filename}"
    print("file_name = "+filename)
    print("bucket =" +bucket)
    print("object_name"+object_name)
    
    try:
        urlPut = s3_client.generate_presigned_url(
            Params={
            "Bucket": bucket,
            "Key": object_name,
            "ContentType": filetype
        },
            ClientMethod='put_object'
        )
    except ClientError as e:
        logging.error(e)

    try:
        urlGet = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket,
                                                            'Key': object_name})
    except ClientError as e:
        logging.error(e)
        return None

    logger.info(f'UrlGet: {urlGet}')
    logger.info(f'UrlPut: {urlPut}')

    return {
            "uploadURL": urlGet,
            "objectName" : object_name
        }
