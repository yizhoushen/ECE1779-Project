
from flask import render_template, url_for, request, g
from app import webapp, memcache
from flask import json
from datetime import datetime, timedelta

import mysql.connector
from app.config import db_config, s3_bucket, aws_access_key, aws_secret_key
import sys

import tempfile
import os
import time

import requests
import base64

import boto3

# os.chdir(os.path.abspath("./A1/WebFrontend"))

images_tag = {}

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

@webapp.route('/',methods=['GET'])
@webapp.route('/main',methods=['GET'])
def main():
    return render_template("main.html")

@webapp.route('/upload_form', methods=['GET'])
def upload_form():
    return render_template("upload_form.html", title="Upload Image")

@webapp.route('/image_upload', methods=['POST'])
def image_upload():
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

    return render_template("execute_result.html", title="Upload image successfully")


@webapp.route('/display_form', methods=['GET'])
def display_form():
    return render_template("display_form.html", title="Select Image Key")

@webapp.route('/image_display', methods=['POST'])
def image_display():
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



@webapp.route('/all_keys', methods=['GET'])
def all_keys():
    cnx = get_db()

    cursor = cnx.cursor()

    query = "SELECT * FROM imagelist"

    cursor.execute(query)

    return render_template("keylist.html", title="ImageID List", cursor=cursor)


@webapp.route('/config_form', methods=['GET'])
def config_form():
    return render_template("config_form.html", title="Configure Memory Cache")

@webapp.route('/config_mem_cache', methods=['POST'])
def config_mem_cache():
    if 'cache_clear' not in request.form and 'cache_configure' in request.form:
        if 'memcache_size' not in request.form:
            return "Missing MemCache size"
        
        if 'memcache_policy' not in request.form:
            return "Missing MemCache Replacement Policy"
        
        memcache_szie = request.form.get('memcache_size')
        memcache_policy = request.form.get('memcache_policy')

        if memcache_szie == '':
            return 'MemCache size is empty'
        if memcache_policy == '':
            return 'MemCache Replacement Policy is empty'
        if memcache_policy != '0' and memcache_policy != '1':
            return 'Invalid Replacement Policy'

        cnx = get_db()
        cursor = cnx.cursor()

        query = ''' UPDATE configuration
                    SET Capacity = %s,
                        ReplacePolicy = %s
                    WHERE id = 1'''

        cursor.execute(query, (memcache_szie, int(memcache_policy)))
        cnx.commit()
        
        response = requests.post("http://127.0.0.1:5001/refreshConfiguration", timeout=5)
        res_json = response.json()
        if res_json['success'] == 'True':
            return render_template("execute_result.html", title="Cache configuration is successful")
        elif res_json['success'] == 'False':
            return render_template("execute_result.html", title="Cache configuration failed!")
        else:
            return render_template("execute_result.html", title="Failed to get repsonse from memcache/clear")

        return "Success"
    elif 'cache_clear' in request.form and 'cache_configure' not in request.form:
        response = requests.post("http://127.0.0.1:5001/clear", timeout=5)
        res_json = response.json()
        if res_json['success'] == 'True':
            return render_template("execute_result.html", title="Cache Cleared")
        else:
            return render_template("execute_result.html", title="Failed to get repsonse from memcache/clear")
    else:
        return "Invalid! Please choose cache configure or cache clear"


@webapp.route('/statistics', methods=['GET'])
def statistics():
    cnx = get_db()
    cursor = cnx.cursor()
    query = "SELECT * FROM statistics"
    cursor.execute(query)

    start_time = datetime.now() - timedelta(minutes=10)
    return render_template("statistics.html", title="Memory Cache Statistics", cursor=cursor, start_time=start_time)

@webapp.route('/testpath', methods=['GET'])
def testpath():
    temp_path = os.path.abspath("./temp_path")
    return temp_path

# @webapp.route('/api_test', methods=['POST', 'GET'])
# def test_api():
#     response = requests.post("http://127.0.0.1:5000/api/list_keys", timeout=5)
#     print("Response from api/key_list: {}".format(response.text))
#     return "okkkk"


# @webapp.route('/detect_labels', methods=['POST'])
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

#todo
#store labels into dynamodb