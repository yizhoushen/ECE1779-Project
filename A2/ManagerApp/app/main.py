from flask import render_template, url_for, request, g
from app import webapp_manager
from flask import json
from flask import jsonify
import requests
import mysql.connector
from app.config import db_config, ami_id, subnet_id, s3_bucket
from datetime import datetime, timedelta
import jyserver.Flask as jsf
import boto3

# s3 = boto3.resource('s3',
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

# def get_memcache_count():
#     cnx = get_db()
#     cursor = cnx.cursor()
#     query_get_memcache_count = '''SELECT COUNT(memcacheID) FROM memcachelist WHERE activeStatus = true'''
#     cursor.execute(query_get_memcache_count)
#     row = cursor.fetchone()
#     count = row[0]
#     return count

@webapp_manager.teardown_appcontext
def teardown_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# global
new_node_count = 0
memcache_list = {0: 'i-0b71b0a8514c4a69d (does not matter)'}
user_data = '''#!/bin/bash
cd /home/ubuntu/ECE1779-Project
source venv/bin/activate
cd A2
bash start.sh'''

def create_ec2():
    ec2 = boto3.resource('ec2')
    instances = ec2.create_instances(
        ImageId='ami-0b3a8a363dc47e0eb',
        MinCount=1,
        MaxCount=1,
        InstanceType="t2.micro",
        KeyName="ece1779-2nd-acc",
        UserData=user_data
    )
    instance = instances[0]
    return instance

def delete_ec2(instance_id):
    ec2 = boto3.client('ec2')
    ec2.terminate_instances(InstanceIds = [instance_id])

#Create/terminate or Start/Stop the instance?
def start_ec2(instance_id):
    ec2 = boto3.client('ec2')
    ec2.start_instances(InstanceIds=[instance_id])

def stop_ec2(instance_id):
    ec2 = boto3.client('ec2')
    ec2.stop_instances(InstanceIds=[instance_id])

@webapp_manager.route('/', methods=['GET'])
@webapp_manager.route('/main', methods=['GET'])
def main():
    return render_template("main.html")

@jsf.use(webapp_manager)
class App:
    def __init__(self) -> None:
        self.count = new_node_count

    def increment(self):
        if self.count < 8:
            self.count += 1
        self.js.document.getElementById('node_count').innerHTML = self.count
        global new_node_count
        new_node_count = self.count

    def decrement(self):
        if self.count > 1:
            self.count -= 1
        self.js.document.getElementById('node_count').innerHTML = self.count
        global new_node_count
        new_node_count = self.count


@webapp_manager.route('/statistics', methods=['GET'])
def statistics():
    cnx = get_db()
    cursor = cnx.cursor()
    query = "SELECT * FROM statistics"
    cursor.execute(query)

    start_time = datetime.now() - timedelta(minutes=10)
    return render_template("statistics.html", title="Memory Cache Statistics", cursor=cursor, start_time=start_time)

@webapp_manager.route('/config_form', methods=['GET'])
def config_form():
    return render_template("config_form.html", title="Configure Memory Cache")

@webapp_manager.route('/config_mem_cache', methods=['POST'])
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
            return "Cache configuration is successful"
        elif res_json['success'] == 'False':
            return "Cache configuration failed!"
        else:
            return "Failed to get repsonse from memcache/clear"

    elif 'cache_clear' in request.form and 'cache_configure' not in request.form:
        response = requests.post("http://127.0.0.1:5001/clear", timeout=5)
        res_json = response.json()
        if res_json['success'] == 'True':
            return "Cache Cleared"
        else:
            return "Failed to get repsonse from memcache/clear"

    else:
        return "Invalid! Please choose cache configure or cache clear"


@webapp_manager.route('/resize_form', methods=['GET'])
def resize_form():
    # curr_node_count = get_memcache_count()
    cnx = get_db()
    cursor = cnx.cursor()
    query_get_memcache_count = '''SELECT COUNT(memcacheID) FROM memcachelist'''
    cursor.execute(query_get_memcache_count)
    row = cursor.fetchone()
    global curr_node_count
    curr_node_count = row[0]
    return App.render(render_template("resize_form.html", title="Change Memory Cache Resize Mode", curr_node_count=curr_node_count, new_node_count=new_node_count))

@webapp_manager.route('/resize_mem_cache', methods=['POST'])
def resize_mem_cache():
    if 'manual_mode' not in request.form and 'auto_mode' in request.form:

        if 'max_missrate' not in request.form:
            return "Missing Max Miss Rate threshold"
        if 'min_missrate' not in request.form:
            return "Missing Min Miss Rate threshold"
        if 'ratio_expand' not in request.form:
            return "Missing Ratio by which to expand the pool"
        if 'ratio_shrink' not in request.form:
            return "Missing Ratio by which to shrink the pool"

        max_missrate = request.form.get('max_missrate')
        min_missrate = request.form.get('min_missrate')
        ratio_expand = request.form.get('ratio_expand')
        ratio_shrink = request.form.get('ratio_shrink')

        if max_missrate == '':
            return 'Max Miss Rate threshold is empty'
        if min_missrate == '':
            return 'Min Miss Rate threshold is empty'
        if ratio_expand == '':
            return 'Ratio by which to expand the pool is empty'
        if ratio_shrink == '':
            return 'Ratio by which to shrink the pool is empty'
        if max_missrate > 1 or min_missrate < 0 or max_missrate <= min_missrate:
            return 'Invalid Thresholds!'
        if ratio_expand <= 1 or ratio_shrink < 0 or ratio_shrink >= 1:
            return 'Invalid Ratios!'

        data = {'autoscaler_mode': 1,
                'max_missrate': max_missrate,
                'min_missrate': min_missrate,
                'ratio_expand': ratio_expand,
                'ratio_shrink': ratio_shrink}

        response = requests.post("http://127.0.0.1:5003/set_autoscaler_to_automatic_mode", data=data, timeout=5)
        res_json = response.json()
        if res_json['success'] == 'True':
            return "Set auto mode is successful"
        elif res_json['success'] == 'False':
            return "Set auto mode failed!"
        else:
            return "Failed to get repsonse from autoscaler/set_autoscaler_to_automatic_mode"

        # return "1"

    elif 'manual_mode' in request.form and 'auto_mode' not in request.form:
        data = {'autoscaler_mode': 0}
        response = requests.post("http://127.0.0.1:5003/set_autoscaler_to_manual_mode", data=data, timeout=5)
        res_json = response.json()
        if res_json['success'] == 'True':
            pass
        elif res_json['success'] == 'False':
            return "Set manual mode failed!"
        else:
            return "Failed to get repsonse from autoscaler/set_autoscaler_to_manual_mode"

        cnx = get_db()

        if new_node_count > curr_node_count:
            for x in range (new_node_count - curr_node_count):
                instance = create_ec2()
                created_instance_id = instance.id
                memcache_id = x + curr_node_count
                memcache_list[memcache_id] = instance
                
                cursor = cnx.cursor()
                query = ''' INSERT INTO memcachelist(MemcacheID, InstanceID, PublicIP)
                            VALUES(%s, %s, %s)'''
                cursor.execute(query, (memcache_id, created_instance_id, 'waiting'))
                cnx.commit()
            for x in range (new_node_count - curr_node_count):
                memcache_id = x + curr_node_count
                instance = memcache_list[memcache_id]
                instance.wait_until_running()
                instance.reload()
                created_instance_ip = instance.public_ip_address

                cursor = cnx.cursor()
                query = ''' UPDATE Memcachelist
                            SET PublicIP = %s
                            WHERE MemcacheID = %s'''
                cursor.execute(query, (created_instance_ip, memcache_id))
                cnx.commit()

            return "memcache pool size increment is successful!"

        elif new_node_count < curr_node_count:
            for x in range (curr_node_count - new_node_count):
                memcache_id = curr_node_count - 1 - x
                deleted_instance_id = memcache_list[memcache_id].id
                delete_ec2(deleted_instance_id)
                memcache_list.pop(memcache_id)

                cursor = cnx.cursor()
                query = ''' DELETE FROM Memcachelist
                            WHERE MemcacheID = %s'''
                cursor.execute(query, (memcache_id,))
                cnx.commit()
            return "memcache pool size decrement is successful!"
        else:
            return "memcache pool size did not change"


    else:
        return "Invalid! Please choose manual mode or auto mode"


@webapp_manager.route('/delete_all_data', methods=['POST'])
def delet_all_data():
    # delete all image paths in RDS
    cnx = get_db()
    cursor = cnx.cursor()
    query = ''' TRUNCATE imagelist '''
    cursor.execute(query)
    cnx.commit()
    # delet all images in S3
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(s3_bucket['name'])
    bucket.objects.all().delete()
    # clear contents in all memcache nodes
    # todo

    return '1'

@webapp_manager.route('/delete_memcache_nodes', methods=['POST'])
def delet_memcache_nodes():
    return '1'