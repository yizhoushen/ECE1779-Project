# config of A2 RDS database
# this database instance enables public access for local connection testing, remember to replace with a new S3 database instance without public access
db_config = {'user': 'admin',
             'password': 'admin1234',
             'host': 'database-test.c5xj5z6rnfm8.us-east-1.rds.amazonaws.com',
             'database': 'ece1779project'}

# config of local database
# db_config = {'user': 'dbadmin',
#              'password': 'admin1234',
#              'host': '127.0.0.1',
#              'database': 'ece1779project'}

# config of aws ec2 database
# db_config = {'user': 'root',
#              'password': 'ece1779pass',
#              'host': '127.0.0.1',
#              'database': 'ece1779project'}

# todo
# need ami_id and subnet_id for ec2
ami_id = 'ami-07bf503260d4ce676'
subnet_id = '<Subnet ID>'

s3_bucket = {'name': 'bucket-ece1779-project-new'}

aws_access_key = "AKIAYCMAR64CBTBYTIQC"
aws_secret_key = "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"