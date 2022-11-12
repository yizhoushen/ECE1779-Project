create database ece1779project;
use ece1779project;

show tables;

-- drop table imagelist;
-- drop table configuration;
-- drop table statistics;

create table imagelist
(
ImageID varchar(20) NOT NULL,
ImagePath text NOT NULL,
PRIMARY KEY(ImageID)
);

create table configuration
(
id int NOT NULL,
Capacity int NOT NULL,
ReplacePolicy int NOT NULL,
PRIMARY KEY(id)
);

INSERT INTO configuration
VALUES(
1,
1000000,
0
);

create table statistics
(
    id               int auto_increment
        primary key,
    ItemNum          int           not null,
    CurrentMemCache  int           not null,
    TotalRequestNum  int           not null,
    MissRate         decimal(4, 3) not null,
    HitRate          decimal(4, 3) not null,
    GetPicRequestNum int           not null,
    CurrTime         datetime      null
);

create table memcachelist
(
memcacheID int NOT NULL,
activeStatus boolean NOT NULL,
PRIMARY KEY(memcacheID)
);

INSERT INTO memcachelist VALUES(5001, false);
INSERT INTO memcachelist VALUES(5004, false);
INSERT INTO memcachelist VALUES(5005, false);
INSERT INTO memcachelist VALUES(5006, false);
INSERT INTO memcachelist VALUES(5007, false);
INSERT INTO memcachelist VALUES(5008, false);
INSERT INTO memcachelist VALUES(5009, false);
INSERT INTO memcachelist VALUES(5010, false);

-- INSERT INTO statistics
-- VALUES(
-- 1,
-- '2022-01-01 00:00:00',
-- 5,
-- 500,
-- 10,
-- 4,
-- 0.650,
-- 0.350
-- );

-- select * from imagelist;
-- select * from configuration;
-- select * from statistics;
-- select * from memcachelist;

-- DELETE FROM imagelist WHERE ImageID = 'ds1';

-- update memcachelist set activeStatus=true where memcacheID=5001;
-- update memcachelist set activeStatus=true where memcacheID=5004;
-- update memcachelist set activeStatus=true where memcacheID=5005;

