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
username = 'username'

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

    return len(aggregate_labels)

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
    dbimage_path = "{}.{}".format(new_key, file_extension)

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
    num_labels = detect_labels(new_key, new_image_bytes)
    print('The number of detected labels for {} is {}'.format(new_key, str(num_labels)))
    print(images_tag)

    write_end = time.time()
    duration = (write_end - write_start) * 1000
    print("time used for writing: {}".format(duration))

    # data = {'tableName': username, 'key': new_key, 'labels': images_tag[new_key]}
    # response = requests.post("http://127.0.0.1:5001/putItem", data=data)
    return render_template("execute_result.html", title="Upload image successfully")