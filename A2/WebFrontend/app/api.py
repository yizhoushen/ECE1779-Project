from app import webapp
from flask import render_template, request, jsonify, g
import os
import requests
import base64
import hashlib
import boto3

import mysql.connector
from app.config import db_config, s3_bucket, aws_access_key, aws_secret_key
from app.main import memcache_track

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


@webapp.route('/api/upload', methods=['POST'])
def upload_api():
    if 'key' not in request.form or request.form.get('key') == '':
        response = jsonify({
            "success": "false",
            "error": {
                "code": 400,
                "message": "Missing key"
            }
        })
        return response
    
    if 'file' not in request.files or request.files['file'] == '':
        response = jsonify({
            "success": "false",
            "error": {
                "code": 400,
                "message": "Missing file"
            }
        })
        return response
    
    new_key = request.form.get("key")
    new_image = request.files['file']

    # invalidate key in memcache_track
    if new_key in memcache_track.keys():
        memcache_track.pop(new_key)

    memcache_ip_dict = {}
    node_count = 0

    cnx = get_db()
    cursor = cnx.cursor()
    query = ''' SELECT MemcacheID, PublicIP FROM memcachelist '''
    cursor.execute(query)
    for row in cursor:
        memcache_id = row[0]
        public_ip = row[1]
        if public_ip == 'waiting':
            continue
        memcache_ip_dict[memcache_id] = public_ip
        node_count = node_count + 1

    # get md5 hash
    image_key_md5 = hashlib.md5(new_key.encode()).hexdigest()
    print("upload md5 hashing: {}".format(image_key_md5))
    if len(image_key_md5) < 32:
        partition = 0
    else:
        partition = image_key_md5[0]
    print("upload md5 partition: {}".format(partition))
    node_ip = memcache_ip_dict[int(partition, base=16) % node_count]
    print("upload node_ip: {}".format(node_ip)) 

    # invilidate memcache
    data = {'key': new_key}
    response = requests.post("http://{}:5001/invalidateKey".format(node_ip), data=data, timeout=5)
    res_json = response.json()
    if res_json['success'] == 'True':
        pass
    else:
        response = jsonify({
            "success": "false",
            "error": {
                "code": 400,
                "message": "Failed to invalidate key in memcache from ip {}".format(node_ip)
            }
        })
        return response
    
    # Save key and path to database
    s = new_image.filename.split(".")
    file_extension = s[len(s)-1]
    dbimage_path = "{}.{}".format(new_key, file_extension)

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
    
    response = jsonify({"success": "true"})
    return response

@webapp.route('/api/list_keys', methods=['POST'])
def list_keys_api():
    cnx = get_db()
    cursor = cnx.cursor()
    query = "SELECT ImageID FROM imagelist"
    cursor.execute(query)

    keylist = []
    for row in cursor:
        keylist.append(row[0])
    
    response = jsonify({"success": "true",
                        "keys": keylist })
    return response

@webapp.route('/api/key/<key_value>', methods=['POST', 'GET'])
def get_key_api(key_value):
    node_count = 0
    memcache_ip_dict = {}
    cnx = get_db()
    cursor = cnx.cursor()
    query = ''' SELECT MemcacheID, PublicIP FROM memcachelist '''
    cursor.execute(query)
    for row in cursor:
        memcache_id = row[0]
        public_ip = row[1]
        if public_ip == 'waiting':
            continue
        memcache_ip_dict[memcache_id] = public_ip
        node_count = node_count + 1

    # get md5 hash
    image_key_md5 = hashlib.md5(key_value.encode()).hexdigest()
    print("display md5 hashing: {}".format(image_key_md5))
    if len(image_key_md5) < 32:
        partition = 0
    else:
        partition = image_key_md5[0]
    node_ip = memcache_ip_dict[int(partition, base=16) % node_count]
    print("display node_ip: {}".format(node_ip))

    data = {'key': key_value}
    response = requests.post("http://{}:5001/get".format(node_ip), data=data, timeout=5)
    res_json = response.json()
    if res_json['success'] == 'True':
        
        encoded_string = res_json['content']

        # save key_value in memcache_track
        memcache_track[key_value] = encoded_string
        memcache_track.move_to_end(key=key_value, last=True)

        response_from_auto = requests.post("http://127.0.0.1:5003/new_get_requests", timeout=5)
        res_auto_json = response_from_auto.json()
        if res_auto_json['success'] == 'True':
            pass
        else:
            response = jsonify({
                "success": "false",
                "error": {
                    "code": 400,
                    "message": "Failed to send new_get_requests to auto scaler"
                }
            })
            return response

        response = jsonify({"success": "true",
                            "content": encoded_string })
        return response
    else:
        cnx = get_db()
        cursor = cnx.cursor()
        query = ''' SELECT ImagePath FROM imagelist
                    WHERE ImageID = %s'''
        cursor.execute(query, (key_value,))
        row = cursor.fetchone()
        
        if row == None:
            response = jsonify({
                "success": "false",
                "error": {
                    "code": 400,
                    "message": "No such key"
                }
            })
            return response

        image_path = row[0]

        # bucket = s3.Bucket(s3_bucket['name'])
        s3 = boto3.client('s3',
                          region_name='us-east-1',
                          aws_access_key_id=aws_access_key,
                          aws_secret_access_key=aws_secret_key
                          )
        image_file = s3.get_object(Bucket=s3_bucket['name'], Key=image_path)['Body'].read()
        encoded_string = base64.b64encode(image_file).decode('utf-8')
        print("Getting from local file system: \n {}".format(encoded_string[:10]))

        # save key_value in memcache_track
        memcache_track[key_value] = encoded_string
        memcache_track.move_to_end(key=key_value, last=True)
        
        data = {'key': key_value, 'value': encoded_string}
        response = requests.post("http://{}:5001/put_kv".format(node_ip), data=data, timeout=10)
        res_json = response.json()
        if res_json['success'] == 'True':
            
            response_from_auto = requests.post("http://127.0.0.1:5003/new_get_requests", timeout=5)
            res_auto_json = response_from_auto.json()
            if res_auto_json['success'] == 'True':
                pass
            else:
                response = jsonify({
                    "success": "false",
                    "error": {
                        "code": 400,
                        "message": "Failed to send new_get_requests to auto scaler"
                    }
                })
                return response

            response = jsonify({"success": "true",
                                "content": encoded_string })
            return response
        else:
            response = jsonify({
                "success": "false",
                "error": {
                    "code": 400,
                    "message": "No response from backend memcache"
                }
            })
            return response


# test api
@webapp.route('/api_test_1', methods=['POST', 'GET'])
def api_test_1():
    return render_template("api_test.html")

# alternative tests for api 2 & 3
# also can be tested in /api_test_1
@webapp.route('/api_test_2', methods=['POST', 'GET'])
def api_test_2():
    response = requests.post("http://127.0.0.1:5000/api/list_keys", timeout=5)
    print("Response from api/key_list: {}".format(response.text))
    return "okkkk2"

@webapp.route('/api_test_3', methods=['POST', 'GET'])
def api_test_3():
    response = requests.post("http://127.0.0.1:5000/api/key/badkey", timeout=5)
    print("Response from api/key_list: {}".format(response.text))
    return "okkkk3"