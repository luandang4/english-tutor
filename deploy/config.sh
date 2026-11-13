# Shared settings for the deploy scripts (no secrets here).
export AWS_PROFILE=new-frontiers         # the only AWS profile this project may use
export AWS_REGION=ap-southeast-2
export AWS_DEFAULT_REGION=$AWS_REGION

APP=english-tutor
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET=$APP-tts-$ACCOUNT_ID
INSTANCE_TYPE=t3.small                   # 2 vCPU / 2 GB (+2 GB swap): Kokoro TTS + FastAPI
KEY_NAME=$APP
KEY_FILE=$HOME/.ssh/$APP.pem
APP_DIR=/opt/$APP
REPO=https://github.com/luandang4/english-tutor.git

instance_id() {
  aws ec2 describe-instances --filters "Name=tag:Name,Values=$APP" "Name=instance-state-name,Values=pending,running,stopped" \
    --query 'Reservations[0].Instances[0].InstanceId' --output text
}
public_ip() {
  aws ec2 describe-addresses --filters "Name=tag:Name,Values=$APP" --query 'Addresses[0].PublicIp' --output text
}
