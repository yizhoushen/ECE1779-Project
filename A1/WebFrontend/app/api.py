from app import webapp
from flask import render_template, request, jsonify, g
import os
import requests
import base64

import mysql.connector
from app.config import db_config

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

    # invilidate memcache
    data = {'key': new_key}
    response = requests.post("http://127.0.0.1:5001/invalidateKey", data=data, timeout=5)
    
    # path saved in database is ./static/images/<new_key>.<file_extension>
    s = new_image.filename.split(".")
    file_extension = s[len(s)-1]
    temp_path = os.path.join("./static/images", "{}.{}".format(new_key, file_extension))
    dbimage_path = temp_path.replace("\\", "/")

    cnx = get_db()
    cursor = cnx.cursor()

    query_overwrite = '''   INSERT INTO imagelist(ImageID, ImagePath)
                            VALUES(%s, %s) as newimage
                            ON DUPLICATE KEY UPDATE ImagePath=newimage.ImagePath'''

    cursor.execute(query_overwrite, (new_key, dbimage_path))
    cnx.commit()

    temp_path = os.path.join(os.path.abspath("./A1/WebFrontend/app"), dbimage_path)
    save_path = temp_path.replace("\\", "/")
    new_image.save(save_path)
    
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
    data = {'key': key_value}
    response = requests.post("http://127.0.0.1:5001/get", data=data, timeout=5)
    res_json = response.json()
    if res_json['success'] == 'True':
        encoded_string = res_json['content']
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

        temp_path = os.path.join(os.path.abspath("./A1/WebFrontend/app"), image_path)
        read_path = temp_path.replace("\\", "/")

        with open(read_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read())
        
        data = {'key': key_value, 'value': encoded_string}
        response = requests.post("http://127.0.0.1:5001/put_kv", data=data, timeout=5)
        res_json = response.json()
        if res_json['success'] == 'True':
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