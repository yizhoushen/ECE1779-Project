import app
from flask import render_template, redirect, url_for, request, g
from app import webapp
from app.config import db_config, s3_bucket, aws_access_key, aws_secret_key
import mysql.connector
import requests
import time
import boto3
from boto3.dynamodb.conditions import Key
import base64

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

@webapp.teardown_appcontext
def teardown_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@webapp.route('/display_form', methods=['GET'])
def display_form():
    if app.userid == None:
        return "Access Denied! Please Login!"
    else:
        pass
    return render_template("display_form.html", title="Select Image Key")

@webapp.route('/image_display', methods=['POST'])
def image_display():
    if app.userid == None:
        return "Access Denied! Please Login!"
    else:
        pass
    
    read_start = time.time()
    if 'image_key' not in request.form:
        return "Need a image key"

    image_key = request.form.get('image_key')

    if image_key == '':
        return "Need a image key"

    # first try getting from memcache
    data = {'key': image_key}
    response = requests.post("http://127.0.0.1:5001/get", data=data, timeout=5)
    print("response type from memcache/get: {}".format(type(response.json())))
    res_json = response.json()

    if res_json['success'] == 'True':
        # display encodeed image string from memcache
        encoded_string = res_json['content']
        read_end = time.time()
        duration = (read_end - read_start) * 1000
        print("time used for reading from memcache: {}".format(duration))
        return render_template("image_display.html", title="Image Display", encoded_string=encoded_string)
    else:
        print("No Such image in memcache, getting from local file system...")

        cnx = get_db()
        cursor = cnx.cursor()

        query = ''' SELECT ImagePath FROM imagelist
                    WHERE ImageID = %s'''

        cursor.execute(query, (image_key,))
        row = cursor.fetchone()
        
        if row == None:
            return "No such image"

        image_path = row[0]
        image_path = get_single_image_s3loc(image_key)
        print(image_path)
        s3 = boto3.client('s3',
                          region_name='us-east-1',
                          aws_access_key_id=aws_access_key,
                          aws_secret_access_key=aws_secret_key
                          )
        image_file = s3.get_object(Bucket=s3_bucket['name'], Key=image_path)['Body'].read()
        encoded_string = base64.b64encode(image_file).decode('utf-8')
        print("Getting from S3: \n {}".format(encoded_string[:10]))
        
        data = {'key': image_key, 'value': encoded_string}
        response = requests.post("http://127.0.0.1:5001/put_kv", data=data, timeout=5)
        res_json = response.json()
        if res_json['success'] == 'True':
            read_end = time.time()
            duration = (read_end - read_start) * 1000
            print("time used for reading from local file: {}".format(duration))
            return render_template("image_display.html", title="Image Display", encoded_string=encoded_string, local_file=True)
        elif res_json['success'] == 'False':
            print("Cache failure! MemCache capacity is too small")
            return render_template("image_display.html", title="Image Display", encoded_string=encoded_string, local_file=True)
        else:
            return render_template("execute_result.html", title="Failed to get repsonse from memcache/put_kv")


def get_single_image_s3loc(key):
    table = dynamodb.Table('Images')
    response = table.get_item(
        Key={
            'user_id': app.userid,
            'image_key': key
        },
    )

    if 'Item' in response:
        pic_loc = response['Item']['pic_s3_loc']
    return pic_loc

