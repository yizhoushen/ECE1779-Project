import app
from flask import render_template, redirect, url_for, request, g
from app import webapp
from app.config import db_config, s3_bucket, aws_access_key, aws_secret_key
import mysql.connector
import requests
import time
import boto3
from boto3.dynamodb.conditions import Key

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

@webapp.route('/config_form', methods=['GET'])
def config_form():
    if app.userid == None:
        return "Access Denied! Please Login!"
    else:
        pass
    return render_template("config_form.html", title="Configure Memory Cache")

@webapp.route('/config_mem_cache', methods=['POST'])
def config_mem_cache():
    if app.userid == None:
        return "Access Denied! Please Login!"
    else:
        pass
    
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
