param (
    [Parameter(Mandatory = $true)]
    [string]$KeyFile,

    [Parameter(Mandatory = $true)]
    [string]$EC2IP
)

$ErrorActionPreference = "Stop"

Write-Host "Deploying to EC2 instance: $EC2IP"

# Copy files to EC2
Write-Host "Copying files..."
scp -i $KeyFile api_server.py ec2-user@$EC2IP:~
scp -i $KeyFile requirements.txt ec2-user@$EC2IP:~

# Run remote commands via SSH
Write-Host "Installing dependencies and starting server..."
$remoteCommands = @"
set -e
if command -v yum >/dev/null 2>&1; then
  sudo yum install -y python3 python3-pip
elif command -v apt >/dev/null 2>&1; then
  sudo apt update && sudo apt install -y python3 python3-pip
fi

pip3 install --user -r requirements.txt

pgrep -f "api_server.py" && pkill -f "api_server.py" || true

export TABLE_NAME=arxiv-papers
# export AWS_REGION=us-west-2

nohup python3 api_server.py 8080 > server.log 2>&1 &
echo "Server started. Check locally on EC2:"
echo "curl http://localhost:8080/papers/recent?category=cs.LG&limit=5"
"@

ssh -i $KeyFile ec2-user@$EC2IP $remoteCommands

Write-Host "`nDeployment complete!"
Write-Host "Test from local machine:"
Write-Host "curl `"http://$EC2IP:8080/papers/recent?category=cs.LG&limit=5`""
