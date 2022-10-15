from collections import OrderedDict
from sys import getsizeof
import random
import mysql.connector

DROP_APPROACH = 1

# database prepare
# def connect_to_database():
#     return mysql.connector.connect(user=db_config['user'],
#                                    password=db_config['password'],
#                                    host=db_config['host'],
#                                    database=db_config['database'])
#
# def get_db():
#     db = getattr(g, '_database', None)
#     if db is None:
#         db = g._database = connect_to_database()
#     return db
#
# @webapp.teardown_appcontext
# def teardown_db(exception):
#     db = getattr(g, '_database', None)
#     if db is not None:
#         db.close()


# MemCache class starts here
class PicMemCache(object):

    def __init__(self, memCacheCapacity) -> None:
        # 用户设定的MemCache大小，需从数据库读取
        self.memCacheCapacity = memCacheCapacity
        # 当前MemCache容量 = 占用情况
        self.currentMemCache = 0
        self.MC = OrderedDict()

    def drop_specific_pic(self, keyID):
        # invalidateKey(key) to drop a specific key.
        self.currentMemCache -= getsizeof(self.MC[keyID])
        self.MC.pop(keyID)
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
            # print('没超！')
        # 加入新图片后，没有超过MemCache总容量
            self.MC[keyID] = picString
            self.currentMemCache += getsizeof(picString)
        else:
            # print('超了')

        # 加入新图片后，超过了MemCache总容量，需要丢掉图片，存入新图片
            while self.currentMemCache + getsizeof(picString) > self.memCacheCapacity:
                self.drop_pic(DROP_APPROACH)
            self.MC[keyID] = picString
            self.currentMemCache += getsizeof(picString)
            print('Memcache set key {}'.format(keyID))

    def get_pic(self, keyID):
        # 当用户看图时，调用此函数
        # 仅有此处才可能写入memCache
        if self.MC[keyID] != -1:
            # 调用的图片就在MemCache
            self.MC.move_to_end(key=keyID, last=True)
            # 需要：将图片发送到前端
            return self.MC[keyID]
        else:
            # 调用的图片不在MemCache
            print("MemCache无此图片")
            # 从前端接收图片string，然后存入memCache
            # self.put_pic(keyID, picStrin) —— 这里picStrin参数怎么处理？


    def clear_memcache(self):
        self.MC.clear()
        # if self.MC == None: 这里需要判断空嘛
        self.currentMemCache = 0

    def refreshConfiguration(self, newMemCacheCapacity):
        if newMemCacheCapacity < 0:
            # 最好在前端验证，不能在数据库中存非正常值
            print("MemCacheCapacity应该大于等于0，本次更改失败")
        else:
            while newMemCacheCapacity < self.currentMemCache:
                self.drop_pic(DROP_APPROACH)
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


    def write2db(self):
        cnx = get_db()
        cursor = cnx.cursor()

        query = ''' SELECT ImagePath FROM imagelist
                        WHERE ImageID = %s'''

        cursor.execute(query, (image_key,))
        row = cursor.fetchone()



# following for test
memory1 = PicMemCache(2000)
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

