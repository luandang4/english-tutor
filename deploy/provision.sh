#!/usr/bin/env bash
# One-time AWS setup: S3 bucket for TTS audio, IAM role, security group, EC2 instance, Elastic IP.
# Safe to re-run: existing resources are reused.
set -euo pipefail
cd "$(dirname "$0")"
source ./config.sh

MY_IP=$(curl -fsS https://checkip.amazonaws.com)

# --- S3 bucket (private, encrypted, audio expires after 30 days) -------------------------------
if ! aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  aws s3api create-bucket --bucket "$BUCKET" --create-bucket-configuration LocationConstraint="$AWS_REGION" >/dev/null
fi
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-lifecycle-configuration --bucket "$BUCKET" --lifecycle-configuration '{
  "Rules": [{"ID": "expire-tts", "Status": "Enabled", "Filter": {"Prefix": "tts/"}, "Expiration": {"Days": 30}}]}'
echo "bucket: $BUCKET"

# --- IAM role: the instance may only touch its own bucket ---------------------------------------
if ! aws iam get-role --role-name "$APP-ec2" >/dev/null 2>&1; then
  aws iam create-role --role-name "$APP-ec2" --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]}' >/dev/null
fi
aws iam put-role-policy --role-name "$APP-ec2" --policy-name tts-bucket --policy-document "{
  \"Version\": \"2012-10-17\",
  \"Statement\": [
    {\"Effect\": \"Allow\", \"Action\": [\"s3:ListBucket\"], \"Resource\": \"arn:aws:s3:::$BUCKET\"},
    {\"Effect\": \"Allow\", \"Action\": [\"s3:GetObject\", \"s3:PutObject\", \"s3:DeleteObject\"],
     \"Resource\": \"arn:aws:s3:::$BUCKET/*\"}]}"
if ! aws iam get-instance-profile --instance-profile-name "$APP-ec2" >/dev/null 2>&1; then
  aws iam create-instance-profile --instance-profile-name "$APP-ec2" >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name "$APP-ec2" --role-name "$APP-ec2"
  sleep 10  # instance profiles take a moment to become usable
fi

# --- SSH key pair ------------------------------------------------------------------------------
if ! aws ec2 describe-key-pairs --key-names "$KEY_NAME" >/dev/null 2>&1; then
  aws ec2 create-key-pair --key-name "$KEY_NAME" --key-type ed25519 --query KeyMaterial --output text > "$KEY_FILE"
  chmod 400 "$KEY_FILE"
fi

# --- Security group: web open, SSH only from this machine's IP -------------------------------
VPC=$(aws ec2 describe-vpcs --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId' --output text)
SG=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$APP-web" "Name=vpc-id,Values=$VPC" \
  --query 'SecurityGroups[0].GroupId' --output text)
if [ "$SG" = "None" ]; then
  SG=$(aws ec2 create-security-group --group-name "$APP-web" --description "$APP web + ssh" --vpc-id "$VPC" \
    --query GroupId --output text)
  aws ec2 authorize-security-group-ingress --group-id "$SG" --ip-permissions \
    "IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges=[{CidrIp=0.0.0.0/0}]" \
    "IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges=[{CidrIp=0.0.0.0/0}]" >/dev/null
fi
aws ec2 authorize-security-group-ingress --group-id "$SG" \
  --ip-permissions "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=$MY_IP/32,Description=deploy}]" \
  >/dev/null 2>&1 || true
echo "security group: $SG (ssh from $MY_IP)"

# --- EC2 instance ------------------------------------------------------------------------------
ID=$(instance_id)
if [ "$ID" = "None" ]; then
  AMI=$(aws ec2 describe-images --owners 099720109477 \
    --filters 'Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*' \
    --query 'sort_by(Images,&CreationDate)[-1].ImageId' --output text)
  ID=$(aws ec2 run-instances --image-id "$AMI" --instance-type "$INSTANCE_TYPE" --key-name "$KEY_NAME" \
    --security-group-ids "$SG" --iam-instance-profile Name="$APP-ec2" \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3,Encrypted=true}' \
    --metadata-options HttpTokens=required \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$APP}]" \
    --query 'Instances[0].InstanceId' --output text)
  aws ec2 wait instance-running --instance-ids "$ID"
fi
echo "instance: $ID"

# --- Elastic IP (stable address for DNS) -------------------------------------------------------
ALLOC=$(aws ec2 describe-addresses --filters "Name=tag:Name,Values=$APP" --query 'Addresses[0].AllocationId' --output text)
if [ "$ALLOC" = "None" ]; then
  ALLOC=$(aws ec2 allocate-address --domain vpc \
    --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Name,Value=$APP}]" --query AllocationId --output text)
fi
aws ec2 associate-address --instance-id "$ID" --allocation-id "$ALLOC" >/dev/null
echo "public IP: $(public_ip)"
