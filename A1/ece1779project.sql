
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
100,
0
);

create table statistics
(
id int NOT NULL,
Time datetime NOT NULL,
ItemNum int NOT NULL,
CurrentMemCache int NOT NULL,
TotalRequestNum int NOT NULL,
GetPicRequestNum int NOT NULL,
MissRate decimal(4,3),
HitRate decimal(4,3),
PRIMARY KEY(id)
);

INSERT INTO statistics
VALUES(
1,
'2022-01-01 00:00:00',
5,
500,
10,
4,
0.650,
0.350
);

-- select * from imagelist;
-- select * from configuration;
-- select * from statistics;

-- DELETE FROM imagelist WHERE ImageID = 'ds1';


