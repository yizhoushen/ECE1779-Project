
from flask import render_template, url_for, request, g
from app import webapp
from flask import json
from datetime import datetime, timedelta

import mysql.connector
from app.config import db_config, ami_id, subnet_id, s3_bucket
import sys

import tempfile
import os
import time

import requests
import base64

import boto3
import hashlib

# os.chdir(os.path.abspath("./A1/WebFrontend"))

# s3 = boto3.client('s3',
#                   aws_access_key_id=aws_access['aws_access_key_id'],
#                   aws_secret_access_key=aws_access['aws_secret_access_key'])


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
        return "Missing image key"
    if 'uploaded_image' not in request.files:
        return "Missing uploaded image"
    
    new_key = request.form.get('uploaded_key')
    new_image = request.files['uploaded_image']

    if new_key == '':
        return 'Image key is empty'
    if new_image.filename == '':
        return 'Missing file name'
    
    # get md5 hash
    new_key_md5 = hashlib.md5(new_key.encode())
    partition = new_key_md5.hexdigest()[0]

    # invilidate memcache

    # todo: route request to memcache node based on partition

    data = {'key': new_key}
    response = requests.post("http://127.0.0.1:5001/invalidateKey", data=data, timeout=5)
    print(response.text)
    
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
    s3 = boto3.client('s3')
    s3.upload_fileobj(new_image, s3_bucket['name'], dbimage_path)

    write_end = time.time()
    duration = (write_end - write_start) * 1000
    print("time used for writing: {}".format(duration))

    return "Success"


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
        print("Getting from memory cache: \n {}".format(encoded_string[:10]))
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
        
        # bucket = s3.Bucket(s3_bucket['name'])
        s3 = boto3.client('s3')
        image_file = s3.get_object(Bucket=s3_bucket['name'], Key=image_path)['Body'].read()
        encoded_string = base64.b64encode(image_file).decode('utf-8')
        print("Getting from local file system: \n {}".format(encoded_string[:10]))
        
        # save image to memcache
        data = {'key': image_key, 'value': encoded_string}
        response = requests.post("http://127.0.0.1:5001/put_kv", data=data, timeout=5)
        res_json = response.json()
        if res_json['success'] == 'True':
            read_end = time.time()
            duration = (read_end - read_start) * 1000
            print("time used for reading from local file: {}".format(duration))
            return render_template("image_display.html", title="Image Display", encoded_string=encoded_string, local_file=True)
        else:
            return "Failed to get repsonse from memcache/put_kv"



@webapp.route('/all_keys', methods=['GET'])
def all_keys():
    cnx = get_db()
    cursor = cnx.cursor()
    query = "SELECT * FROM imagelist"
    cursor.execute(query)
    return render_template("keylist.html", title="ImageID List", cursor=cursor)


@webapp.route('/testpath', methods=['GET'])
def testpath():
    temp_path = os.path.abspath("./temp_path")
    return temp_path

# @webapp.route('/api_test', methods=['POST', 'GET'])
# def test_api():
#     response = requests.post("http://127.0.0.1:5000/api/list_keys", timeout=5)
#     print("Response from api/key_list: {}".format(response.text))
#     return "okkkk"