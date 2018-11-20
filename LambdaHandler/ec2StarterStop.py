# This script start and stop instances that are tagged with the tag lambda and value true.
# Ensure that your Lmabda Function have the right permissions SNS:Publish, EC2:DescribeInstances, EC2:DescribeRegions, EC2:StartInstances, EC2:StopInstances 
# The event payload must match the following

# { "status":"start", "phone_number":"123123123123"}

#import logging
import boto3

## Initialize logger and set log level
#logger = logging.getLogger()
#logger.setLevel(logging.INFO)

# Initialize Ec2 and sns client for Ireland region
client = boto3.client('ec2')
client_sns = boto3.client('sns')

def send_message(status, phone_number, exception):
    response = client_sns.publish(
                     PhoneNumber=phone_number,
                     Message='Failed to {} the Instance, due to {}'.format(status, exception),
                     MessageAttributes={
                         'AWS.SNS.SMS.SenderID': {
                             'DataType': 'String',
                             'StringValue': 'EC2{}'.format(status)
                         },
                         'AWS.SNS.SMS.SMSType': {
                             'DataType': 'String',
                             'StringValue': 'Transactional'
                            }
                        }
                    )

def lambda_handler(event, context):
    ec2_regions = [region['RegionName'] for region in client.describe_regions()['Regions']]
    message = []
    for region in ec2_regions:
        session = boto3.Session(
            region_name=region
        )
        client_ec2 = session.client('ec2')
        response = client_ec2.describe_instances(Filters=[{'Name':'tag:lambda','Values':['true','True']}])
        if response['Reservations'] != []:
            for group_instance in response['Reservations']: 
                instance = group_instance['Instances'][0]
                instance_id = instance['InstanceId']
                if event['status'] == 'stop':
                    if instance['State']['Name'] == 'running':
                          try:
                            client_ec2.stop_instances(InstanceIds=[instance_id])                    
                            message.append('{}: Instance {} is being stopped.'.format(region, instance_id))
                          except Exception as e:
                            send_message('Stop', phone_number, e)
                            message.append('{}: Failed to stop Instance {}, due to error {}.'.format(region,instance_id, e))
                    else: message.append('{}: Instance {} is not running.'.format(region, instance_id))
                elif event['status'] == 'start':
                    if instance['State']['Name'] == 'stopped':
                        try:
                            client_ec2.start_instances(InstanceIds=[instance_id])
                            message.append('{}: Instance {} is being started.'.format(region, instance_id))
                        except Exception as e:
                            send_message('Start', phone_number, e)
                            message.append('{}: Failed to start Instance {}, due to error {}.'.format(region, instance_id, e))
                    else: message.append('{}: Instance {} is not stopped.'.format(region, instance_id))
        else: message.append("{}: No Instances tagged.".format(region))
    return message
