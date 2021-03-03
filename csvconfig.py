"""
AWS Disclaimer.

(c) 2020 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer
Agreement available at https://aws.amazon.com/agreement/ or other written
agreement between Customer and Amazon Web Services, Inc.

This script is a module called by cwreport.py, it creates the csv file
"""
import yaml
import numpy

# Open the metrics configuration file metrics.yaml and retrive settings
with open("metrics.yaml", 'r') as f:
    metrics = yaml.load(f, Loader=yaml.FullLoader)

# Function to determine the statistic type the user is trying to calculate from the statistic varible in metrics.yaml
# Supported statistics are average, min, max, sum. It is called in write_to_csv()
def requested_overall_statistic(data):
    user_request = metrics['statistics']
    #Check for user requested statistic type from metrics.yaml
    if user_request.lower() == 'maximum':
        method_to_call = getattr(numpy, 'max')
        output = method_to_call(data)
    elif user_request.lower() == 'minimum':
        method_to_call = getattr(numpy, 'min')
        output = method_to_call(data)
    elif user_request.lower() == 'sum':
        method_to_call = getattr(numpy, 'sum')
        output = method_to_call(data)
    elif user_request.lower() == 'average':
        method_to_call = getattr(numpy, 'average')
        output = method_to_call(data)
    else:
        method_to_call = getattr(numpy, 'size')
        output = method_to_call(data)
    return output

# Construct csv headers and return
def make_csv_header(service):
    if service == 'ec2':
        csv_headers = [
                'Name',
                'Instance',
                'Type',
                'Hypervisor',
                'Virtualization Type',
                'Architecture',
                'EBS Optimized',
                'CPUUtilization (Percent)',
                'DiskReadOps (Count)',
                'DiskWriteOps (Count)',
                'DiskReadBytes (Bytes)',
                'DiskWriteBytes (Bytes)',
                'NetworkIn (Bytes)',
                'NetworkOut (Bytes)',
                'NetworkPacketsIn (Count)',
                'NetworkPacketsOut (Count)'
            ]
        return csv_headers
    elif service == 'tgwattachment':
        csv_headers = [
                'Attachment ID',
                'TransitGateway ID',
                'Resource Type',
                'Resource ID',
                'BytesIn',
                'BytesOut',
                'PacketsIn (Count)',
                'PacketsOut (Count)',
                'PacketDropCountBlackhole (Count)',
                'PacketDropCountNoRoute (Count)'
            ]
        return csv_headers
    else:
        csv_headers = ['Resource Identifier']
        for metric in metrics['metrics_to_be_collected'][service]:
            csv_headers.append(metric['name']+" ("+metric['unit']+")")

        return csv_headers


# function to write to csv
def write_to_csv(service, csvwriter, resource, metrics_info):
    if service == 'ec2':
        # get instance name
        if resource.tags:
            name_dict = next(
                (i for i in resource.tags if i['Key'] == 'Name'),
                None)
        else:
            name_dict = None
        csvwriter.writerow([
            '' if name_dict is None else name_dict.get('Value'),
            resource.id,
            resource.instance_type,
            resource.hypervisor,
            resource.virtualization_type,
            resource.architecture,
            resource.ebs_optimized,
            numpy.round(requested_overall_statistic(metrics_info['CPUUtilization']), 2),
            numpy.round(requested_overall_statistic(metrics_info['DiskReadOps']), 2),
            numpy.round(requested_overall_statistic(metrics_info['DiskWriteOps']), 2),
            numpy.round(requested_overall_statistic(metrics_info['DiskReadBytes']), 2),
            numpy.round(requested_overall_statistic(metrics_info['DiskWriteBytes']), 2),
            numpy.round(requested_overall_statistic(metrics_info['NetworkIn']), 2),
            numpy.round(requested_overall_statistic(metrics_info['NetworkOut']), 2),
            numpy.round(requested_overall_statistic(metrics_info['NetworkPacketsIn']), 2),
            numpy.round(requested_overall_statistic(metrics_info['NetworkPacketsOut']), 2)
        ])
    elif service == 'tgwattachment':
        # get attachment name
        if resource['Tags']:
            name_dict = next(
                (i for i in resource['Tags'] if i['Key'] == 'Name'),
                None)
        else:
            name_dict = None
        csvwriter.writerow([
            resource['TransitGatewayAttachmentId'] if name_dict is None else name_dict.get('Value'),
            resource['TransitGatewayId'],
            resource['ResourceType'],
            resource['ResourceId'],
            numpy.round(requested_overall_statistic(metrics_info['BytesIn']), 2),
            numpy.round(requested_overall_statistic(metrics_info['BytesOut']), 2),
            numpy.round(requested_overall_statistic(metrics_info['PacketsIn']), 2),
            numpy.round(requested_overall_statistic(metrics_info['PacketsOut']), 2),
            numpy.round(requested_overall_statistic(metrics_info['PacketDropCountBlackhole']), 2),
            numpy.round(requested_overall_statistic(metrics_info['PacketDropCountNoRoute']), 2)
        ])
    else:
        row_data = [resource]
        for metric in metrics['metrics_to_be_collected'][service]:
            row_data.append(numpy.round(requested_overall_statistic(metrics_info[metric['name']]), 2))
        csvwriter.writerow(row_data)
