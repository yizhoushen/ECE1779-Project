from flask import render_template, url_for, request
from app import webapp_autoscaler
from flask import json
from flask import jsonify
import math

AUTO_SCALER_ENABLE = False

MAX_MISS_RATE_THRESHOLD = 0
MIN_MISS_RATE_THRESHOLD = 0

expand_ratio = 2
shrink_ratio = 0.5

MAX_NUM_OF_INSTANCES = 8
MIN_NUM_OF_INSTANCES = 1

# come from cloudwatch
miss_rate = 0


def get_instance_change(miss_rate):
    # delta_of_instance: positive = num to be added； negative = num to be reduced ; 0 means no change
    delta_of_instance = 0

    # get most updated num_of_instance, old_num_of_instance
    # can only come from db
    num_of_instance = 0
    old_num_of_instance = 0

    # expand
    if miss_rate > MAX_MISS_RATE_THRESHOLD:
        # expand instances based on expand_ratio
        num_of_instance *= expand_ratio
        num_of_instance = math.ceil(num_of_instance)
        if num_of_instance > MAX_NUM_OF_INSTANCES:
            num_of_instance = MAX_NUM_OF_INSTANCES

    # shrink
    if miss_rate < MIN_MISS_RATE_THRESHOLD:
        # shrink instances based on shrink_ratio
        num_of_instance *= shrink_ratio
        num_of_instance = math.ceil(num_of_instance)
        if num_of_instance < MIN_NUM_OF_INSTANCES:
            num_of_instance = MIN_NUM_OF_INSTANCES

    delta_of_instance = int(num_of_instance - old_num_of_instance)
    return delta_of_instance


def operate_instances(delta_of_instance = 0):
    if delta_of_instance > 0:
        print("Need to add " + str(delta_of_instance) + " new instances automatically!")
    elif delta_of_instance < 0:
        print("Need to shrink " + str(abs(delta_of_instance)) + "instances automatically!")
    else:
        print("Don't need to adjust instances!")

def auto_bu_qidong():
    # 等待信号变更为auto模式，重置标志位，启动

def get_autoscaler_status():
    return AUTO_SCALER_ENABLE

@webapp_autoscaler.route('/')
def main():
    # 默认autoscaler启动，AUTO_SCALER_ENABLE为True
    # 1.等待来自前端的信号
    #     1.1 若传来手动信号，则启动autoscaler功能函数
    #     1.2 若传来自动信号，则停止autoscaler功能函数 / 启动 非autoscaler功能

    if (new_message != AUTO_SCALER_ENABLE):


    return render_template("main.html")


