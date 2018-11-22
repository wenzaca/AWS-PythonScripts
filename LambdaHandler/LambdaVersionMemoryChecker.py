from __future__ import absolute_import, print_function, unicode_literals
import logging
import datetime;
import boto3

# Initialize logger and set log level
logger = logging.getLogger()
logger.setLevel(logging.ERROR)

# Initialize Lambda and CloudWatch client for the specific region
def initialize_services(region):
    session = boto3.Session(region_name=region)
    return [session.client('lambda'), session.client('cloudwatch')]

# Read all the verions from the Functions in that region
# versions = versions_all[1:-5]
# This would change list from:
# ["Latest", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
# To:
# [1, 2, 3, 4, 5, 6, 7, 8]
def read_versions_from_funtion(function, event, client_lambda, region):
    memory_free = 0
    versions_all = client_lambda.list_versions_by_function(FunctionName=function['FunctionArn'])['Versions']
    versions = versions_all[1:-int(event.get('num_versions', 1))]

    if not len(versions): logger.info('{}: No versions older than the specified value for FunctionName={}'.format(region, function['FunctionArn']))
    for version in versions:
        if version['Version'] != function['Version']:
            arn = version['FunctionArn']
            logger.info('{}: FunctionName={}'.format(arn))
            logger.info('{}: Memory size of this version: {} MB\n'.format(region, version['MemorySize']))

            if not event.get('read_only', True): memory_free += remove_version(version, client_lambda, region)
        else:
            logger.info("{}: Ignoring Latest version for function: {}".format(region, function['Version']))
    return memory_free


# Create CloudWatch Metric for Code Storage usage
def put_metrics_cloudwatch(client_cloudwatch, in_use_memory):
    client_cloudwatch.put_metric_data(
        Namespace='AWS/Lambda',
        MetricData=[
            {
                'MetricName': 'UsedCodeStorage',
                'Timestamp': datetime.datetime.now().timestamp(),
                'Value': in_use_memory/1024,
                'Unit': 'Gigabytes',
                'StorageResolution': 60
            },
        ]
    )

# Delete the version and return the total of memory freed
def remove_version(version, client, region):
    try:
        client.delete_function(FunctionName=version['FunctionArn'])
        logger.info("{}: {} Delete Successful!".format(region, version['FunctionArn']))
        logger.info("{}: Memory freed {}".format(region, str(version['MemorySize'])))
        return int(version['MemorySize'])
    except Exception as e:
        logger.error('{}: Failed to delete: {}'.format(region, str(e)))
        return 0

def clean_old_lambda_versions(event, context):
    message = []
    ec2_regions = [region['RegionName'] for region in boto3.client('ec2').describe_regions()['Regions']]
    for region in ec2_regions:
        # ap-northeast-3 requires special credentials
        if region == 'ap-northeast-3': continue
        client = initialize_services(region)
        functions = client[0].list_functions()['Functions']
        memory_usage = int(client[0].get_account_settings()['AccountUsage']['TotalCodeSize'])
        memory_free = 0
        if len(functions) != 0:
            logger.info('{}: Functions found, checking for versions'.format(region))
            for function in functions:
                memory_free += read_versions_from_funtion(function, event, client[0], region)
            in_use_memory = int(int(client[0].get_account_settings()['AccountUsage']['TotalCodeSize'])/1024)
            logger.info("{}: Total memory freed: {} MB and in usage: {} MB".format(region, str(memory_free), str(in_use_memory)))
            put_metrics_cloudwatch(client[1], in_use_memory)
            message.append("{}: Review Function completed!".format(region))
        else:
            message.append("{}: No function review in that region!".format(region))
    return message
