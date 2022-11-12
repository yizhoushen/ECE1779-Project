# config of A2 RDS database
# this database instance enables public access for local connection testing, remember to replace with a new S3 database instance without public access
db_config = {'user': 'admin',
             'password': 'admin1234',
             'host': 'database-new.c5xj5z6rnfm8.us-east-1.rds.amazonaws.com',
             'database': 'ece1779project'}

aws_access = {'aws_access_key_id': '<do not upload access key to github, change to your own>',
              'aws_secret_access_key': '<do not upload access key to github, change to your own>'}

s3_bucket = {'name': 'bucket-ece1779-project-new'}