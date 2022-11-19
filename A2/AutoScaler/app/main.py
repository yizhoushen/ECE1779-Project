from flask import render_template, url_for, request
from app import webapp_autoscaler
from flask import json
from flask import jsonify

from app.config import db_config
import mysql.connector
import boto3

import math
import time
from datetime import datetime, timedelta
import threading

# Autoscaler Status Variables
AUTO_SCALER_ENABLE = False
AUTO_SCALER_CHECK_SIGN_INTERVAL = 5
SECONDS_READING_2DB_INTERVAL = 15

max_miss_rate_threshold = 0.8
min_miss_rate_threshold = 0.2

expand_ratio = 2
shrink_ratio = 0.5

# come from cloudwatch
miss_rate = 0.5


# database prepare & connect
def connect_to_database():
    return mysql.connector.connect(user=db_config['user'],
                                   password=db_config['password'],
                                   host=db_config['host'],
                                   database=db_config['database'],
                                   auth_plugin='mysql_native_password')


def get_db():
    db = connect_to_database()
    return db


def get_instance_change(miss_rate):
    # delta_of_instance: positive = num to be added； negative = num to be reduced ; 0 means no change
    global max_miss_rate_threshold, min_miss_rate_threshold
    global expand_ratio, shrink_ratio

    # get most updated num_of_instances, old_num_of_instance
    cnx = get_db()
    cursor = cnx.cursor()
    sql_num_of_activate_instances = "SELECT COUNT(MemcacheID) FROM memcachelist"
    cursor.execute(sql_num_of_activate_instances)
    num_of_instances = cursor.fetchone()[0]
    print("num of instances: {}".format(num_of_instances))
    old_num_of_instances = num_of_instances
    print("old num of instances: {}".format(old_num_of_instances))

    # expand
    if miss_rate > max_miss_rate_threshold:
        # expand instances based on expand_ratio
        num_of_instances *= expand_ratio
        num_of_instances = math.ceil(num_of_instances)
        if num_of_instances > 8:
            num_of_instances = 8

    # shrink
    if miss_rate < min_miss_rate_threshold:
        # shrink instances based on shrink_ratio
        num_of_instances *= shrink_ratio
        num_of_instances = math.ceil(num_of_instances)
        if num_of_instances < 1:
            num_of_instances = 1

    delta_of_instances = int(num_of_instances - old_num_of_instances)
    return delta_of_instances


def operate_instances(delta_of_instances=0):
    # to be done
    if delta_of_instances > 0:
        # maybe one way: while until delta_of_instances == 0
        print("Need to expand " + str(delta_of_instances) + " new instances automatically!")
    elif delta_of_instances < 0:
        print("Need to shrink " + str(abs(delta_of_instances)) + "instances automatically!")
    else:
        print("Don't need to adjust instances!")


def autoscaler_mode_change():
    while True:
        if AUTO_SCALER_ENABLE:
            print("The auto scaler is running in auto model.")
            # step 1： get miss rate from CloudWatch API
            miss_rate = statistic_cloudwatch.avg_MissRate
            # step 2： adjust instances
            delta_of_instances = get_instance_change(miss_rate=miss_rate)
            operate_instances(delta_of_instances)
            time.sleep(AUTO_SCALER_CHECK_SIGN_INTERVAL)


class read_statistics_2CloudWatch():
    def __init__(self) -> None:
        # Statistical variables
        self.avg_MissRate = -1
        self.avg_HitRate = -1
        self.MetricName = ['single_ItemNum', 'single_currentMemCache', 'single_TotalRequestNum',
                           'single_GetPicRequestNum', 'single_miss_num', 'singe_hit_num']
        self.statistic = dict.fromkeys(self.MetricName, 0)
        self.cloudwatch_data = {}

    def read_statistics(self):
        while True:
            print("statistic report2: ", threading.current_thread().name)
            print("CurrentTime", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            cloudwatch = boto3.client('cloudwatch')

            
            cloudwatch_sum_miss_num = cloudwatch.get_metric_statistics(
                Namespace='statistical_variable_of_one_instance',
                MetricName='single_miss_num',
                Dimensions=[
                    {
                        'Name': 'instance-id',
                        'Value': 'string'
                    },
                ],
                StartTime=datetime.utcnow() - timedelta(seconds=1 * 5),
                EndTime=datetime.utcnow(),
                Period=5,
                Statistics=[
                    'Sum', 'SampleCount',
                ],
            
            )
            print(cloudwatch_sum_miss_num)
            
            cloudwatch_sum_GetPicRequestNum = cloudwatch.get_metric_statistics(
                Namespace='statistical_variable_of_one_instance',
                MetricName='single_GetPicRequestNum',
                Dimensions=[
                    {
                        'Name': 'instance-id',
                        'Value': 'string'
                    },
                ],
                StartTime=datetime.utcnow() - timedelta(seconds=1 * 5),
                EndTime=datetime.utcnow(),
                Period=5,
                Statistics=[
                    'Sum', 'SampleCount',
                ],
            
            )
            print(cloudwatch_sum_GetPicRequestNum)
            
            if len(cloudwatch_sum_miss_num['Datapoints']) == 0 or len(
                    cloudwatch_sum_GetPicRequestNum['Datapoints']) == 0:
                self.MissNum = -2
            else:
                self.MissNum = cloudwatch_sum_miss_num['Datapoints'][0]['Sum']
                self.GetPicRequestNum = cloudwatch_sum_GetPicRequestNum['Datapoints'][0]['Sum']
                if self.GetPicRequestNum == 0:
                    self.avg_MissRate = -1
                else:
                    self.avg_MissRate = self.MissNum / self.GetPicRequestNum
                print("average miss rate: " + str(self.avg_MissRate))
            print("Miss number: " + str(self.MissNum))

            time.sleep(SECONDS_READING_2DB_INTERVAL)

statistic_cloudwatch = read_statistics_2CloudWatch()
threading.Thread(target=statistic_cloudwatch.read_statistics, daemon=True).start()
threading.Thread(target=autoscaler_mode_change, daemon=True).start()


@webapp_autoscaler.route('/')
def main():
    global AUTO_SCALER_ENABLE
    get_curr_autoscaler_status()
    return "The auto scaler is running. " \
           " Auto mode: " + str(AUTO_SCALER_ENABLE)


# @webapp_autoscaler.route('/set_autoscaler_mode', methods=['POST'])
# # has been tested successfully at Nov. 11
# def set_autoscaler_mode():
#     new_autoscaler_mode = float(request.form.get('autoscaler_mode'))
#     if new_autoscaler_mode == 1.0:
#         AUTO_SCALER_ENABLE = True
#         # autoscaler_mode_change()
#         response = jsonify(success='True',
#                            message='Success! The mode of autoscaler is on.')
#     elif new_autoscaler_mode == 0.0:
#         AUTO_SCALER_ENABLE = False
#         # autoscaler_mode_change()
#         response = jsonify(success='True',
#                            message='Success! The mode of autoscaler is off.')
#     else:
#         response = jsonify(success='False',
#                            message='Failure! Illegal parameters, the mode of autoscaler unchanged.')
#     return response
#
#
# @webapp_autoscaler.route('/set_ratio', methods=['POST'])
# # has been tested successfully at Nov. 11
# def set_ratio():
#     ratio_type = request.form.get('ratio_type')
#     ratio_num = float(request.form.get('ratio_num'))
#
#     if ratio_type not in ["expand", "shrink"]:
#         response = jsonify(success='False',
#                            message='Failure! The ratio_type is illegal.')
#     elif ratio_type == "expand":
#         if ratio_num <= 1.0:
#             response = jsonify(success='False',
#                                message='Failure! The ratio_num is illegal.')
#         else:
#             expand_ratio = ratio_num
#             response = jsonify(success='True',
#                                message='Success! The expand_ratio has changed to ' + str(expand_ratio))
#     elif ratio_type == "shrink":
#         if ratio_num <= 0.0 or ratio_num >= 1.0:
#             response = jsonify(success='False',
#                                message='Failure! The ratio_num is illegal.')
#         else:
#             shrink_ratio = ratio_num
#             response = jsonify(success='True',
#                                message='Success! The shrink_ratio has changed to ' + str(shrink_ratio))
#     return response


@webapp_autoscaler.route('/set_autoscaler_to_automatic_mode', methods=['POST'])
# has been tested successfully at Nov. 12
def set_autoscaler_to_automatic_mode():
    global AUTO_SCALER_ENABLE
    global max_miss_rate_threshold, min_miss_rate_threshold
    global expand_ratio, shrink_ratio

    new_autoscaler_mode = float(request.form.get('autoscaler_mode'))
    new_max_miss_rate_threshold = float(request.form.get('max_missrate'))
    new_min_miss_rate_threshold = float(request.form.get('min_missrate'))
    new_expand_ratio = float(request.form.get('ratio_expand'))
    new_shrink_ratio = float(request.form.get('ratio_shrink'))

    if new_autoscaler_mode == 1:
        if 0 < new_max_miss_rate_threshold <= 1 and 0 <= new_min_miss_rate_threshold < 1 and new_min_miss_rate_threshold < new_max_miss_rate_threshold:
            if new_expand_ratio > 1 and 0 < new_shrink_ratio < 1:
                AUTO_SCALER_ENABLE = True
                max_miss_rate_threshold = new_max_miss_rate_threshold
                min_miss_rate_threshold = new_min_miss_rate_threshold
                expand_ratio = new_expand_ratio
                shrink_ratio = new_shrink_ratio

                response = jsonify(success='True',
                                   message='The parameters of autoscaler have changed success.')
                print(AUTO_SCALER_ENABLE)
                return response

    response = jsonify(success='False',
                       message='Invalid parameter.')
    print(AUTO_SCALER_ENABLE)
    return response


@webapp_autoscaler.route('/set_autoscaler_to_manual_mode', methods=['POST'])
# has been tested successfully at Nov. 12
def set_autoscaler_to_manual_mode():
    global AUTO_SCALER_ENABLE

    new_autoscaler_mode = float(request.form.get('autoscaler_mode'))
    if new_autoscaler_mode == 0:
        AUTO_SCALER_ENABLE = False
        response = jsonify(success='True',
                           message='The parameters of autoscaler have changed success.')
        print(AUTO_SCALER_ENABLE)
        return response

    print(AUTO_SCALER_ENABLE)
    response = jsonify(success='False',
                       message='Invalid parameter.')
    return response


@webapp_autoscaler.route('/get_curr_autoscaler_status', methods=['POST'])
# has been tested successfully at Nov. 11
def get_curr_autoscaler_status():
    curr_autoscaler_status = {'Auto Mode': AUTO_SCALER_ENABLE,
                              'Max Miss Rate Threshold': max_miss_rate_threshold,
                              'Min Miss Rate Threshold': min_miss_rate_threshold,
                              'Expand Ratio': expand_ratio,
                              'Shrink Ratio': shrink_ratio,
                              'Time': datetime.now().strftime("%y-%m-%d %H:%M:%S")
                              }
    response = jsonify(message=curr_autoscaler_status)
    return response


