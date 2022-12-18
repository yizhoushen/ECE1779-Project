import app
from flask import render_template, redirect, url_for, request, g
from app import webapp
from app.config import db_config, s3_bucket, aws_access_key, aws_secret_key
import mysql.connector
import requests
import time
import boto3
from boto3.dynamodb.conditions import Key


images_tag = {}
public = True

dynamodb = boto3.resource('dynamodb',
                          region_name='us-east-1',
                          aws_access_key_id=aws_access_key,
                          aws_secret_access_key=aws_secret_key)

def connect_to_database():
    return mysql.connector.connect(user=db_config['user'],
                                   password=db_config['password'],
                                   host=db_config['host'],
                                   database=db_config['database'])

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = connect_to_database()
    return db

def detect_labels(key, photo):
    global images_tag
    aggregate_labels = []
    client=boto3.client('rekognition')
    response = client.detect_labels(Image={'Bytes': photo}, MaxLabels=10)

    for label in response['Labels']:
        if label['Confidence'] > 90:
            aggregate_labels.append(label['Name'])
    images_tag[key] = aggregate_labels

    return aggregate_labels

@webapp.teardown_appcontext
def teardown_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@webapp.route('/upload_form', methods=['GET'])
def upload_form():
    if app.userid == None:
        return "Access Denied! Please Login!"
    else:
        pass
    return render_template("upload_form.html", title="Upload Image")

@webapp.route('/image_upload', methods=['POST'])
def image_upload():
    if app.userid == None:
        return "Access Denied! Please Login!"
    else:
        pass

    write_start = time.time()
    if 'uploaded_key' not in request.form:
        return render_template("execute_result.html", title="Missing image key")

    if 'uploaded_image' not in request.files:
        return render_template("execute_result.html", title="Missing uploaded image")

    new_key = request.form.get('uploaded_key')
    new_image = request.files['uploaded_image']
    # new_image_bytes = new_image.read()
    print("new_image: {}".format(new_image))
    # print("new image_bytes: {}".format(new_image_bytes[:10]))

    if new_key == '':
        return render_template("execute_result.html", title="Image key is empty")
    if new_image.filename == '':
        return render_template("execute_result.html", title="Missing file name")

    # invilidate memcache
    data = {'key': new_key}
    response = requests.post("http://127.0.0.1:5001/invalidateKey", data=data, timeout=5)
    res_json = response.json()
    if res_json['success'] == 'True':
        pass
    else:
        return render_template("execute_result.html", title="Failed to invalidate key in memcache")

    # Save key and path to database
    s = new_image.filename.split(".")
    file_extension = s[len(s)-1]
    # temp_path = os.path.join("./static/images", "{}.{}".format(new_key, file_extension))
    # dbimage_path = temp_path.replace("\\", "/")
    user = app.userid.replace("@", "_").replace(".", "_")
    dbimage_path = "{}_{}.{}".format(user, new_key, file_extension)

    cnx = get_db()
    cursor = cnx.cursor()
    query_overwrite = '''   INSERT INTO imagelist(ImageID, ImagePath)
                            VALUES(%s, %s) as newimage
                            ON DUPLICATE KEY UPDATE ImagePath=newimage.ImagePath'''

    cursor.execute(query_overwrite, (new_key, dbimage_path))
    cnx.commit()

    # Save file to S3
    s3 = boto3.client('s3',
                      region_name='us-east-1',
                      aws_access_key_id=aws_access_key,
                      aws_secret_access_key=aws_secret_key
                      )
    s3.upload_fileobj(new_image, s3_bucket['name'], dbimage_path)

    # Get image file from S3
    new_image_bytes = s3.get_object(Bucket=s3_bucket['name'], Key=dbimage_path)['Body'].read()
    print("new image: {}".format(new_image_bytes[:10]))

    # label the uploaded image file
    img_labels = detect_labels(new_key, new_image_bytes)
    print('The number of detected labels for {} is {}'.format(new_key, str(len(img_labels))))
    print(images_tag)

    write_end = time.time()
    duration = (write_end - write_start) * 1000
    print("time used for writing: {}".format(duration))

    #put image info into Table2(Images)
    response = put_image_Item(new_key, img_labels, dbimage_path, public, location=None)
    print(response)

    # put tag info into Table3(Tags)
    user_img_pair = app.userid + "_" + new_key
    for tag in img_labels:
        re = put_tag_Item(tag, user_img_pair, public, dbimage_path)


    # update the column "public_or_not" if it changed
    if public == False:
        img_labels = get_image_labels(new_key)
        response = tag_update(img_labels, user_img_pair, public)

    return render_template("execute_result.html", title="Upload image successfully")


def put_image_Item(key, labels, s3_loc, public, location):
    table = dynamodb.Table('Images')
    response = table.put_item(
        Item={
            'user_id': app.userid,
            'image_key': key,
            'labels': labels,
            'pic_s3_loc': s3_loc,
            'public_or_not': public,
            'location': location
        }
    )
    return 'image item upload to dynamodb successfully'

def get_image_labels(key):
    data = {}
    table = dynamodb.Table('Tags')
    response = table.get_item(
        Key={
            'user_id': app.userid,
            'image_key': key,
        },
        # ProjectionExpression="tag",
    )

    if 'Item' in response:
        item = response['Item']
        data.update(item)

    return data['labels']


def tag_update(labels, user_img_pair, public):
    table = dynamodb.Table('Tags')
    for tag in labels:
        response = table.update_item(
           Key={
                'tag': tag,
                'user_img': user_img_pair,
            },
            UpdateExpression = "SET #p = :p",
            ExpressionAttributeValues = {
                ':p': public
            },
            ExpressionAttributeNames = {"#p": "public_or_not"}

        )
    return 'success'


def put_tag_Item(tag, user_img_pair, public, s3_loc):
    table = dynamodb.Table('Tags')

    response = table.put_item(
        Item={
            'tag': tag,
            'user_img': user_img_pair,
            'public_or_not': public,
            'pic_s3_loc': s3_loc
        }
    )
    return 'success'

