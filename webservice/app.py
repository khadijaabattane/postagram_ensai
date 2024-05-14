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

from pydantic import BaseModel

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
    # Générer un ID unique pour le post
    post_id = str(uuid.uuid4())
    
    # Sauvegarder le post dans DynamoDB
    item = {
        "user": f"USER#khadija+{post_id}",  # Clé de partition
        "id": f"#POST#{post_id}",  # Clé de tri
        "title": post.title,
        "Body": post.body       
    }
    response = table.put_item(Item=item)
    # Code pour sauvegarder dans DynamoDB
    logger.info(f"Saved post with ID: {post_id}")
    return {"message": "Post saved successfully", "data": item}


@app.get("/posts")
async def get_all_posts(post: Union[str, None] = None):
    # Get all posts from DynamoDB
    response = table.scan()
    posts = response['Items']
    return {"message": "Posts retrieved successfully", "data": posts}

@app.get("/posts")
async def get_posts_by_user(user: str = None):
    if user:
        response = table.scan(FilterExpression=Attr('user').begins_with(f"USER#{user}"))
        posts = response['Items']
        return {"message": f"Posts retrieved successfully for user {user}", "data": posts}
    else:
        # Si aucun utilisateur n'est spécifié, retourner toutes les publications
        response = table.scan()
        posts = response['Items']
        return {"message": "All posts retrieved successfully", "data": posts}

@app.get("/posts/{user}")
async def get_user_posts(user: str):
    response = table.scan(FilterExpression=Attr('user').begins_with(f"USER#{user}"))
    posts = response['Items']
    return {"message": f"Posts retrieved successfully for user {user}", "data": posts}
	
@app.get("/signedUrlPut")
async def get_signed_url_put(filename: str,filetype: str, postId: str,authorization: str | None = Header(default=None)):
    return getSignedUrl(filename, filetype, postId, authorization)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80, log_level="debug")

