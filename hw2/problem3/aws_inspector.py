#!/usr/bin/env python3
import boto3
import json
import sys
import argparse
import os
from datetime import datetime
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError


# A: authentication 
def authenticate(region=None):
    try:
        session = boto3.session.Session(region_name=region)
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        return session, identity
    except NoCredentialsError:
        print("[ERROR] No AWS credentials found")
        sys.exit(1)
    except ClientError as e:
        print(f"[ERROR] Authentication failed: {e}")
        sys.exit(1)


# users 
def get_iam_users(session):
    users_data = []
    iam = session.client("iam")
    try:
        users = iam.list_users()["Users"]
        for user in users:
            u = {
                "username": user["UserName"],
                "user_id": user["UserId"],
                "arn": user["Arn"],
                "create_date": user["CreateDate"].isoformat(),
                "last_activity": None,
                "attached_policies": []
            }

            # Last activity
            try:
                details = iam.get_user(UserName=user["UserName"])
                if "PasswordLastUsed" in details["User"]:
                    u["last_activity"] = details["User"]["PasswordLastUsed"].isoformat()
            except ClientError:
                pass

            # policies
            try:
                policies = iam.list_attached_user_policies(UserName=user["UserName"])
                for p in policies.get("AttachedPolicies", []):
                    u["attached_policies"].append({
                        "policy_name": p["PolicyName"],
                        "policy_arn": p["PolicyArn"]
                    })
            except ClientError:
                pass

            users_data.append(u)
        return users_data
    except ClientError:
        print("Access denied for IAM operations")
        return []


# EC2 Instances - Elastic Compute Cloud Instances
def get_ec2_instances(session):
    instances_data = []
    ec2 = session.client("ec2")
    try:
        reservations = ec2.describe_instances()["Reservations"]
        for res in reservations:
            for inst in res["Instances"]:
                tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
                data = {
                    "instance_id": inst["InstanceId"],
                    "instance_type": inst["InstanceType"],
                    "state": inst["State"]["Name"],
                    "public_ip": inst.get("PublicIpAddress"),
                    "private_ip": inst.get("PrivateIpAddress"),
                    "availability_zone": inst["Placement"]["AvailabilityZone"],
                    "launch_time": inst["LaunchTime"].isoformat(),
                    "ami_id": inst["ImageId"],
                    "ami_name": None,
                    "security_groups": [sg["GroupId"] for sg in inst.get("SecurityGroups", [])],
                    "tags": tags
                }

                # Get AMI name
                try:
                    img = ec2.describe_images(ImageIds=[inst["ImageId"]])
                    if img["Images"]:
                        data["ami_name"] = img["Images"][0].get("Name")
                except ClientError:
                    pass

                instances_data.append(data)
        return instances_data
    except ClientError:
        print("Access denied for operations- skipping enumeration")
        return []


# S3 Buckets - Simple Storage Service
def get_s3_buckets(session):
    buckets_data = []
    s3 = session.client("s3")
    try:
        buckets = s3.list_buckets()["Buckets"]
        for b in buckets:
            bucket_name = b["Name"]
            bucket_info = {
                "bucket_name": bucket_name,
                "creation_date": b["CreationDate"].isoformat(),
                "region": None,
                "object_count": 0,
                "size_bytes": 0
            }

            try:
                loc = s3.get_bucket_location(Bucket=bucket_name)
                bucket_info["region"] = loc.get("LocationConstraint") or "us-east-1"

                # Count objects + size
                obj_count, total_size = 0, 0
                paginator = s3.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=bucket_name):
                    for obj in page.get("Contents", []):
                        obj_count += 1
                        total_size += obj["Size"]
                bucket_info["object_count"] = obj_count
                bucket_info["size_bytes"] = total_size
            except ClientError:
                print(f"Failed to access S3 bucket '{bucket_name}': Access Denied")

            buckets_data.append(bucket_info)
        return buckets_data
    except ClientError:
        print("Access denied for S3 operations - skipping enumeration")
        return []


# security groups 
def get_security_groups(session):
    groups_data = []
    ec2 = session.client("ec2")
    try:
        groups = ec2.describe_security_groups()["SecurityGroups"]
        for g in groups:
            inbound = []
            for rule in g.get("IpPermissions", []):
                ports = f"{rule.get('FromPort','all')}-{rule.get('ToPort','all')}" if "FromPort" in rule else "all"
                for ip in rule.get("IpRanges", []):
                    inbound.append({"protocol": rule.get("IpProtocol", "all"), "port_range": ports, "source": ip["CidrIp"]})
            outbound = []
            for rule in g.get("IpPermissionsEgress", []):
                ports = f"{rule.get('FromPort','all')}-{rule.get('ToPort','all')}" if "FromPort" in rule else "all"
                for ip in rule.get("IpRanges", []):
                    outbound.append({"protocol": rule.get("IpProtocol", "all"), "port_range": ports, "destination": ip["CidrIp"]})

            groups_data.append({
                "group_id": g["GroupId"],
                "group_name": g.get("GroupName"),
                "description": g.get("Description"),
                "vpc_id": g.get("VpcId"),
                "inbound_rules": inbound,
                "outbound_rules": outbound
            })
        return groups_data
    except ClientError:
        print("Access denied for Security Group operations - skipping enumeration")
        return []


# outputs 
def format_output(data, fmt="json"):
    if fmt == "json":
        return json.dumps(data, indent=2)
    elif fmt == "table":
        lines = []
        acct = data["account_info"]
        lines.append(f"AWS Account: {acct['account_id']} ({acct['user_arn']})")
        lines.append(f"Region: {acct['region']}")
        lines.append(f"Scan Time: {acct['scan_timestamp']}\n")

        # IAM
        lines.append(f"IAM USERS ({len(data['resources']['iam_users'])} total)")
        for u in data["resources"]["iam_users"]:
            lines.append(f" - {u['username']} | Created: {u['create_date']} | Last: {u['last_activity']} | Policies: {len(u['attached_policies'])}")

        # EC2 - Elastic Compute Cloud
        running = [i for i in data["resources"]["ec2_instances"] if i["state"] == "running"]
        lines.append(f"\nEC2 INSTANCES ({len(running)} running, {len(data['resources']['ec2_instances'])} total)")
        for i in data["resources"]["ec2_instances"]:
            lines.append(f" - {i['instance_id']} | {i['instance_type']} | {i['state']} | {i['public_ip']} | {i['launch_time']}")

        # SSimple Storage Service 3
        lines.append(f"\nS3 BUCKETS ({len(data['resources']['s3_buckets'])} total)")
        for b in data["resources"]["s3_buckets"]:
            size_mb = b['size_bytes'] / (1024*1024)
            lines.append(f" - {b['bucket_name']} | {b['region']} | {b['creation_date']} | {b['object_count']} objs | {size_mb:.2f} MB")

        # security groups
        lines.append(f"\nSECURITY GROUPS ({len(data['resources']['security_groups'])} total)")
        for g in data["resources"]["security_groups"]:
            lines.append(f" - {g['group_id']} | {g['group_name']} | VPC {g['vpc_id']} | Inbound: {len(g['inbound_rules'])} rules")

        return "\n".join(lines)
    else:
        return "[ERROR] Unknown format"


# main
def main():
    parser = argparse.ArgumentParser(description="AWS Resource Inspector")
    parser.add_argument("--region", help="AWS region to inspect")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    parser.add_argument("--format", choices=["json", "table"], default="json", help="Output format")
    args = parser.parse_args()

    # authentication
    session, identity = authenticate(region=args.region)
    account_info = {
        "account_id": identity["Account"],
        "user_arn": identity["Arn"],
        "region": session.region_name,
        "scan_timestamp": datetime.utcnow().isoformat()
    }

    # collect resources
    resources = {
        "iam_users": get_iam_users(session),
        "ec2_instances": get_ec2_instances(session),
        "s3_buckets": get_s3_buckets(session),
        "security_groups": get_security_groups(session),
    }

    summary = {
        "total_users": len(resources["iam_users"]),
        "running_instances": sum(1 for i in resources["ec2_instances"] if i["state"] == "running"),
        "total_buckets": len(resources["s3_buckets"]),
        "security_groups": len(resources["security_groups"]),
    }

    result = {"account_info": account_info, "resources": resources, "summary": summary}

    output_str = format_output(result, args.format)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output_str)
    else:
        print(output_str)


if __name__ == "__main__":
    main()