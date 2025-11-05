# HƯỚNG DẪN TRIỂN KHAI HỆ THỐNG CLOUDIFYSHARE TRÊN AWS
## BƯỚC 1: Tạo VPC & Subnet
- Vào AWS Console → VPC → Create VPC
- Chọn kiểu: VPC and more
Mục                 	            Giá trị
Name	                            cloudify-vpc
IPv4 CIDR	                        10.0.0.0/16
Tenancy	                            Default
IPv6 CIDR	                        No IPv6 CIDR block
Number of Availability Zones (AZs)	2
Number of public subnets	        2
Number of private subnets	        2
NAT gateways	                    1 per AZ
VPC endpoints	                    None
DNS options	                        Enable DNS hostnames, Enable DNS resolution

AWS sẽ tạo sẵn:
2 public subnet (dùng cho Load Balancer, NAT Gateway)
2 private subnet (dùng cho EC2 Flask App, RDS)
1 Internet Gateway (IGW)
1 NAT Gateway (đặt trong public subnet)

## BƯỚC 2: Tạo Security Groups
Tạo 4 Security Group:
    Tên	        Mục đích
    sg-lb	    Cho Load Balancer (HTTP/HTTPS)
    sg-ec2	    Cho Flask EC2 App
    sg-rds	    Cho MySQL RDS
    sg-bastion	Cho phép SSH từ máy cá nhân

### SG #1: Load Balancer
Mục đích: Cho phép người dùng ngoài Internet truy cập vào Flask qua cổng 80/443

- Vào EC2 Console → Security Groups → Create Security Group
    Thuộc tính	        Giá trị
    Name	            sg-lb
    Description	        Allow HTTP/HTTPS from Internet
    VPC	                cloudify-vpc
- Inbound rules:
    Type	            Protocol	Port	    Source	        Mô tả
    HTTP	            TCP	        80	        0.0.0.0/0	    Cho phép tất cả truy cập web
    HTTPS	            TCP	        443	        0.0.0.0/0	    Cho phép HTTPS
    All ICMP - IPv4	    ICMP	    -	        0.0.0.0/0	    Cho phép ping

Outbound: Giữ mặc định (All traffic)
Mục tiêu: User → Load Balancer qua port 80/443.

### SG #2: EC2 Flask App
Mục đích: Cho phép Load Balancer truy cập vào Flask app (port 80), và bạn có thể SSH (22) khi cần.
Tạo Security Group mới:
    Thuộc tính	        Giá trị
    Name	            sg-ec2
    Description	        Allow HTTP from Load Balancer + SSH from Bastion
    VPC	                cloudify-vpc
- Inbound rules:
    Type	        Protocol	Port	Source	        Mô tả
    HTTP	        TCP	        80	    sg-lb	        Cho phép LB truy cập Flask
    SSH	            TCP	        22	    sg-bastion  	Chỉ Bastion host được SSH
    All ICMP-IPv4	ICMP	    -	    0.0.0.0/0	    Cho phép ping nội bộ
- Outbound: để mặc định (All traffic)
Mục tiêu: Load Balancer → EC2, bạn vẫn có thể SSH kiểm tra app.

### SG #3: RDS MySQL
Cho phép EC2 Flask truy cập cơ sở dữ liệu MySQL (port 3306).
Tạo Security Group mới:
    Thuộc tính      	Giá trị
    Name	            sg-rds
    Description	        Allow MySQL from Flask EC2 only
    VPC	                cloudify-vpc
- Inbound rules:
    Type	        Protocol	Port	Source	    Mô tả
    MySQL/Aurora	TCP	        3306	sg-ec2	    Chỉ EC2 Flask được phép kết nối DB

- Outbound: Giữ mặc định (All traffic)
Mục tiêu: EC2 Flask → RDS qua port 3306, không ai khác vào được.

### SG #4: Bastion Host (sg-bastion)
    Thuộc tính	        Giá trị
    Name	            sg-bastion
    Description	        Allow SSH from admin
    VPC	                cloudify-vpc
Inbound rules:
    Type	        Protocol	Port	Source	                            Mô tả
    SSH	            TCP	        22	    IP của bạn (ví dụ 113.x.x.x/32)	    Cho phép máy cá nhân SSH vào Bastion
    All ICMP-IPv4	ICMP	    -	    0.0.0.0/0	                        Cho phép ping
Outbound: Giữ mặc định (All traffic)


### Kiểm tra lại sau khi tạo xong:
SG Name	Cho phép vào từ	Port	Dùng cho
sg-lb	Internet (0.0.0.0/0)	80, 443	Load Balancer
sg-ec2	sg-lb, IP của bạn	80, 22	EC2 Flask
sg-rds	sg-ec2	3306	RDS MySQL


## BƯỚC 3: Tạo EC2 Template (Flask App)
#### Bước 1 — Mở Launch Template
- EC2 → Launch Template → Create Launch Template
BƯỚC 3: Tạo EC2 Launch Template (Flask App)
    Mục	                            Giá trị
    Name	                        flask-template
    Description	                    Template for Flask EC2 instances
    Auto Scaling guidance	        Enabled

Cấu hình:
    Quick Start
    AMI: Ubuntu Server 24.04 LTS (Free tier eligible)
    Instance type: t2.micro
    Key pair: cloudify-key.pem (tạo mới nếu chưa có)
    Network: Không chọn subnet
    Auto-assign public IP: Disable (vì ở private subnet)
    Availability Zone: Để trống	Auto chọn
    Security group: sg-ec2
    Volume: 8 GiB gp3
    Tag: Project=CloudifyShare

#### Bước 6 - Advanced network configuration
- Subnet: Remove subnet (nếu còn hiện dòng đỏ)	Không được chọn subnet cho Auto Scaling
- Security groups: sg-ec2-flask
- Auto-assign public IP: Disable	Vì EC2 Flask nằm trong private subnet, không có IP public
Các phần khác (Primary IP, IPv6, Prefixes, Description, …)	Để mặc định (Don't include)	Không cần chỉnh

#### Bước 8 — Advanced details → User data (rất quan trọng)
Trong ô User data, dán đoạn script sau để EC2 tự cài app Flask khi khởi động:

```
#!/bin/bash
# Cập nhật và cài đặt môi trường cần thiết
sudo apt update -y
sudo apt install -y python3 python3-pip git

# Clone project Flask từ GitHub (nhánh main)
cd /home/ubuntu
if [ ! -d "CloudifyShare" ]; then
  git clone -b main https://github.com/nhatduydo/CloudifyShare.git
fi
cd CloudifyShare

# Cài đặt các thư viện Python
pip install -r requirements.txt

# Thêm lệnh auto chạy Flask vào crontab khi máy khởi động lại
croncmd="@reboot cd /home/ubuntu/CloudifyShare && nohup python3 run.py > /home/ubuntu/app.log 2>&1 &"
(crontab -l 2>/dev/null | grep -F "$croncmd") || (crontab -l 2>/dev/null; echo "$croncmd") | crontab -

# Chạy Flask lần đầu tiên khi instance được tạo
nohup python3 run.py --host=0.0.0.0 --port=80 > /home/ubuntu/app.log 2>&1 &
```
```
EC2 cài Python, pip, git
Clone repo CloudifyShare (nhánh main)
Cài thư viện Flask
Tự động thêm crontab để Flask chạy lại sau mỗi lần reboot
Chạy Flask ngay lần đầu EC2 khởi động
```
### Bước 8 — Review & Create
Nhấn Create launch template
→ AWS sẽ tạo mẫu máy chủ EC2 Flask của bạn.

### Sau khi tạo xong:
Bạn có thể kiểm tra bằng cách:
- Vào EC2 → Launch Template → flask-template → Launch instance from template
- Chạy thử 1 máy để kiểm tra:
    Khi khởi động xong → SSH vào máy
Dùng lệnh:
    ps aux | grep python
Nếu thấy python3 run.py đang chạy → script hoạt động tốt 


## BƯỚC 4: Tạo Auto Scaling Group
- EC2 → Auto Scaling Groups → Create
- Name: asg-flask
- Launch template: flask-template
- Version: default(1)
- VPC: cloudify-vpc
- Availability Zones and subnets: private1 và private2
- Balanced best effort

#### Integrate with other services - optional - Load balancing 
- Select Load balancing options: Attach to a new load balancer
- Load balancer type: Application Load Balancer (ALB)
- Load balancer name: asg-flask-lb
- Load balancer scheme: Internet-facing
- Availability Zones and subnets: Chọn 2 public subnets
- Listeners and routing: Protocol: HTTP - Port: 80
- Default routing (target group): Create a target group

#### Health Checks:
EC2 health checks: Enabled
ELB health checks: Enabled
Health check grace period: 300 giây

#### VPC Lattice integration options
- Select VPC Lattice service to attach: No VPC Lattice service
- Application Recovery Controller (ARC) zonal shift: không tick
Health checks
- EC2 health checks: Always enabled
- Turn on Elastic Load Balancing health checks: Bật
- Turn on Amazon EBS health checks: Không bật
- Health check grace period: 300

#### Tag (optional)
Key: Project
Value: CloudifyShare

### CONFIGURE GROUP SIZE AND SCALING
- Desired capacity: 2
- Minimum capacity: 1
- Maximum capacity: 3
- Choose whether to use a target tracking policy: Target tracking scaling policy
- Metric type: Average CPU utilization
- Target value: 60
Instance maintenance policy
- chọn: Launch before terminating
- Capacity Reservation preference: Default
- Enable instance scale-in protection: Không bật
- Enable group metrics collection within CloudWatch: Bật
- Enable default instance warmu:p Bật, 180 seconds

- Add tags: Project = CloudifyShare
==> Create Auto Scaling group

### kiểm tra hoạt động thực tế của hệ thống
- AWS Console → EC2 → Load Balancers
- Chọn Application Load Balancer bạn đã tạo
- Chuyển sang tab “instance management” bạn sẽ thấy dòng: 
    Kiểm tra Status = running và Health = healthy.

## BƯỚC 5: Tạo Application Load Balancer (ALB)
- EC2 → Load Balancer → Create
- Load balancer name: cloudify-lb
- Scheme: chọn Internet-facing → vì bạn muốn người dùng ngoài Internet có thể truy cập được Flask app.
- IP address type: chọn IPv4
- VPC: chọn cloudify-vpc
- Mappings: chọn 2 public subnet khác vùng (Availability Zone)
- Chọn security group dành riêng cho Load Balancer: sg-lb.
- Listener protocol: HTTP
- Port: 80
- Default action: Forward to → nhấn Create target group

#### Tạo Target Group
Sau khi nhấn “Create target group”, mở ra tab mới:
- Choose a target type: Instance
- Target group name: tg-flask
- Protocol: HTTP
- Port: 80
- VPC: chọn cloudify-vpc
- Health check:
- Protocol: HTTP
- Path: /
- Giữ nguyên các giá trị mặc định khác.
    Nhấn Next, bỏ qua bước “Register targets”
    Nhấn Create target group.

3 Quay lại ALB → chọn target group tg-flask
→ add vào Auto Scaling Group.
## BƯỚC 6: Tạo Bastion Host (để SSH vào EC2 Private)
Mục đích: Các EC2 Flask nằm trong private subnet không có public IP, nên không thể SSH trực tiếp. Bastion Host nằm ở public subnet để làm cầu SSH trung gian.
Thực hiện:
    EC2 → Launch Instance
    Name: bastion-host
    AMI: Ubuntu Server 24.04 LTS
    Instance type: t2.micro
    Key pair: cloudify-key.pem (dùng chung với EC2 Flask)
    Network:
        Subnet: Public Subnet 1
        Auto-assign Public IP: Enable
    Security group: sg-bastion  
    Launch instance

## BƯỚC 7: Kết nối SSH hai lớp
Bước 1: Từ máy cá nhân vào Bastion Host
    ssh -i "cloudify-key.pem" ubuntu@<bastion_public_ip>
Bước 2: Từ Bastion vào EC2 Flask trong Private Subnet
    ssh ubuntu@<private_ip_of_flask_instance>
    Private IP có thể xem trong EC2 Console → Instances → Private IPv4 address.
    Nếu truy cập được nghĩa là cấu hình Bastion hoạt động đúng.
Kiểm tra hoạt động hệ thống
    EC2 → Load Balancers → chọn cloudify-lb.
    Vào tab Instance management → kiểm tra Status = Running và Health = Healthy.
    Sao chép DNS name của Load Balancer, truy cập thử trên trình duyệt: 
        http://<dns_name_alb>
        
#### Kiểm tra Load Balancer
Sau khi tạo xong:
    - Vào EC2 → Load Balancers → cloudify-lb
    - Kiểm tra trạng thái: Active
    - Sao chép DNS name
#### Gắn ALB vào Auto Scaling Group
- Vào EC2 → Auto Scaling Groups → chọn nhóm asg-flask
- chọn Integrations => Load balancing => edit
- Tích chọn Attach to an existing load balancer
- Chọn loại: Application Load Balancer or Network Load Balancer
- Ở danh sách Load balancer, chọn cloudify-lb
- Nhấn Update.
- Quay lại tab Integrations → kiểm tra xem mục “Load balancing” hiển thị:
    Application Load Balancer: Auto-Scaling-group-flask-LB


- Vì bạn không thể chọn được Auto-Scaling-group-flask-LB, nên hãy:
- Vào EC2 → Auto Scaling Groups → Auto-Scaling-group-flask → tab Integrations → Edit Load balancing.
- Bỏ chọn Auto-Scaling-group-flask-LB.
- Thay vào đó, chọn tg-flask.
- Nhấn Update.
BƯỚC 6: Tạo RDS MySQL (ở AWS Thật)

Đăng nhập vào tài khoản AWS thật (không phải AWS Academy).

Vào RDS → Create Database

Chọn Standard create

Engine options

Engine type: MySQL

Version: MySQL 8.0.35

Edition: MySQL Community Edition

Templates

Chọn Free Tier hoặc Production (tuỳ tài khoản).

Availability and durability

Deployment: Single-AZ (hoặc Multi-AZ nếu muốn redundancy).

Settings

DB identifier: cloudsharedb

Master username: admin

Master password: Admin123!

Instance configuration

DB instance class: db.t3.micro

Storage: General Purpose SSD (gp2), 20 GB

Disable autoscaling (để tránh phát sinh chi phí).

Connectivity

VPC: chọn VPC ở AWS thật (không trùng với VPC trong AWS Academy).

Public access: Yes (Publicly accessible) để cho phép EC2 trong AWS Academy truy cập qua Internet.

Security group: tạo mới hoặc chọn SG mở port 3306 cho IP công khai của EC2/ALB AWS Academy.

Ví dụ inbound rule SG của RDS:

Type	Protocol	Port	Source
MySQL/Aurora	TCP	3306	0.0.0.0/0 (hoặc IP cụ thể của Academy)

Database authentication

Password authentication

Monitoring, backup: để mặc định hoặc tắt Performance Insights để tiết kiệm.

Additional configuration

Initial database name: cloudsharedb

Sau khi tạo xong, copy Endpoint RDS, ví dụ:

cloudsharedb.xxxxxx.us-east-1.rds.amazonaws.com


Cấu hình trong Flask (bên AWS Academy):

DB_HOST=cloudsharedb.xxxxxx.us-east-1.rds.amazonaws.com
DB_USER=admin
DB_PASS=Admin123!
DB_NAME=cloudsharedb


Kết nối này hoạt động bình thường vì RDS thật có IP public và EC2 (Academy) có outbound Internet thông qua NAT Gateway.

BƯỚC 7: Tạo S3 Buckets (ở AWS Thật)

Đăng nhập tài khoản AWS thật.

Vào S3 → Create bucket

Tạo bucket chính:

Name: cloudifyshare-main-bucket

Region: us-east-1

Block all public access: Bật

Enable versioning: Bật

Tạo bucket phụ (backup):

Name: cloudifyshare-backup-bucket

Region: us-west-1

Trong bucket chính → tab Management → Replication Rules → Create Rule

Source bucket: cloudifyshare-main-bucket

Destination bucket: cloudifyshare-backup-bucket

IAM Role: tạo role cho phép replicate.

Copy thông tin cấu hình để kết nối từ Flask:

S3_MAIN_BUCKET=cloudifyshare-main-bucket
S3_BACKUP_BUCKET=cloudifyshare-backup-bucket
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=<AccessKey của tài khoản thật>
AWS_SECRET_ACCESS_KEY=<SecretKey của tài khoản thật>


Trong Flask code, upload file chỉ cần gọi tới S3_MAIN_BUCKET, AWS sẽ tự sao chép sang bucket backup nhờ replication.

BƯỚC 8: Cấu hình kết nối giữa AWS Academy và AWS thật
1. Kiểm tra outbound Internet của EC2 trong AWS Academy

EC2 trong private subnet sử dụng NAT Gateway để ra ngoài.

Vào EC2 → chạy lệnh kiểm tra:

ping cloudsharedb.xxxxxx.us-east-1.rds.amazonaws.com


hoặc

curl https://s3.amazonaws.com


Nếu có phản hồi → NAT hoạt động đúng, EC2 Academy có thể kết nối RDS và S3 thật.

2. Kiểm tra port MySQL

Dùng lệnh:

nc -zv cloudsharedb.xxxxxx.us-east-1.rds.amazonaws.com 3306


Nếu thấy succeeded → kết nối RDS thành công.

3. Kiểm tra upload S3

Trong Flask:

import boto3
s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)
s3.upload_file("test.txt", os.getenv('S3_MAIN_BUCKET'), "test.txt")


Sau đó kiểm tra trên AWS thật → file có trong cả hai bucket.

BƯỚC 9: Thiết lập CloudWatch Monitoring (AWS Academy)

CloudWatch → Alarms → Create alarm

Metric: EC2 → CPUUtilization

Condition: >70% trong 5 phút

Action: Scale out Auto Scaling Group

Tạo thêm một alarm ngược lại:

Condition: <30%

Action: Scale in

BƯỚC 10: Thiết lập AWS Backup (AWS Academy)

AWS Backup → Create Backup Plan

Plan name: cloudify-backup-plan

Frequency: Daily

Retention: 30 days

Assign resources:

RDS (nếu muốn backup định kỳ cấu hình DB)

S3 bucket (metadata backup)

IAM role: AWSBackupDefaultServiceRole

BƯỚC 11: Route 53 + Domain (AWS Academy hoặc thật đều được)

Route 53 → Hosted Zones → Create

Domain: cloudifyshare.website

Add record:

Name: app.cloudifyshare.website

Type: A

Alias: trỏ đến Load Balancer DNS

Khi truy cập https://app.cloudifyshare.website → Flask app chạy qua Load Balancer → EC2 → kết nối RDS và S3 thật.

KẾT QUẢ TỔNG THỂ
Thành phần	Nơi triển khai	Vai trò
VPC, EC2, ALB, Auto Scaling, Bastion, CloudWatch, Backup	AWS Academy	Compute và điều phối ứng dụng
RDS MySQL	AWS thật	Lưu trữ dữ liệu chính, có IP public
S3 (2 buckets, replication)	AWS thật	Lưu trữ file và sao lưu tự động