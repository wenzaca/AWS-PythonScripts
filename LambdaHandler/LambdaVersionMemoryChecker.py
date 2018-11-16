from __future__ import absolute_import, print_function, unicode_literals
import logging
import boto3

# JSON Event example
# {
#   "topic_arn": "arn:aws:sns:eu-west-1:123456789:S3notification",
#   "notification": false,
#   "read_only": true,
#   "aws_region": "eu-west-1",
#   "num_versions": 0
# }

# Initialize logger and set log level
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize Lambda and SNS client for the specified region
def initialize_services(region):
    session = boto3.Session(region_name=region)
    return [session.client('lambda'), session.client('sns')]

# Validate the events
def validate_event(event):
    if 'aws_region' not in event:
        logger.info('Region not informed, will execute in us-east-1 (N.Virginia)')
        event['aws_region'] = 'us-east-1'
    if 'notification' not in event:
        logger.info('Notification not informed, no notification will be send')
        event['notification'] = True
    if 'num_versions' not in event:
        logger.info('Number of Version not informed, function will check only the latest versions')
        event['num_versions'] = 1
    if 'read_only' not in event:
        logger.info('Read Only not informed, function will only read')
        event['read_only'] = True
    if 'notification' in event and event['notification'] and 'topic_arn' not in event:
        logger.error('Notification allowed but topic not informed')
        return 'Notification allowed but topic not informed'
    if 'topic_arn' in event and event['aws_region'] not in event['topic_arn']:
        logger.error('Topic region is different from the region informed')
        return 'Topic region is different from the region informed'
    return None


# Delete the version and return the total of memory freed
def remove_version(version, client):
    try:
        client.delete_function(FunctionName=version['FunctionArn'])
        logger.info("Delete Successful!")
        logger.info("Memory freed: " + str(version['MemorySize']) + "MB")
        return int(version['MemorySize'])
    except Exception as e:
        logger.error('Failed to delete: ' + str(e))
        return 0


# Send a notification to the Topic input
def alert_memory_usage(memory_usage, topic_arn, client_sns):

    # Send message
    try:
        response = client_sns.publish(
            TopicArn=topic_arn,
            Message="The total size, in bytes, of the account's deployment packages per region is close to the limit. You are using " + memory_usage + "of 76800MB"
        )
        logger.info('Notification Sent to the following topic {}'.format(topic_arn))
    except:
        logger.error('Failed top delete: ' + str(e))


def clean_old_lambda_versions(event, context):
    validation = validate_event(event)
    if bool(validation):
        raise Exception(validation)
    client = initialize_services(event['aws_region'])
    functions = client[0].list_functions()['Functions']
    memory_usage = int(client[0].get_account_settings()['AccountUsage']['TotalCodeSize'])
    # Check if memory usage is above 75% of the maximum for that account in that region.
    # Check if the notifications are allowed.
    if memory_usage >= int(client[0].get_account_settings()['AccountLimit']['TotalCodeSize']) * 0.75 and event['notification']:
        alert_memory_usage(str(int(memory_usage/1024)), event['topic_arn'], client[1])

    if len(functions) != 0:
        memory_free = 0
        logger.info('Listing Functions Versioned')
        for function in functions:

            # versions = versions_all[1:-5]
            # This would change list from:
            # ["Latest", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
            # To:
            # [1, 2, 3, 4, 5, 6, 7, 8]
            versions_all = client[0].list_versions_by_function(FunctionName=function['FunctionArn'])['Versions']
            versions = versions_all[1:-int(event['num_versions'])]

            for version in versions:
                if version['Version'] != function['Version']:
                    arn = version['FunctionArn']
                    logger.info('FunctionName={}'.format(arn))
                    logger.info("Memory size of this version: " + str(version['MemorySize']) + " MB\n")

                    if event['read_only']:
                        break
                    else:
                        memory_free += remove_version(version, client[0])
                else:
                    logger.info("Ignoring Latest version for function: " + function['Version'])

        logger.info("Total memory freed: " + str(memory_free) + "MB\n\t In usage: " + str(
            int(int(client[0].get_account_settings()['AccountUsage']['TotalCodeSize'])/1024))+ "MB")
        return "Review Function completed!"
    else:
        return "No function review in that region!"
