import boto3
from botocore.config import Config
import os
from dotenv import load_dotenv
from typing import Union
import logging
from fastapi import FastAPI, Request, status, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import uuid
from getSignedUrl import getSignedUrl
from boto3.dynamodb.conditions import Key, Attr
from pydantic import BaseModel
from urllib.parse import urlparse
app = FastAPI()

load_dotenv()

app = FastAPI()
logger = logging.getLogger("uvicorn")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
	exc_str = f'{exc}'.replace('\n', ' ').replace('   ', ' ')
	logger.error(f"{request}: {exc_str}")
	content = {'status_code': 10422, 'message': exc_str, 'data': None}
	return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class Post(BaseModel):
    title: str
    body: str


my_config = Config(
    region_name='us-east-1',
    signature_version='v4',
)

dynamodb = boto3.resource('dynamodb', config=my_config)
table = dynamodb.Table(os.getenv("DYNAMO_TABLE"))
s3_client = boto3.client('s3', config=boto3.session.Config(signature_version='s3v4'))
bucket = os.getenv("BUCKET")


@app.post("/posts")
async def post_a_post(post: Post, authorization: str | None = Header(default=None)):
    post_id = str(uuid.uuid4())
    item = {
        "user": f"USER#{authorization}",  
        "id": f"POST#{post_id}",  
        "title": post.title,
        "Body": post.body       
    }
    response = table.put_item(Item=item)
    logger.info(f"Saved post with ID: {post_id}")
    return {
        "user": item["user"],
	"id": item["id"],
        "title": item["title"],
        "body": item["Body"],
        "image": item.get("image", ""),  
        "labels": item.get("labels", "")
    }
@app.get("/posts")
async def get_all_posts(user: Union[str, None] = None):
    if user:
        response = table.scan(
            FilterExpression=Attr('user').eq(f"USER#{user}")
        )
    else:
        response = table.scan()

    posts = response['Items']
    formatted_posts = []
    for post in posts:
        formatted_post = {
            "user": post.get("user", ""),
            "id": post.get("id", ""),
            "title": post.get("title", ""),
            "body": post.get("Body", ""),
            "image": post.get("image", ""),  
            "labels": post.get("labels", "")
        }
        formatted_posts.append(formatted_post)
    return formatted_posts


def extract_bucket_key_from_presigned_url(url):
    parsed_url = urlparse(url)
    bucket_name = parsed_url.netloc.split('.')[0]
    key = parsed_url.path.lstrip('/')
    return bucket_name, key

@app.delete("/posts/{post_id}")
async def delete_post(post_id: str, authorization: str = Header(None)):
    post_id = "POST#" + post_id
    
    user_id = "USER#"+authorization  

    try:
        # Query the table to find the item by post_id
        response = table.scan(
            FilterExpression="id = :id",
            ExpressionAttributeValues={":id": post_id}
        )

        items = response.get('Items', [])
        if not items:
            raise HTTPException(status_code=404, detail="Post not found")

        # Assume the first item is the one we want to delete (since post_id should be unique)
        item = items[0]

        # Validate that the user making the request is the owner of the post
        if item['user'] != user_id:
            raise HTTPException(status_code=403, detail="Permission denied")

        # Get the S3 URL and extract the bucket name and key if the image URL is not empty
        s3_url = item.get('image', '')
        if s3_url:
            bucket_name, object_key = extract_bucket_key_from_presigned_url(s3_url)
            # Delete the S3 object
            s3_client.delete_object(Bucket=bucket_name, Key=object_key)
            logger.info(f"Deleted S3 object: {s3_url}")

        # Delete the item using partition key and sort key
        delete_response = table.delete_item(
            Key={
                'user': user_id,
                'id': post_id
            }
        )

        if delete_response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
            logger.info(f"Deleted post with ID: {post_id}")
            return delete_response
        else:
            raise HTTPException(status_code=500, detail="Failed to delete post")

    except Exception as e:
        logger.error(f"Error deleting post with ID {post_id}: {e}")
        raise HTTPException(status_code=500, detail="Error deleting post")


	
@app.get("/signedUrlPut")
async def get_signed_url_put(filename: str,filetype: str, postId: str,authorization: str | None = Header(default=None)):
    return getSignedUrl(filename, filetype, postId, authorization)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="debug")

