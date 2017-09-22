from troposphere import Ref, Template, GetAtt, Parameter, Base64, Output, Join, Tags, GetAZs, Select, If, Equals, Condition, FindInMap
from troposphere.ec2 import VPC, Subnet, InternetGateway, VPCGatewayAttachment, RouteTable, SubnetRouteTableAssociation, Route, EIP, NatGateway, SecurityGroup, Instance, SecurityGroupRule, NetworkInterfaceProperty
from troposphere.s3 import Bucket, PublicRead, BucketPolicy, CorsConfiguration, CorsRules
from troposphere.rds import DBSubnetGroup, DBInstance, DBCluster
from troposphere.iam import Policy, User, AccessKey, Role, InstanceProfile, PolicyType as IAMPolicy
from troposphere.cloudfront import Distribution, DistributionConfig
from troposphere.cloudfront import Origin, DefaultCacheBehavior
from troposphere.cloudfront import ForwardedValues
from troposphere.cloudfront import S3Origin
import awacs
from awacs import s3
from awacs.aws import Principal, Everybody, Allow, Statement
from awacs.sts import AssumeRole

t = Template()

t.add_mapping("RegionMap", {
    "us-east-1": {"AMI": "ami-4fffc834"},
    "us-east-2": {"AMI": "ami-ea87a78f"},
    "us-west-1": {"AMI": "ami-3a674d5a"},
    "us-west-2": {"AMI": "ami-aa5ebdd2"}
})

keyname_param = t.add_parameter(Parameter(
    "KeyName",
    Description="Name of an existing EC2 KeyPair to enable SSH access to the instance",
    Type="AWS::EC2::KeyPair::KeyName",
))


dbclustername = t.add_parameter(Parameter(
    "DBClusterName",
    Default="testcluster",
    Description="This is the name of your Aurora DB instance (e.g. testcluster)",
    Type="String",
    MinLength="2",
    AllowedPattern="[a-zA-Z][a-zA-Z0-9]*",
    ConstraintDescription=("Must be alphanumeric and start with a letter.")
))

dbclass = t.add_parameter(Parameter(
    "DBClass",
    Default="db.t2.small",
    Description="DB instance type",
    Type="String",
    AllowedValues=[
        "db.t2.small",
        "db.t2.medium",
        "db.r3.large",
        "db.r3.xlarge",
        "db.r3.2xlarge",
        "db.r3.4xlarge",
        "db.r3.8xlarge"
    ],
    ConstraintDescription="Must select a valid database instance type.",
))

ec2class = t.add_parameter(Parameter(
    "EC2Class",
    Default="t2.micro",
    Description="EC2 instance type",
    Type="String",
    AllowedValues=[
        "t2.micro",
        "t2.small",
        "t2.medium"
        "m4.large",
        "m4.xlarge",
    ],
    ConstraintDescription="Must select a valid EC2 instance type.",
))

dbpassword = t.add_parameter(Parameter(
    "DBPassword",
    NoEcho=True,
    Description="Password for the Aurora DB master user account (you can reset this in RDS later if you forget). Must contain at least 8 characters. Do not use /, @, single, or double quotes.",
    Type="String",
    MinLength="8",
    ConstraintDescription="Must contain at least 8 characters. Do not use /, @, single, or double quotes."
))

# VPC
MyVPC = t.add_resource(
    VPC(
        'MyVPC',
        CidrBlock='192.168.100.0/24'
    )
)

# Public subnet for web server
subnet_public = t.add_resource(
    Subnet(
        'PublicSubnet',
        CidrBlock='192.168.100.0/28',
        MapPublicIpOnLaunch=True,
        VpcId=Ref(MyVPC)
    )
)

# Private subnets for DB
subnet_private_A = t.add_resource(
    Subnet(
        'PrivateSubnetA',
        AvailabilityZone=Select(0,GetAZs("")),
        CidrBlock='192.168.100.16/28',
        MapPublicIpOnLaunch=False,
        VpcId=Ref(MyVPC)
    )
)

subnet_private_B = t.add_resource(
    Subnet(
        'PrivateSubnetB',
        AvailabilityZone=Select(1,GetAZs("")),
        CidrBlock='192.168.100.32/28',
        MapPublicIpOnLaunch=False,
        VpcId=Ref(MyVPC)
    )
)

# Internet GW on the VPC to allow internet access
igw = t.add_resource(InternetGateway('InternetGateway',))

# Attaches IGW to VPC
net_gw_vpc_attachment = t.add_resource(
    VPCGatewayAttachment(
        "AttachGateway",
        VpcId=Ref(MyVPC),
        InternetGatewayId=Ref(igw),
    )
)

# Public route table on the VPC
public_route_table = t.add_resource(
    RouteTable(
        'PublicRouteTable',
        VpcId=Ref(MyVPC),
        DependsOn="AttachGateway"
    )
)

# Wires public route table to public subnet
public_route_association = t.add_resource(
    SubnetRouteTableAssociation(
        'PublicRouteAssociation',
        SubnetId=Ref(subnet_public),
        RouteTableId=Ref(public_route_table),
    )
)

# On the Public route table, send ANY traffic to the IGW
default_public_route = t.add_resource(
    Route(
        'PublicDefaultRoute',
        RouteTableId=Ref(public_route_table),
        DestinationCidrBlock='0.0.0.0/0',
        GatewayId=Ref(igw),
    )
)

EC2SecurityGroup = t.add_resource(
    SecurityGroup(
        'EC2SecurityGroup',
        GroupDescription='Enable web traffic',
        SecurityGroupIngress=[
            SecurityGroupRule(
                IpProtocol='tcp',
                FromPort='80',
                ToPort='80',
                CidrIp='0.0.0.0/0'),
            SecurityGroupRule(
                IpProtocol='tcp',
                FromPort='443',
                ToPort='443',
                CidrIp='0.0.0.0/0'),
            SecurityGroupRule(
                IpProtocol='tcp',
                FromPort='22',
                ToPort='22',
                CidrIp='0.0.0.0/0')
        ],
        VpcId=Ref(MyVPC),
    ))

# RDS DB security group
rdssecuritygroup = t.add_resource(
    SecurityGroup(
        "RDSSecurityGroup",
        GroupDescription="Security group for RDS DB Instance.",
        SecurityGroupIngress=[
            SecurityGroupRule(
                IpProtocol='tcp',
                FromPort='3306',
                ToPort='3306',
                SourceSecurityGroupId=Ref(EC2SecurityGroup),
            )
        ],
        VpcId=Ref(MyVPC),
        DependsOn="EC2SecurityGroup"
    )
)

# RDS DB subnet group
mydbsubnetgroup = t.add_resource(
    DBSubnetGroup(
        "MyDBSubnetGroup",
        DBSubnetGroupDescription="Subnets available for the RDS DB Instance",
        SubnetIds=[
            Ref(subnet_private_A),
            Ref(subnet_private_B)
        ],
        DependsOn=["PrivateSubnetA", "PrivateSubnetB"]
    )
)

mydbcluster = t.add_resource(
    DBCluster(
        "AuroraDBCluster",
        AvailabilityZones=[
            Select(0,GetAZs("")),
            Select(1,GetAZs(""))
        ],
        DatabaseName=Ref(dbclustername),
        Engine="aurora",
        EngineVersion="5.6.10a",
        DBSubnetGroupName=Ref(mydbsubnetgroup),
        MasterUsername="admin",
        MasterUserPassword=Ref(dbpassword),
        VpcSecurityGroupIds=[Ref(rdssecuritygroup)]
    )
)

# Aurora DB
mydbA = t.add_resource(
    DBInstance(
        "AuroraDBA",
        DeletionPolicy="Delete",
        DBInstanceClass=Ref(dbclass),
        DBClusterIdentifier=Ref(mydbcluster),
        Engine="aurora",
        EngineVersion="5.6.10a",
        DBSubnetGroupName=Ref(mydbsubnetgroup),
        AvailabilityZone=Select(0,GetAZs("")),
        MultiAZ=False,
        PubliclyAccessible=False
    )
)

mydbB = t.add_resource(
    DBInstance(
        "AuroraDBB",
        DeletionPolicy="Delete",
        DBInstanceClass=Ref(dbclass),
        DBClusterIdentifier=Ref(mydbcluster),
        Engine="aurora",
        EngineVersion="5.6.10a",
        DBSubnetGroupName=Ref(mydbsubnetgroup),
        AvailabilityZone=Select(1,GetAZs("")),
        MultiAZ=False,
        PubliclyAccessible=False
    )
)

# EC2 instance
ec2_instance = t.add_resource(
    Instance(
        "WebServer",
        ImageId=FindInMap("RegionMap", Ref("AWS::Region"), "AMI"),
        InstanceType=Ref(ec2class),
        KeyName=Ref(keyname_param),
        NetworkInterfaces=[
            NetworkInterfaceProperty(
                GroupSet=[
                    Ref(EC2SecurityGroup)],
                AssociatePublicIpAddress='true',
                DeviceIndex='0',  # eth0
                SubnetId=Ref(subnet_public)
            )
        ],
        DependsOn=["AuroraDBA", "AuroraDBB"],
        UserData=Base64(Join('', [
            '#!/bin/bash',
            '\n',
            'sudo yum install mysql -y'
        ])),
    )
)

ipAddress = t.add_resource(EIP('IPAddress',
    DependsOn='AttachGateway',
    Domain='vpc',
    InstanceId=Ref(ec2_instance)
))

t.add_metadata({
    'AWS::CloudFormation::Interface': {
        'ParameterGroups': [
            {
                'Label': {'default': 'EC2 instance'},
                'Parameters': ['EC2Class', 'KeyName']
            },
            {
                'Label': {'default': 'Aurora DB'},
                'Parameters': ['DBClusterName', 'DBPassword', 'DBClass']
            },
        ],
        'ParameterLabels': {
            'AccountId': {'default': 'AWS Account Id'},
        }
    }
})

t.add_output(Output(
    "EIPDNS",
    Description="Elastic IP address",
    Value=Ref(ipAddress)
))

t.add_output(Output(
    "RDSEndpoint",
    Description="RDS Endpoint",
    Value=GetAtt("AuroraDBCluster", "Endpoint.Address")
))

print(t.to_json())
