import logging
import datetime;
import boto3

# Initialize logger and set log level
logger = logging.getLogger()
logger.setLevel(logging.ERROR)

# Initialize Lambda and CloudWatch client for the specific region
def initialize_services(region):
    return [boto3.client('lambda', region_name = region), boto3.client('cloudwatch', region_name = region)]

# Create CloudWatch Metric for Code Storage usage
def put_metrics_cloudwatch_region(client_cloudwatch, in_use_memory):
    client_cloudwatch.put_metric_data(
        Namespace='AWS/Lambda',
        MetricData=[
            {
                'MetricName': 'TotalCodeSize',
                'Timestamp': datetime.datetime.now().timestamp(),
                'Value': in_use_memory/1024/1024,
                'Unit': 'Gigabytes',
                'StorageResolution': 60
            }
        ]
    )

# Create CloudWatch Metric for Code Storage usage
def put_metrics_cloudwatch(client_cloudwatch, in_use_memory, function_name):
    client_cloudwatch.put_metric_data(
        Namespace='AWS/Lambda',
        MetricData=[
            {
                'MetricName': 'CodeSize',
                'Timestamp': datetime.datetime.now().timestamp(),
                'Value': in_use_memory/1024/1024,
                'Unit': 'Gigabytes',
                'StorageResolution': 60,
                'Dimensions': [
                    {
                        'Name': 'FunctionName',
                        'Value': function_name
                    },{
                        'Name': 'Resource',
                        'Value': function_name
                    },
                ]
            }
        ]
    )


def lambda_handler(event, context):
    message = []
    regions = []
    regions = [region['RegionName'] for region in boto3.client('ec2').describe_regions()['Regions']]
    if event.get('region', ''):
        if event['region'] not in regions: return 'Invalid Region'
        regions = [event['region']]
    for region in regions:
        # ap-northeast-3 requires special credentials
        if region == 'ap-northeast-3': continue

        # Initialize Lambda and CloudWatch Client
        client = initialize_services(region)

        # Adding metric for the region
        put_metrics_cloudwatch_region(client[1], client[0].get_account_settings()['AccountUsage']['TotalCodeSize'])

        functions = client[0].list_functions()['Functions']
        if len(functions) != 0:
            logger.info('{}: Found {} Functions '.format(region, str(len(functions))))
            for function in functions:
                # Adding metric per funtion
                put_metrics_cloudwatch(client[1], function['CodeSize'], function['FunctionName'])
            message.append('{}: Found {} Functions, metrics per Function created'.format(region, str(len(functions))))
        else:
            logger.info('{}: No Function found'.format(region))
            message.append('{}: No Function found'.format(region))
    return message
