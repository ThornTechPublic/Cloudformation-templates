# SFTP Gateway

This is a secure, pre-configured SFTP server that saves uploaded files to an Amazon S3 bucket. A lot of business processes and COTS software still use SFTP, and this is a great way to get important files into a durable S3 layer.

* **[AMI Marketplace page](https://aws.amazon.com/marketplace/pp/B072M8VY8M?qid=1506098175364&sr=0-1&ref_=srh_res_product_title)**: Check out product details, and `subscribe` so your AWS account can instantiate the AMI.
* **[Wiki page](https://bitbucket.org/thorntechnologies/sftpgateway-public/wiki/Home)**: Usage instructions, troubleshooting, and other useful information
* **[CloudFormation template](https://s3.amazonaws.com/thorntech-public-documents/cf-templates/SFTPGateway.cf)**: Spin up the AMI, S3 bucket, security group, and everything else you need. The template itself has some good syntax for EC2, which makes it a useful reference.