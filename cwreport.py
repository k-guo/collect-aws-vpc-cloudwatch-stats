"""
AWS Disclaimer.

(c) 2020 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer
Agreement available at https://aws.amazon.com/agreement/ or other written
agreement between Customer and Amazon Web Services, Inc.

This Python Script fetches Amazon CloudWatch metrics for a given AWS service in a given
region and generates a CSV report for the metrics information

"""

import csvconfig
import yaml
import datetime
import sys
import os
import csv
import logging
import boto3
from botocore.exceptions import ClientError
import argparse

# make sure we are running with python 3
if sys.version_info < (3, 0):
    print("Sorry, this script requires Python 3 to run")
    sys.exit(1)


# setup logging function
def setup_logging():
    """
        Logging Function.

        Creates a global log object and sets its level.
        """
    global log
    log = logging.getLogger()
    log_levels = {'INFO': 20, 'WARNING': 30, 'ERROR': 40}

    if 'logging_level' in os.environ:
        log_level = os.environ['logging_level'].upper()
        if log_level in log_levels:
            log.setLevel(log_levels[log_level])
        else:
            log.setLevel(log_levels['ERROR'])
            log.error("The logging_level environment variable is not set to INFO, WARNING, or \
                    ERROR.  The log level is set to ERROR")
    else:
        log.setLevel(log_levels['ERROR'])
        log.warning('The logging_level environment variable is not set. The log level is set to \
                    ERROR')
        log.info('Logging setup complete - set to \
            log level ' + str(log.getEffectiveLevel()))

setup_logging()

# set default values
allowed_services = ["lambda", "ec2", "rds", "alb", "nlb", "apigateway", "tgw", 'tgwattachment']
use_profile = False
region = "ap-southeast-1"

# Open the metrics configuration file metrics.yaml and retrive settings
with open("metrics.yaml", 'r') as f:
        metrics = yaml.load(f, Loader=yaml.FullLoader)

# Retrieve argument
parser = argparse.ArgumentParser()
parser.add_argument("service", choices=["lambda", "ec2", "rds", "alb", "nlb", "apigateway", "tgw", "tgwattachment"], help="The AWS Service to pull metrics for. Supported \
         services are lambda, ec2, rds, alb, nlb, apigateway, tgw, and tgwattachment")
parser.add_argument("-r", "--region", help="The AWS Region to pull \
    metrics from, the default is ap-southeast-1")
parser.add_argument("-p", "--profile", help="The credential profile to \
     use if not using default credentials")

args = parser.parse_args()


# Retrieve script arguments
service = args.service

if args.region is None and args.profile is None:
    print("Fetching {serv} metrics for the past {hrs}hour(s) with {sec}second(s) \
        period....".format(serv=service, hrs=metrics['hours'], sec=metrics['period']))
    print("No region and credential profile passed, using default \
        region \"ap-southeast-1\" and using default configured AWS credentials to run script")
if args.region and args.profile is None:
    region = args.region
    print("Fetching {serv} metrics for the past {hrs}hour(s) with {sec}second(s) \
        period....".format(serv=service, hrs=metrics['hours'], sec=metrics['period']))
    print("Region argument passed. Using region \"{reg}\" and using the \
        default AWS Credentials to run script".format(reg=region))
if args.profile and args.region is None:
    profile = args.profile
    print("Fetching {serv} metrics for the past {hrs}hour(s) with {sec}second(s)\
        period....".format(serv=service, hrs=metrics['hours'], sec=metrics['period']))
    print("Credential profile passed. Using default region ap-southeast-1 and \
        using profile \"{prof}\" to run script".format(prof=profile))
    use_profile = True
if args.region and args.profile:
    region = args.region
    profile = args.profile
    print("Fetching {serv} metrics for the past {hrs}hour(s) with {sec}second(s) \
        period....".format(serv=service, hrs=metrics['hours'], sec=metrics['period']))
    print("Credential profile and region passed. Using region \"{reg}\" and \
        using profile \"{prof}\" to run script".format(reg=region, prof=profile))
    use_profile = True

# Create boto3 session
if use_profile:
    session = boto3.session.Session(region_name=region, profile_name=profile)
else:
    session = boto3.session.Session(region_name=region)

# create boto clients
cw = session.client('cloudwatch')
ec2 = session.resource('ec2')
rds = session.client('rds')
lda = session.client('lambda')
elbv2 = session.client('elbv2')
apigateway = session.client('apigateway')
tgw = session.client('ec2')
tgwattachment = session.client('ec2')


# Get all the resources of a particular service in a particular region and return
def get_all_resources(resource_type):
    if resource_type == 'ec2':
        return ec2.instances.filter(
            Filters=[
                {'Name': 'instance-state-name', 'Values': ['running']}])
    elif resource_type == 'rds':
        result = rds.describe_db_instances()
        return result['DBInstances']
    elif resource_type == 'lambda':
        result = lda.list_functions()
        return result['Functions']
    elif resource_type == 'alb':
        alb_list = []
        result = elbv2.describe_load_balancers()
        for lb in result['LoadBalancers']:
            if lb['Type'] == 'application':
                alb_list.append(lb)
        return alb_list
    elif resource_type == 'nlb':
        nlb_list = []
        result = elbv2.describe_load_balancers()
        for lb in result['LoadBalancers']:
            if lb['Type'] == 'network':
                nlb_list.append(lb)
        return nlb_list
    elif resource_type == 'apigateway':
        result = apigateway.get_rest_apis()
        return result['items']
    elif resource_type == 'tgw':
        tgw_list = []
        #Find all TGW's in the region regardless of state
        tgw_result=tgw.describe_transit_gateways()
        #print (tgw_result)
        #Return a list of avaialble TGW's based on their states
        for gateway in tgw_result['TransitGateways']:
            if gateway['State'] == 'available':
                tgw_list.append(gateway)
        return tgw_list
    elif resource_type == 'tgwattachment':
        attachment_list = []
        #Find all Attachments in the region regardless of state
        result=tgw.describe_transit_gateway_attachments()
        #print (result)
        #Return a list of available attachments based on their states
        for attachment in result['TransitGatewayAttachments']:
            if attachment['State'] == 'available':
                attachment_list.append(attachment)
        #print(attachment_list)
        return attachment_list

        

'''
Get all the metrics datapoint for the metrics listed in metrics.yaml
for the service script is executed against
'''


def get_metrics(service, resource_id):
    #Note the resource_id can be a string or a list (specifically for TGW attachments)
    datapoints = {}
    now = datetime.datetime.now()
    for metric in metrics['metrics_to_be_collected'][service]:
        if 'statistics' in metric.keys():
            statistics = metric['statistics']
        else:
            statistics = metrics['statistics']
#If we're collecting tgw attachment stats, metric dimensions have to include
#both the TransitGateway dimension AND TransitGatewayAttachment
        if service == 'tgwattachment':
            metric_dimensions=[
            {
                'Name': metric['dimension_name'],
                'Value': resource_id[0]
            },
            {
                'Name': 'TransitGateway',
                'Value': resource_id[1]
            }
            ]
        else:
            metric_dimensions=[
            {
                'Name': metric['dimension_name'],
                'Value': resource_id
            }
            ]
        result = cw.get_metric_statistics(
            Namespace=metric['namespace'],
            MetricName=metric['name'],
            Dimensions=metric_dimensions,
            Unit=metric['unit'],
            Period=metrics['period'],
            StartTime=now - datetime.timedelta(hours=metrics['hours']),
            EndTime=now,
            Statistics=[statistics]
        )
        actual_datapoint = []
        for datapoint in result['Datapoints']:
            actual_datapoint.append(float(datapoint[statistics]))
        if len(actual_datapoint) == 0:
            actual_datapoint.append(0)
        datapoints[metric['name']] = actual_datapoint

    return datapoints

# get all resources and return a list
resources = get_all_resources(service)
print ('Finished searching for the',service,'resources')

filename = service+".csv"
#filename = service+datetime.datetime.now().strftime("-%b-%d-%H-%M-%S")+".csv"
with open(filename, 'w') as csvfile:
    # initialize csv writer
    csvwriter = csv.writer(
        csvfile,
        delimiter=',',
        quotechar='"',
        quoting=csv.QUOTE_MINIMAL)

    # write the headers to csv
    csv_headers = csvconfig.make_csv_header(service)
    csvwriter.writerow(csv_headers)

    # From the list of returned resources, get metrics for each resource
    for resource in resources:

        # get the resource id to be used for metric dimension value
        if service == 'ec2':
            resource_id = resource.id
        elif service == 'rds':
            resource_id = resource['DBInstanceIdentifier']
        elif service == 'lambda':
            resource_id = resource['FunctionName']
        elif service == 'alb':
            lb_arn_split = resource['LoadBalancerArn'].split("loadbalancer/")
            resource_id = lb_arn_split[1]
        elif service == 'nlb':
            lb_arn_split = resource['LoadBalancerArn'].split("loadbalancer/")
            resource_id = lb_arn_split[1]
        elif service == 'apigateway':
            resource_id = resource['name']
        elif service == 'tgw':
            tgw_arn_split = resource['TransitGatewayArn'].split("transit-gateway/")
            resource_id = tgw_arn_split[1]
        elif service == 'tgwattachment':
            #If statsitcs for TGW Attachments is requested,
            #create a list to preserve both the tgw ID and attachment ID
            resource_id = [resource['TransitGatewayAttachmentId'], resource['TransitGatewayId']]

        print("Collecting Cloudwatch statsitcs for resource",resource_id)
        metrics_info = get_metrics(service, resource_id)
        if service == 'ec2' or service =='tgwattachment':
            csvconfig.write_to_csv(service, csvwriter, resource, metrics_info)
        else:
            csvconfig.write_to_csv(service, csvwriter, resource_id, metrics_info)

    print('CSV file %s created.' % filename)
