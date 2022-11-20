# config of A2 RDS database
# this database instance enables public access for local connection testing, remember to replace with a new S3 database instance without public access
# db_config = {'user': 'admin',
#              'password': 'admin1234',
#              'host': 'database-new.c5xj5z6rnfm8.us-east-1.rds.amazonaws.com',
#              'database': 'ece1779project'}

# config of local database
db_config = {'user': 'dbadmin',
             'password': 'admin1234',
             'host': '127.0.0.1',
             'database': 'ece1779project'}

# config of aws ec2 database
# db_config = {'user': 'root',
#              'password': 'ece1779pass',
#              'host': '127.0.0.1',
#              'database': 'ece1779project'}

# Better to use local credentials under ~/.aws rather than explicit access keys
# aws_access = {'aws_access_key_id': '<do not upload access key to github, change to your own>',
#               'aws_secret_access_key': '<do not upload access key to github, change to your own>'}

# todo
# need ami_id and subnet_id for ec2
ami_id = 'ami-09047bd5954627aa9'
subnet_id = '<Subnet ID>'

s3_bucket = {'name': 'bucket-ece1779-project-new'}