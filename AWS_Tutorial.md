## BƯỚC 1: Tạo VPC & Subnet
- Vào AWS Console → VPC → Create VPC
- Chọn kiểu “VPC and more”
- Name: cloudify-vpc
- IPv4 CIDR: 10.0.0.0/16
- Chọn: No IPv6 CIDR block
- NAT gateways: 1 per AZ
- Tenancy: Default
- Number of Availability Zones (AZs): 2
- Number of public subnets: 2
- Number of private subnets: 2
- NAT gateways : 1 per AZ 
- VPC endpoints: None
- DNS options Bật cả 2:
    + Enable DNS hostnames
    + Enable DNS resolution
AWS sẽ tạo sẵn:
2 public subnet (dùng cho Load Balancer, NAT Gateway)
2 private subnet (dùng cho EC2, RDS)
1 Internet Gateway (IGW)
1 NAT Gateway (đặt trong public subnet)


## BƯỚC 2: Tạo Security Groups
Tạo 3 nhóm bảo mật:
    - sg-lb → cho Load Balancer
    - sg-ec2 → cho EC2 Flask App
    - sg-rds → cho MySQL RDS

### SG #1: Load Balancer
Mục đích: Cho phép người dùng ngoài Internet truy cập vào Flask qua cổng 80/443

- Vào EC2 Console → Security Groups → Create Security Group
Mục	Giá trị
- Name	sg-lb
- Description	Allow HTTP/HTTPS from Internet
- VPC	chọn cloudify-vpc
- Inbound rules:
    Type	Protocol	Port	Source	Mô tả
    HTTP	TCP	80	0.0.0.0/0	Cho phép tất cả truy cập web
    HTTPS	TCP	443	0.0.0.0/0	Nếu có SSL sau này
    All ICMP - IPv4 TCP 0.0.0.0/0

Outbound: để mặc định (All traffic)
Mục tiêu: User → Load Balancer qua port 80/443.

### SG #2: EC2 Flask App
Mục đích: Cho phép Load Balancer truy cập vào Flask app (port 80), và bạn có thể SSH (22) khi cần.

Tạo Security Group mới:

- Name	sg-ec2
- Description	Allow HTTP from Load Balancer + SSH for admin
- VPC	cloudify-vpc
- Inbound rules:
    Type	Protocol	Port	Source	Mô tả
    HTTP	TCP	80	sg-lb	Chỉ cho Load Balancer truy cập
    SSH	TCP	22	IP cá nhân của bạn (ví dụ 113.x.x.x/32)	Truy cập qua terminal riêng
    All ICMP - IPv4 TCP 0.0.0.0/0

- Outbound: để mặc định (All traffic)
Mục tiêu: Load Balancer → EC2, bạn vẫn có thể SSH kiểm tra app.

### SG #3: RDS MySQL
Cho phép EC2 Flask truy cập cơ sở dữ liệu MySQL (port 3306).
Tạo Security Group mới:

Mục	Giá trị
- Name	sg-rds
- Description	Allow MySQL from Flask EC2 only
- VPC	cloudify-vpc
- Inbound rules:
    Type	Protocol	Port	Source	Mô tả
    MySQL/Aurora	TCP	3306	sg-ec2	Chỉ EC2 Flask được phép kết nối DB

- Outbound: để mặc định (All traffic)
Mục tiêu: EC2 Flask → RDS qua port 3306, không ai khác vào được.

### Kiểm tra lại sau khi tạo xong:
SG Name	Cho phép vào từ	Port	Dùng cho
sg-lb	Internet (0.0.0.0/0)	80, 443	Load Balancer
sg-ec2	sg-lb, IP của bạn	80, 22	EC2 Flask
sg-rds	sg-ec2	3306	RDS MySQL


## BƯỚC 3: Tạo EC2 Template (Flask App)
#### Bước 1 — Mở Launch Template
- EC2 → Launch Template → Create Launch Template
- Mục	Giá trị
    Launch template name	flask-template
    Description	Template for Flask EC2 instances
    Auto Scaling guidance	Bật (tích chọn)

#### Bước 2 — Chọn AMI (hệ điều hành)
- Application and OS Images (Amazon Machine Image)
    → Nhấn “Quick Start”
    → Chọn: Ubuntu Server 24.04 LTS (Free tier eligible)
#### Bước 3 — Chọn Instance type
- Chọn loại nhỏ (Free Tier): t2.micro

#### Bước 4 — Key pair (login)
- Nếu chưa có, nhấn Create new key pair
    Tên: cloudify-key
    Type: RSA
    File format: .pem
- Tải file .pem về, giữ lại để sau này SSH.
#### Bước 5 — Network settings
- Subnet: Không chọn (bỏ trống)	Vì Launch Template không cố định subnet — Auto Scaling sẽ chọn sau
- Availability Zone: Để trống	Auto chọn
- Security group: sg-ec2-flask	Đây là tường lửa EC2 Flask, chỉ LB truy cập được
#### Bước 6 - Advanced network configuration
- Subnet: Remove subnet (nếu còn hiện dòng đỏ)	Không được chọn subnet cho Auto Scaling
- Security groups: sg-ec2-flask
- Auto-assign public IP: Disable	Vì EC2 Flask nằm trong private subnet, không có IP public
Các phần khác (Primary IP, IPv6, Prefixes, Description, …)	Để mặc định (Don't include)	Không cần chỉnh

#### Bước 7 — Storage (EBS volume)
- Giữ mặc định:
    Volume size: 8 GiB
    Volume type: gp3

- Resource tags
Add new tag	Key: Project, Value: CloudifyShare	Giúp quản lý tài nguyên dễ hơn

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

### BƯỚC 6: Tạo RDS MySQL (Multi-AZ)

AWS RDS → Create Database

Engine: MySQL

Template: Free Tier

DB name: cloudsharedb

Master username: admin

Password: password

Multi-AZ: 

Public access: 

VPC: cloudify-vpc

Subnet group: Private subnet

Security Group: sg-rds

Sau khi tạo xong, copy Endpoint:

cloudsharedb.abc123.us-east-1.rds.amazonaws.com


Cấu hình trong Flask .env:

DB_HOST=cloudsharedb.abc123.us-east-1.rds.amazonaws.com
DB_USER=admin
DB_PASS=your_password
DB_NAME=cloudsharedb

BƯỚC 7: Tạo S3 Buckets

 S3 → Create Bucket →

Name: cloudifyshare-main-bucket

Region: us-east-1

Block all public access: 

Enable versioning 

2Tạo thêm bucket backup:

Name: cloudifyshare-backup-bucket

Region: us-west-1

3Trong bucket chính → Replication Rule:

Source: cloudifyshare-main-bucket

Destination: cloudifyshare-backup-bucket

IAM Role: cho phép replicate

Flask app chỉ cần upload vào main bucket, AWS tự copy sang backup.

BƯỚC 8: Thiết lập CloudWatch Monitoring

CloudWatch → Alarms → Create alarm

Metric: EC2 → CPUUtilization

Condition: > 70% trong 5 phút

Action: Scale out Auto Scaling Group
 Tạo thêm Alarm ngược lại:

Condition: < 30%

Action: Scale in

BƯỚC 9: Thiết lập AWS Backup
 AWS Backup → Create Backup Plan

Plan name: cloudify-backup-plan

Frequency: Daily

Retention: 30 days
 Assign resources:

RDS database

S3 bucket

IAM role: AWSBackupDefaultServiceRole

BƯỚC 10: Route 53 + Domain (DNS)

Route 53 → Hosted Zones → Create

Domain: cloudifyshare.website

Add record:

Name: app.cloudifyshare.website

Type: A

Alias → chọn Load Balancer DNS

Khi truy cập https://app.cloudifyshare.website → Flask app chạy qua Load Balancer.


KẾT QUẢ
Thành phần	Vai trò	Tình trạng
VPC	Mạng riêng gồm public/private subnet	
EC2 + ASG	Flask app tự mở rộng	
Load Balancer	Cân bằng tải request	
RDS MySQL Multi-AZ	DB an toàn, tự failover	
S3 + Backup	Lưu trữ và nhân bản tự động	
CloudWatch + AWS Backup	Giám sát + sao lưu	