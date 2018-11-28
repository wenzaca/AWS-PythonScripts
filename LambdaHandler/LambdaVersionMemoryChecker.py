import logging
import boto3

# Initialize logger and set log level
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize Lambda and CloudWatch client for the specific region
def initialize_services(region):
    return boto3.client('lambda', region_name=region)

# Read all the verions from the Functions in that region
# versions = versions_all[1:-5]
# This would change list from:
# ["Latest", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
# To:
# [1, 2, 3, 4, 5, 6, 7, 8]
def read_versions_from_funtion(function, event, client_lambda, region):
    versions_all = client_lambda.list_versions_by_function(FunctionName=function['FunctionArn'])['Versions']
    versions = versions_all[1:-int(event.get('num_versions', 1))]

    if not len(versions): logger.info('{}: No versions older than the specified value for FunctionName={}'.format(region, function['FunctionArn']))
    for version in versions:
        if version['Version'] != function['Version']:
            arn = version['FunctionArn']
            logger.info('{}: FunctionName={}'.format(region, arn))
            logger.info('{}: Memory size of this version: {} MB\n'.format(region, int(version['CodeSize'])/1024))

            if not event.get('read_only', True): remove_version(version, client_lambda, region)
        else:
            logger.info('{}: Ignoring Latest version for function: {}'.format(region, function['Version']))

# Delete the version and catch an exception if failed to be deleted.
# Function with alias cannot be deleted by this code.
def remove_version(version, client, region):
    try:
        client.delete_function(FunctionName=version['FunctionArn'])
        logger.info('{}: {} Delete Successful!'.format(region, version['FunctionArn']))
    except Exception as e:
        logger.error('{}: Failed to delete: {}'.format(region, str(e)))

def lambda_handler(event, context):
    message = []
    regions = []
    regions = [region['RegionName'] for region in boto3.client('ec2').describe_regions()['Regions']]
    # Check for region in the events
    if event.get('region', ''):
        if event['region'] not in regions: return 'Invalid Region'
        regions = [event['region']]
    for region in regions:
        # ap-northeast-3 requires special credentials
        if region == 'ap-northeast-3': continue
        client = initialize_services(region)
        functions = client.list_functions()['Functions']
        memory_usage = int(client.get_account_settings()['AccountUsage']['TotalCodeSize'])
        memory_free = 0
        if len(functions) != 0:
            logger.info('{}: Found {} Functions, checking for versions'.format(region, len(functions)))
            for function in functions:
                read_versions_from_funtion(function, event, client, region)
            memory_after_prunning = client.get_account_settings()['AccountUsage']['TotalCodeSize']/1024
            logger.info('{}: Total memory freed: {} MB and in usage: {} MB'.format(region, str(memory_usage/1024 - memory_after_prunning), memory_after_prunning))
            message.append('{}: Review Function completed!'.format(region))
        else:
            message.append('{}: No function review in that region!'.format(region))
    return message
