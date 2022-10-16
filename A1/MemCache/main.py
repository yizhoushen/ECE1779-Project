from collections import OrderedDict
from sys import getsizeof
import random
from datetime import datetime

# for database
import mysql.connector
from config import db_config

# flask
from MemCache import webapp_memcache

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

# @webapp.teardown_appcontext
# def teardown_db(exception):
#     db = getattr(g, '_database', None)
#     if db is not None:
#         db.close()


# MemCache class starts here
class PicMemCache(object):

    def __init__(self, memCacheCapacity=None) -> None:

        # 从db读取memCacheCapacity，但此处没有对数据合法性进行验证
        cnx = get_db()
        cursor = cnx.cursor()
        query = "SELECT Capacity FROM configuration WHERE id = 1"
        cursor.execute(query)
        # self.memCacheCapacity = memCacheCapacity
        self.memCacheCapacity = cursor.fetchone()[0]

        # 统计变量
        self.drop_approach = 1
        self.currentMemCache = 0
        self.ItemNum = 0
        self.TotalRequestNum = 0
        self.MissNum = 0
        self.HitNum = 0
        self.GetPicRequestNum = 0

        self.MC = OrderedDict()
        print("memCacheCapacity", self.memCacheCapacity)

    def drop_specific_pic(self, keyID):
        # invalidateKey(key) to drop a specific key.
        self.currentMemCache -= getsizeof(self.MC[keyID])
        self.MC.pop(keyID)
        self.ItemNum -= 1
        # 返回成功与否

    def drop_pic(self, approach=1):
        # Random Replacement
        if approach == 0:
            print("Random Replacement")
            rKey = random.choice(list(self.MC.keys()))
            print('dropped key:{}'.format(rKey))
            self.drop_specific_pic(rKey)

        # Least Recently Use (LRU)
        elif approach == 1:
            print("LRU")
            self.drop_specific_pic(next(iter(self.MC)))


    def put_pic(self, keyID, picString):
        # 具体的写入过程，不可直接调用
        if self.memCacheCapacity < getsizeof(picString):
            print("memCache容量过小，甚至小于本张图片大小，请增大memCache，本次缓存失败")
        elif self.currentMemCache + getsizeof(picString) <= self.memCacheCapacity:
            # 加入新图片后，没有超过MemCache总容量
            # print('没超！')
            self.MC[keyID] = picString
            self.currentMemCache += getsizeof(picString)
            self.ItemNum += 1
        else:
            # 加入新图片后，超过了MemCache总容量。我们需要丢掉图片，存入新图片
            # print('超了')

            cnx = get_db()
            cursor = cnx.cursor()
            query = "SELECT ReplacePolicy FROM configuration WHERE id = 1"
            cursor.execute(query)
            self.drop_approach = cursor.fetchone()[0]
            print("drop_approach: ", self.drop_approach)

            while self.currentMemCache + getsizeof(picString) > self.memCacheCapacity:
                self.drop_pic(self.drop_approach)
            self.MC[keyID] = picString
            self.currentMemCache += getsizeof(picString)
            self.ItemNum += 1
            print('Memcache set key {}'.format(keyID))

    def get_pic(self, keyID):
        # 当用户看图时，调用此函数
        # 唯一写入memCache的情况

        self.GetPicRequestNum += 1

        if self.MC[keyID] != -1:
            # 调用的图片就在MemCache
            self.MC.move_to_end(key=keyID, last=True)
            # 需要：将图片发送到前端
            return self.MC[keyID]
            self.HitNum += 1
        else:
            # 调用的图片不在MemCache
            self.MissNum += 1
            print("MemCache无此图片")
            # 从前端接收图片string，然后存入memCache
            # self.put_pic(keyID, picStrin) —— 这里picStrin参数怎么处理？


    def clear_memcache(self):
        self.MC.clear()
        # if self.MC == None: 这里需要判断空嘛
        self.currentMemCache = 0
        self.ItemNum = 0
        # 统计数据是否删除


    def refreshConfiguration(self):
        # 能否在一个函数内，得到调用2次数据库
        cnx = get_db()
        cursor = cnx.cursor()
        query = "SELECT Capacity FROM configuration WHERE id = 1"
        cursor.execute(query)
        newMemCacheCapacity = cursor.fetchone()[0]

        if newMemCacheCapacity < 0:
            # 最好在前端验证，不能在数据库中存非正常值
            print("MemCacheCapacity应该大于等于0，本次更改失败")
        else:
            cnx = get_db()
            cursor = cnx.cursor()
            query = "SELECT ReplacePolicy FROM configuration WHERE id = 1"
            cursor.execute(query)
            self.drop_approach = cursor.fetchone()[0]
            print("drop_approach: ", self.drop_approach)

            while newMemCacheCapacity < self.currentMemCache:
                self.drop_pic(self.drop_approach)
            self.memCacheCapacity = newMemCacheCapacity


    def Front_end_upload(self, keyID):
        # 用于前端上传时，若MemCache内有同KeyID图片，则drop。没有则无操作
        if self.MC[keyID] != -1:
            self.drop_specific_pic(keyID)


    def get_info(self):
        # for test
        print("currentMem: ",self.currentMemCache)
        # print("memCacheCapacity: ", self.memCacheCapacity)
        # print(self.MC)


    def write_statistics_2db(self):
        # 在每个函数后面写这个，还是在route写
        cnx = get_db()
        cursor = cnx.cursor()
        query = ''' INSERT INTO statistics (Time, ItemNum, CurrentMemCache, TotalRequestNum, GetPicRequestNum, MissRate, HitRate)
                    VALUES ( Time = %s, 
                             ItemNum = %s, 
                             CurrentMemCache = %s, 
                             TotalRequestNum = %s, 
                             GetPicRequestNum = %s, 
                             MissRate = %s, 
                             HitRate = %s)
                '''

        cursor.execute(query, (datetime.now(),
                               self.ItemNum,
                               self.currentMemCache,
                               self.TotalRequestNum,
                               self.GetPicRequestNum,
                               self.MissNum / self.GetPicRequestNum,
                               self.HitNum / self.GetPicRequestNum))
        cnx.commit()


# following for test
memory1 = PicMemCache()
for i in range(60):
    memory1.put_pic(i,"picture1")
    memory1.get_info()
# memory1.drop_pic(DROP_APPROACH)
# memory1.clear_memcache() # 测试正常
# memory1.Front_end_upload(4)  # 测试正常
# memory1.refreshConfiguration(0)  # 测试正常
# print(memory1.get_pic(8))
# memory1.drop_specific_pic(4)
memory1.get_info()




@webapp_memcache.route('/PUT',methods=['GET'])
def PUT(key, value):
    # Fig 1.(5) PUT
    memory1.put_pic(keyID=key, picString=value)
    # Fig 1.(6) OK

@webapp_memcache.route('/GET', methods=['GET'])
def GET(key):
    # Fig 1.(1) GET
    memory1.get_pic(keyID = key)
    # Fig 1.(2) MISS


@webapp_memcache.route('/CLEAR', methods=['GET'])
def CLEAR():
    memory1.clear_memcache()


@webapp_memcache.route('/invalidateKey', methods=['GET'])
def invalidateKey(key):
    # Fig 2.(2) invalidateKey
    memory1.drop_specific_pic(keyID=key)
    # Fig 2.(3) OK


@webapp_memcache.route('/refreshConfiguration', methods=['GET'])
def refreshConfiguration():
    memory1.refreshConfiguration()

@webapp_memcache.route('/UPLOAD', methods=['GET'])
def Front_end_upload(key):
    memory1.Front_end_upload(keyID=key)
