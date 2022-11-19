import threading

from flask import render_template, url_for, request, g
from app import webapp_manager
from flask import json
from flask import jsonify
import requests
import mysql.connector
from app.config import db_config, ami_id, subnet_id, s3_bucket
from datetime import datetime, timedelta, timezone
import jyserver.Flask as jsf
import boto3
import time
import pytz

SECONDS_READING_2DB_INTERVAL = 60


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
aggregated_statistics = []
tzutc_Toronto = timezone(timedelta(hours=-5))
new_node_count = 0
memcache_id_list = {}
memcache_ip_list = {}
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
    ec2.terminate_instances(InstanceIds=[instance_id])


# Create/terminate or Start/Stop the instance?
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


class read_statistics_2CloudWatch():
    def __init__(self) -> None:
        # Statistical variables
        self.avg_MissRate = -1
        self.avg_HitRate = -1
        self.MetricName = ['single_ItemNum', 'single_currentMemCache', 'single_TotalRequestNum',
                           'single_GetPicRequestNum', 'single_miss_num', 'singe_hit_num']
        self.cloudwatch_data = aggregated_statistics

    def read_statistics(self):
        while True:
            print("statistic report2: ", threading.current_thread().name)
            print("CurrentTime", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            data_each_time = {}
            statistic = dict.fromkeys(self.MetricName, 0)
            cloudwatch = boto3.client('cloudwatch')
            for metric in self.MetricName:
                cloudwatch_response = cloudwatch.get_metric_statistics(
                    Namespace='statistical_variable_of_one_instance',
                    MetricName=metric,
                    Dimensions=[
                        {
                            'Name': 'instance-id',
                            'Value': 'string'
                        },
                    ],
                    StartTime=datetime.utcnow() - timedelta(seconds=1 * 60),
                    EndTime=datetime.utcnow(),
                    Period=60,
                    Statistics=[
                        'Sum',
                    ],
                )
                if len(cloudwatch_response['Datapoints']) != 0:
                    statistic[metric] = cloudwatch_response['Datapoints'][0]['Sum']
                else:
                    statistic[metric] = None

            if statistic['single_GetPicRequestNum'] is None:
                print("No DATA so far!!!!")
            else:
                if statistic['single_GetPicRequestNum'] != 0:
                    self.avg_MissRate = round(statistic['single_miss_num'] / statistic['single_GetPicRequestNum'], 3)
                    self.avg_HitRate = round(statistic['singe_hit_num'] / statistic['single_GetPicRequestNum'], 3)
            statistic["avg_MissRate"] = self.avg_MissRate
            statistic["avg_HitRate"] = self.avg_HitRate

            if len(cloudwatch_response['Datapoints']) != 0:
                time_each_data = cloudwatch_response['Datapoints'][0]['Timestamp'].astimezone(tzutc_Toronto)
            else:
                time_each_data = "Null"
            data_each_time["time"] = time_each_data
            data_each_time["statistic"] = statistic
            self.cloudwatch_data.append(data_each_time)
            print(data_each_time)
            # cloudwatch_sum_miss_num = cloudwatch.get_metric_statistics(
            #     Namespace='statistical_variable_of_one_instance',
            #     MetricName='single_miss_num',
            #     Dimensions=[
            #         {
            #             'Name': 'instance-id',
            #             'Value': 'string'
            #         },
            #     ],
            #     StartTime=datetime.utcnow() - timedelta(seconds=1 * 60),
            #     EndTime=datetime.utcnow(),
            #     Period=60,
            #     Statistics=[
            #         'Sum',
            #     ],
            #
            # )
            # print(cloudwatch_sum_miss_num)
            #
            # cloudwatch_sum_GetPicRequestNum = cloudwatch.get_metric_statistics(
            #     Namespace='statistical_variable_of_one_instance',
            #     MetricName='single_GetPicRequestNum',
            #     Dimensions=[
            #         {
            #             'Name': 'instance-id',
            #             'Value': 'string'
            #         },
            #     ],
            #     StartTime=datetime.utcnow() - timedelta(seconds=1 * 60),
            #     EndTime=datetime.utcnow(),
            #     Period=60,
            #     Statistics=[
            #         'Sum',
            #     ],
            #
            # )
            # print(cloudwatch_sum_GetPicRequestNum)
            #
            # if len(cloudwatch_sum_miss_num['Datapoints']) == 0 or len(
            #         cloudwatch_sum_GetPicRequestNum['Datapoints']) == 0:
            #     self.MissNum = -2
            # else:
            #     self.MissNum = cloudwatch_sum_miss_num['Datapoints'][0]['Sum']
            #     self.GetPicRequestNum = cloudwatch_sum_GetPicRequestNum['Datapoints'][0]['Sum']
            #     if self.GetPicRequestNum == 0:
            #         self.avg_MissRate = -1
            #     else:
            #         self.avg_MissRate = self.MissNum / self.GetPicRequestNum
            #     print("average miss rate: " + str(self.avg_MissRate))
            # print("Miss number: " + str(self.MissNum))

            time.sleep(SECONDS_READING_2DB_INTERVAL)


statistic_cloudwatch = read_statistics_2CloudWatch()
threading.Thread(target=statistic_cloudwatch.read_statistics, daemon=True).start()


@webapp_manager.route('/statistics', methods=['GET'])
def statistics():
    cnx = get_db()
    cursor = cnx.cursor()
    query = '''SELECT COUNT(*) FROM memcachelist '''
    cursor.execute(query)
    node_num = cursor.fetchone()[0]
    start_time = (datetime.utcnow() - timedelta(minutes=30)).replace(tzinfo=pytz.UTC).astimezone(tzutc_Toronto)
    return render_template("statistics.html", title="Memory Cache Statistics", aggregated_statistics=aggregated_statistics, node_num=node_num, start_time=start_time)


@webapp_manager.route('/config_form', methods=['GET'])
def config_form():
    cnx = get_db()
    cursor = cnx.cursor()
    query = ''' SELECT MemcacheID, PublicIP FROM memcachelist '''
    cursor.execute(query)
    for row in cursor:
        memcache_id = row[0]
        instance_ip = row[1]
        memcache_ip_list[memcache_id] = instance_ip
    print("memcache_ip_list: {}".format(memcache_ip_list))
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

        for memcache_id in memcache_ip_list:
            response = requests.post("http://{}:5001/refreshConfiguration".format(memcache_ip_list[memcache_id]),
                                     timeout=5)
            res_json = response.json()
            if res_json['success'] == 'True':
                pass
            elif res_json['success'] == 'False':
                return "Cache configuration from ip {} failed!".format(memcache_ip_list[memcache_id])
            else:
                return "Failed to get repsonse from {} memcache/refreshConfiguration".format(
                    memcache_ip_list[memcache_id])
        return render_template("execute_result.html", title="Cache configuration is successful!")

    elif 'cache_clear' in request.form and 'cache_configure' not in request.form:
        for memcache_id in memcache_ip_list:
            response = requests.post("http://{}:5001/clear".format(memcache_ip_list[memcache_id]), timeout=5)
            res_json = response.json()
            if res_json['success'] == 'True':
                pass
            elif res_json['success'] == 'False':
                return "Cache clear from ip {} failed!".format(memcache_ip_list[memcache_id])
            else:
                return "Failed to get repsonse from {} memcache/clear".format(memcache_ip_list[memcache_id])
        return render_template("execute_result.html", title="Cache clear is successful!")

    else:
        return "Invalid! Please choose cache configure or cache clear"


@webapp_manager.route('/resize_form', methods=['GET'])
def resize_form():
    # curr_node_count = get_memcache_count()
    cnx = get_db()
    cursor = cnx.cursor()
    query_get_memcache_count = '''SELECT COUNT(MemcacheID) FROM memcachelist'''
    cursor.execute(query_get_memcache_count)
    row = cursor.fetchone()
    global curr_node_count
    curr_node_count = row[0]

    query = "SELECT MemcacheID, InstanceID FROM memcachelist"
    cursor.execute(query)
    for row in cursor:
        memcache_id = row[0]
        instance_id = row[1]
        memcache_id_list[memcache_id] = instance_id

    return App.render(
        render_template("resize_form.html", title="Change Memory Cache Resize Mode", curr_node_count=curr_node_count,
                        new_node_count=new_node_count))


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

        max_missrate = float(request.form.get('max_missrate'))
        min_missrate = float(request.form.get('min_missrate'))
        ratio_expand = float(request.form.get('ratio_expand'))
        ratio_shrink = float(request.form.get('ratio_shrink'))

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
            memcache_instance_list = {}
            for x in range(new_node_count - curr_node_count):
                instance = create_ec2()
                created_instance_id = instance.id
                memcache_id = x + curr_node_count
                memcache_instance_list[memcache_id] = instance

                cursor = cnx.cursor()
                query = ''' INSERT INTO memcachelist(MemcacheID, InstanceID, PublicIP)
                            VALUES(%s, %s, %s)'''
                cursor.execute(query, (memcache_id, created_instance_id, 'waiting'))
                cnx.commit()
            for x in range(new_node_count - curr_node_count):
                memcache_id = x + curr_node_count
                instance = memcache_instance_list[memcache_id]
                instance.wait_until_running()
                instance.reload()
                created_instance_ip = instance.public_ip_address

                cursor = cnx.cursor()
                query = ''' UPDATE memcachelist
                            SET PublicIP = %s
                            WHERE MemcacheID = %s'''
                cursor.execute(query, (created_instance_ip, memcache_id))
                cnx.commit()

            # check if the initialization has finished
            response = None
            last_instance_id = new_node_count - 1
            last_ip = memcache_instance_list[last_instance_id].public_ip_address
            print("last ip is: {}".format(last_ip))
            while response == None:
                try:
                    response = requests.post("http://{}:5001/refreshConfiguration".format(last_ip), timeout=5)
                except:
                    pass

            response = requests.post("http://127.0.0.1:5000/redistribute")
            res_json = response.json()
            if res_json['success'] == 'True':
                return "memcache pool size increment is successful!"
            else:
                return "memcache redistribution failed"
            # return "memcache pool size increment is successful!"

        elif new_node_count < curr_node_count:
            for x in range(curr_node_count - new_node_count):
                memcache_id = curr_node_count - 1 - x
                deleted_instance_id = memcache_id_list[memcache_id]
                delete_ec2(deleted_instance_id)
                memcache_id_list.pop(memcache_id)

                cursor = cnx.cursor()
                query = ''' DELETE FROM memcachelist
                            WHERE MemcacheID = %s'''
                cursor.execute(query, (memcache_id,))
                cnx.commit()
            response = requests.post("http://127.0.0.1:5000/redistribute")
            res_json = response.json()
            if res_json['success'] == 'True':
                return "memcache pool size increment is successful!"
            else:
                return "memcache redistribution failed"
            # return "memcache pool size decrement is successful!"

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
    query = ''' SELECT PublicIP FROM memcachelist '''
    cursor.execute(query)
    for row in cursor:
        curr_ip = row[0]
        response = requests.post("http://{}:5001/clear".format(curr_ip), timeout=5)
        res_json = response.json()
        if res_json['success'] == 'True':
            pass
        elif res_json['success'] == 'False':
            return "Cache clear from ip {} failed!".format(curr_ip)
        else:
            return "Failed to get repsonse from {} memcache/clear".format(curr_ip)

    return 'success'


@webapp_manager.route('/delete_memcache_nodes', methods=['POST'])
def delet_memcache_nodes():
    return '1'
