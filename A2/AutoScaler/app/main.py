from flask import render_template, url_for, request
from app import webapp_autoscaler
from flask import json
from flask import jsonify
import math
import mysql.connector

AUTO_SCALER_ENABLE = True

MAX_MISS_RATE_THRESHOLD = 0
MIN_MISS_RATE_THRESHOLD = 0

expand_ratio = 2
shrink_ratio = 0.5

MAX_NUM_OF_INSTANCES = 8
MIN_NUM_OF_INSTANCES = 1

# come from cloudwatch
miss_rate = 0

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
    delta_of_instances = 0

    # get most updated num_of_instances, old_num_of_instance
    cnx = get_db()
    cursor = cnx.cursor()
    sql_num_of_activate_instances = "SELECT COUNT(*) FROM memcachelist WHERE activeStatus = TRUE"
    cursor.execute(sql_num_of_activate_instances)
    num_of_instances = cursor.fetchone()[0]
    old_num_of_instances = cursor.fetchone()[0]

    # expand
    if miss_rate > MAX_MISS_RATE_THRESHOLD:
        # expand instances based on expand_ratio
        num_of_instances *= expand_ratio
        num_of_instances = math.ceil(num_of_instances)
        if num_of_instances > MAX_NUM_OF_INSTANCES:
            num_of_instances = MAX_NUM_OF_INSTANCES

    # shrink
    if miss_rate < MIN_MISS_RATE_THRESHOLD:
        # shrink instances based on shrink_ratio
        num_of_instances *= shrink_ratio
        num_of_instances = math.ceil(num_of_instances)
        if num_of_instances < MIN_NUM_OF_INSTANCES:
            num_of_instances = MIN_NUM_OF_INSTANCES

    delta_of_instance = int(num_of_instances - old_num_of_instances)
    return delta_of_instances


def operate_instances(delta_of_instances = 0):
    if delta_of_instances > 0:
        print("Need to expand " + str(delta_of_instances) + " new instances automatically!")
    elif delta_of_instances < 0:
        print("Need to shrink " + str(abs(delta_of_instances)) + "instances automatically!")
    else:
        print("Don't need to adjust instances!")

def autoscaler_mode_change():
    # 不能用while，占用线程
    while(AUTO_SCALER_ENABLE):
        # listen miss rate
        delta_of_instances = get_instance_change(miss_rate)
        operate_instances(delta_of_instances)
    # check AUTO_SCALER_ENABLE变化

@webapp_autoscaler.route('/')
def main():
    # 默认autoscaler启动，AUTO_SCALER_ENABLE为True
    # 1.等待来自前端的信号
    #     1.1 若传来手动信号，则启动autoscaler功能函数
    #     1.2 若传来自动信号，则停止autoscaler功能函数 / 启动 非autoscaler功能

    # if (new_message != AUTO_SCALER_ENABLE):
    #
    #
    # return render_template("main.html")


@webapp_memcache.route('/set_autoscaler_mode', methods=['POST'])
def set_autoscaler_mode():
    new_autoscaler_mode = request.form.get('autoscaler_mode')
    if new_autoscaler_mode == 1:
        AUTO_SCALER_ENABLE = True
        autoscaler_mode_change()
        response = jsonify(success='True',
                           message='Success! The mode of autoscaler is on.')
    elif new_autoscaler_mode == 0:
        AUTO_SCALER_ENABLE = False
        autoscaler_mode_change()
        response = jsonify(success='True',
                           message='Success! The mode of autoscaler is off.')
    else:
        response = jsonify(success='False',
                           message='Failure! Illegal parameters, the mode of autoscaler unchanged.')
    return response

@webapp_memcache.route('/set_ratio', methods=['POST'])
def set_ratio():
    ratio_type = request.form.get('ratio_type')
    ratio_num = request.form.get('ratio_num')
    # 潜在问题：ratio_num是string or float

    if ratio_type not in ["expand", "shrink"]:
        response = jsonify(success='False',
                           message='Failure! The ratio_type is illegal.')
    elif ratio_type == "expand":
        if ratio_num <= 1:
            response = jsonify(success='False',
                               message='Failure! The ratio_num is illegal.')
        else:
            expand_ratio = ratio_num
            response = jsonify(success='True',
                               message='Success! The expand_ratio has changed to ' + str(expand_ratio))
    elif ratio_type == "shrink":
        if ratio_num <= 0 or ratio_num >= 1:
            response = jsonify(success='False',
                               message='Failure! The ratio_num is illegal.')
        else:
            shrink_ratio = ratio_num
            response = jsonify(success='True',
                               message='Success! The shrink_ratio has changed to ' + str(shrink_ratio))



        AUTO_SCALER_ENABLE = True
        autoscaler_mode_change()
        response = jsonify(success='True',
                           message='Success! The mode of autoscaler is on.')
    elif new_autoscaler_mode == 0:
        AUTO_SCALER_ENABLE = False
        autoscaler_mode_change()
        response = jsonify(success='True',
                           message='Success! The mode of autoscaler is off.')
    else:
        response = jsonify(success='False',
                           message='Failure! Illegal parameters, the mode of autoscaler unchanged.')
    return response

@webapp_memcache.route('/get_curr_autoscaler_mode', methods=['POST'])
def get_curr_autoscaler_mode():
    if AUTO_SCALER_ENABLE:
        response = jsonify(success='True',
                           message='The mode of autoscaler is on.')
    else:
        response = jsonify(success='True',
                           message='The mode of autoscaler is off.')
    return response

# 获取当前状态函数
