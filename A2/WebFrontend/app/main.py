
from flask import render_template, url_for, request, g
from app import webapp
from flask import jsonify
from datetime import datetime, timedelta
from collections import OrderedDict

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


memcache_track = OrderedDict()

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
    
    # invalidate key in memcache_track
    if new_key in memcache_track.keys():
        memcache_track.pop(new_key)

    node_count = 0
    memcache_ip_list = {}
    cnx = get_db()
    cursor = cnx.cursor()
    query = ''' SELECT MemcacheID, PublicIP FROM memcachelist '''
    cursor.execute(query)
    for row in cursor:
        memcache_id = row[0]
        public_ip = row[1]
        if public_ip == 'waiting':
            continue
        memcache_ip_list[memcache_id] = public_ip
        node_count = node_count + 1

    print("node count: {}".format(node_count))
    # get md5 hash
    image_key_md5 = hashlib.md5(new_key.encode()).hexdigest()
    print("upload md5 hashing: {}".format(image_key_md5))
    if len(image_key_md5) < 32:
        partition = 0
    else:
        partition = image_key_md5[0]
    print("upload md5 partition: {}".format(partition))
    node_ip = memcache_ip_list[int(partition, base=16) % node_count]
    print("upload node_ip: {}".format(node_ip))      

    # invilidate memcache
    data = {'key': new_key}
    response = requests.post("http://{}:5001/invalidateKey".format(node_ip), data=data, timeout=5)
    res_json = response.json()
    if res_json['success'] == 'True':
        pass
    else:
        return "Failed to invalidate key in memcache from ip {}".format(node_ip)
    
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

    # return "Success"
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

    node_count = 0
    memcache_ip_list = {}
    cnx = get_db()
    cursor = cnx.cursor()
    query = ''' SELECT MemcacheID, PublicIP FROM memcachelist '''
    cursor.execute(query)
    for row in cursor:
        memcache_id = row[0]
        public_ip = row[1]
        if public_ip == 'waiting':
            continue
        memcache_ip_list[memcache_id] = public_ip
        node_count = node_count + 1

    # get md5 hash
    image_key_md5 = hashlib.md5(image_key.encode()).hexdigest()
    print("display md5 hashing: {}".format(image_key_md5))
    if len(image_key_md5) < 32:
        partition = 0
    else:
        partition = image_key_md5[0]
    node_ip = memcache_ip_list[int(partition, base=16) % node_count]
    print("display node_ip: {}".format(node_ip))
    # first try getting from memcache
    data = {'key': image_key}
    response = requests.post("http://{}:5001/get".format(node_ip), data=data, timeout=5)
    print("response type from memcache/get: {}".format(type(response.json())))
    res_json = response.json()

    if res_json['success'] == 'True':
        # display encodeed image string from memcache
        encoded_string = res_json['content']
        read_end = time.time()
        duration = (read_end - read_start) * 1000
        print("time used for reading from memcache: {}".format(duration))
        print("Getting from memory cache: \n {}".format(encoded_string[:10]))

        # save key_value in memcache_track
        memcache_track[image_key] = encoded_string
        memcache_track.move_to_end(key=image_key, last=True)

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

        # save key_value in memcache_track
        memcache_track[image_key] = encoded_string
        memcache_track.move_to_end(key=image_key, last=True)

        # save image to memcache
        data = {'key': image_key, 'value': encoded_string}
        response = requests.post("http://{}:5001/put_kv".format(node_ip), data=data, timeout=5)
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

@webapp.route('/redistribute', methods=['POST'])
def redistribute():
    node_count = 0
    memcache_ip_list = {}
    cnx = get_db()
    cursor = cnx.cursor()
    query = ''' SELECT MemcacheID, PublicIP FROM memcachelist '''
    cursor.execute(query)
    for row in cursor:
        memcache_id = row[0]
        public_ip = row[1]
        memcache_ip_list[memcache_id] = public_ip
        node_count = node_count + 1
    
    for key, value in memcache_track.items():
        print("memcache_track key: {} ".format(key))
        print("memcache_track value: {}".format(value[:10]))
        image_key_md5 = hashlib.md5(key.encode()).hexdigest()
        if len(image_key_md5) < 32:
            partition = 0
        else:
            partition = image_key_md5[0]
        node_ip = memcache_ip_list[int(partition, base=16) % node_count]
        print("target node ip: {}".format(node_ip))
        key_to_invalid = {'key': key}
        key_value = {'key': key, 'value': value}
        for memcache_id, curr_public_ip in memcache_ip_list.items():
            print("memcache id: {}".format(memcache_id))
            print("public ip: {}".format(curr_public_ip))
            if curr_public_ip == node_ip:
                print("a")
                response = requests.post("http://{}:5001/put_kv".format(curr_public_ip), data=key_value, timeout=5)
                res_json = response.json()
                print("aaaa")
                if res_json['success'] == 'True':
                    pass
                else:
                    message = 'Failed to get repsonse from memcache/put_kv from ip {}'.format(curr_public_ip)
                    return jsonify(success='False', message=message) 
            else:
                print("b")
                response = requests.post("http://{}:5001/invalidateKey".format(curr_public_ip), data=key_to_invalid, timeout=5)
                res_json = response.json()
                print("bbbb")
                if res_json['success'] == 'True':
                    pass
                else:
                    message = 'Failed to invalidate key in memcache from ip {}'.format(curr_public_ip)
                    return jsonify(success='False', message=message)
            time.sleep(1)
    return jsonify(success='True')

# @webapp.route('/api_test', methods=['POST', 'GET'])
# def test_api():
#     response = requests.post("http://127.0.0.1:5000/api/list_keys", timeout=5)
#     print("Response from api/key_list: {}".format(response.text))
#     return "okkkk"