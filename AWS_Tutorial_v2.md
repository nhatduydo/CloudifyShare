# 1. Mục tiêu tổng quát
Hệ thống CloudifyShare được triển khai trên kiến trúc AWS theo mô hình High Availability (HA), bao gồm các thành phần chính:
- VPC có 2 Availability Zones (AZ), chia thành các subnet public và private.
- Application Load Balancer (ALB) phân phối yêu cầu đến các EC2 Flask App nằm trong Auto Scaling Group.
- RDS MySQL hoạt động ở chế độ Multi-AZ (Primary và Replica).
- MinIO được sử dụng để thay thế AWS S3, lưu trữ file người dùng.
- Firebase đảm nhiệm chức năng nhắn tin và thông báo thời gian thực.
- Bastion Host được triển khai ở public subnet để SSH vào các EC2 trong private subnet.
- CloudWatch giám sát tài nguyên và AWS Backup sao lưu dữ liệu định kỳ.

# 2. Tạo VPC và Subnet

Truy cập AWS Console → VPC → Create VPC.
Chọn kiểu "VPC and more" và cấu hình như sau:

Name: cloudify-vpc

IPv4 CIDR: 10.0.0.0/16

Tenancy: Default

Availability Zones: 2

Number of public subnets: 2

Number of private subnets: 2

NAT Gateway: 1 per AZ

DNS hostnames: Enable

DNS resolution: Enable

Sau khi tạo, hệ thống sẽ có:

2 public subnet (chứa ALB, NAT Gateway và Bastion Host).

2 private subnet (chứa EC2 Flask App, RDS, MinIO).

1 Internet Gateway (IGW).

2 NAT Gateway (mỗi AZ một NAT).

3. Tạo Security Groups

Tạo 4 nhóm bảo mật chính:

sg-lb: Cho Load Balancer (HTTP/HTTPS từ Internet).

sg-ec2: Cho EC2 Flask App.

sg-rds: Cho RDS MySQL.

sg-bastion: Cho phép SSH từ máy quản trị.

3.1 sg-lb (Load Balancer)

Mục đích: cho phép người dùng ngoài Internet truy cập vào hệ thống qua HTTP/HTTPS.

Inbound rules:

HTTP – TCP – Port 80 – Source 0.0.0.0/0

HTTPS – TCP – Port 443 – Source 0.0.0.0/0

ICMP – Allow all

Outbound rules: giữ mặc định (All traffic).

Luồng: Người dùng → Route 53 → ALB qua port 80/443.

3.2 sg-ec2 (Flask App)

Mục đích: cho phép ALB truy cập Flask app và Bastion SSH vào.

Inbound rules:

HTTP – TCP – Port 80 – Source sg-lb

SSH – TCP – Port 22 – Source sg-bastion

ICMP – Allow all

Outbound rules: giữ mặc định (All traffic).
Luồng: ALB → EC2 Flask App.
Flask chỉ nhận truy cập từ ALB và SSH từ Bastion.

3.3 sg-rds (RDS MySQL)

Mục đích: chỉ cho EC2 Flask được phép kết nối cơ sở dữ liệu.

Inbound rules:

MySQL/Aurora – TCP – Port 3306 – Source sg-ec2

Outbound rules: giữ mặc định.
Luồng: EC2 Flask → RDS MySQL (port 3306).

3.4 sg-bastion (Bastion Host)

Mục đích: cho phép máy quản trị SSH vào hệ thống.

Inbound rules:

SSH – TCP – Port 22 – Source IP cá nhân (ví dụ 113.x.x.x/32)

ICMP – Allow all

Outbound rules: giữ mặc định.
Luồng: Máy quản trị → Bastion (Public IP) → EC2 Flask (Private IP).

4. Tạo EC2 Flask App (Launch Template)

Truy cập EC2 → Launch Templates → Create Launch Template.

Cấu hình:

Name: flask-template

AMI: Ubuntu Server 22.04 LTS

Instance type: t2.micro

Key pair: cloudify-key.pem

Network: không chọn subnet

Auto-assign public IP: Disable

Security group: sg-ec2

Storage: 8 GB gp3

Tag: Project=CloudifyShare

Trong phần “User data”, thêm script khởi tạo Flask tự động:
```
#!/bin/bash
set -e
apt update -y
apt install -y python3 python3-pip git

cd /home/ubuntu
if [ ! -d "CloudifyShare" ]; then
  git clone -b main https://github.com/nhatduydo/CloudifyShare.git
fi
cd CloudifyShare
pip install -r requirements.txt

LOGFILE="/home/ubuntu/app.log"
touch $LOGFILE
chmod 666 $LOGFILE

pkill -f "python3 run.py" || true
nohup python3 run.py --host=0.0.0.0 --port=80 > $LOGFILE 2>&1 &

```
5. Tạo Auto Scaling Group

EC2 → Auto Scaling Groups → Create.

Name: asg-flask

Launch template: flask-template

VPC: cloudify-vpc

Subnets: 2 private subnet

Load Balancer: Application Load Balancer (cloudify-lb)

Health check: ELB + EC2

Desired capacity: 2

Min: 1

Max: 3

Scaling policy: Target tracking – 60% CPU

CloudWatch sẽ theo dõi CPU để tự động scale in/out.

6. Tạo Bastion Host

EC2 → Launch Instance.

Name: bastion-host

AMI: Ubuntu 22.04 LTS

Instance type: t2.micro

Key pair: cloudify-key.pem

Subnet: Public subnet

Auto-assign public IP: Enable

Security group: sg-bastion

Kiểm tra route table của public subnet:
0.0.0.0/0 → Internet Gateway.

Kết nối SSH hai lớp:

Bước 1: SSH vào Bastion
```
ssh -i "cloudify-key.pem" ubuntu@<bastion_public_ip>
```
Bước 2: Từ Bastion SSH vào EC2 Flask (Private Subnet)
```
ssh -i "cloudify-key.pem" ubuntu@<private_ip_of_ec2_flask>
```
7. Tạo RDS MySQL (trong AWS Academy)

RDS → Create Database → Standard create.

Thuộc tính	Giá trị
Engine	MySQL 8.0
DB identifier	cloudsharedb
Master username	admin
Password	Admin123!
Multi-AZ	Enabled
Public access	No
VPC	cloudify-vpc
Subnet group	Private subnet
Security group	sg-rds

Flask cấu hình (.env):
```
DB_HOST=<endpoint của RDS nội bộ>
DB_USER=admin
DB_PASS=Admin123!
DB_NAME=cloudsharedb
```
8. Cấu hình MinIO (thay thế S3)

Cài đặt MinIO trong private subnet (hoặc EC2 riêng).

```
#!/bin/bash
set -e

# Update hệ thống và cài công cụ cần thiết
apt update -y
apt install -y wget curl ufw

# Cài MinIO server
wget https://dl.min.io/server/minio/release/linux-amd64/minio -O /usr/local/bin/minio
chmod +x /usr/local/bin/minio

# Tạo thư mục lưu dữ liệu
mkdir -p /data
chown ubuntu:ubuntu /data

# Thông tin cấu hình
MINIO_USER="admin"
MINIO_PASS="admin123"
BUCKET_MAIN="cloudifyshare-bucket"
BUCKET_BACKUP="cloudifyshare-backup"

echo "MINIO_ROOT_USER=${MINIO_USER}" >> /etc/environment
echo "MINIO_ROOT_PASSWORD=${MINIO_PASS}" >> /etc/environment
export MINIO_ROOT_USER=${MINIO_USER}
export MINIO_ROOT_PASSWORD=${MINIO_PASS}

# Tạo service cho MinIO
cat <<EOF > /etc/systemd/system/minio.service
[Unit]
Description=MinIO Object Storage
After=network.target

[Service]
User=ubuntu
Group=ubuntu
Environment="MINIO_ROOT_USER=${MINIO_USER}"
Environment="MINIO_ROOT_PASSWORD=${MINIO_PASS}"
ExecStart=/usr/local/bin/minio server /data --address "0.0.0.0:9000" --console-address "0.0.0.0:9001"
Restart=always
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

# Mở port cơ bản
ufw allow 22/tcp
ufw allow 9000/tcp
ufw allow 9001/tcp
ufw --force enable

# Khởi động dịch vụ MinIO
systemctl daemon-reload
systemctl enable minio
systemctl start minio

# Cài MinIO Client (mc)
wget https://dl.min.io/client/mc/release/linux-amd64/mc -O /usr/local/bin/mc
chmod +x /usr/local/bin/mc

# Chờ MinIO chạy ổn định
sleep 10

# Kết nối client tới MinIO nội bộ
mc alias set local http://127.0.0.1:9000 ${MINIO_USER} ${MINIO_PASS}

# Tạo 2 bucket nếu chưa có
mc mb local/${BUCKET_MAIN} || true
mc mb local/${BUCKET_BACKUP} || true

# Đặt quyền private
mc anonymous set private local/${BUCKET_MAIN}
mc anonymous set private local/${BUCKET_BACKUP}
```


Lệnh cài đặt:
```
docker run -d -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=admin \
  -e MINIO_ROOT_PASSWORD=Admin123! \
  -v /data/minio:/data \
  minio/minio server /data --console-address ":9001"

```
File .env của Flask:
```
MINIO_ENDPOINT=http://10.0.1.25:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=Admin123!
MINIO_BUCKET_NAME=cloudifyshare-main
```
Nếu có thêm MinIO backup ở AZ khác:
```
MINIO_BACKUP_ENDPOINT=http://10.0.2.25:9000
```
9. Firebase Realtime Messaging

Firebase dùng cho chat và thông báo realtime.

File .env:
```
FIREBASE_URL=https://cloudifyshare.firebaseio.com
```
10. CloudWatch Monitoring và AWS Backup

CloudWatch:

Theo dõi CPU, RAM, Network của EC2 Flask App.

Tạo alarm khi CPU > 70% để scale out, < 30% để scale in.

AWS Backup:

Tạo Backup Plan: cloudify-backup-plan

Chọn tài nguyên: RDS, EC2

Frequency: Daily

Retention: 30 days

11. Route 53 và Domain

Route 53 → Hosted Zones → Create Zone
Domain: cloudifyshare.website

Thêm record:

Name: app.cloudifyshare.website

Type: A (Alias)

Target: DNS của ALB

Truy cập: http://app.cloudifyshare.website

Luồng truy cập:
User → Route 53 → Internet Gateway → ALB → EC2 Flask (Private Subnet) → RDS MySQL → MinIO Storage.

12. Kết quả tổng thể
Thành phần	Nơi triển khai	Vai trò
VPC, EC2, ALB, Auto Scaling, Bastion, CloudWatch, Backup	AWS Academy	Toàn bộ hệ thống ứng dụng
RDS MySQL	AWS Academy (Private subnet)	Lưu trữ dữ liệu chính
MinIO (Main + Backup)	AWS Academy (Private subnet)	Lưu trữ và sao lưu file
Firebase	Dịch vụ ngoài AWS	Gửi thông báo realtime
Route 53 + Domain	AWS	Quản lý DNS truy cập web

13. MÔ TẢ LUỒNG KẾT NỐI MẠNG HỆ THỐNG CLOUDIFYSHARE

Hệ thống hoạt động trong một VPC (Virtual Private Cloud), được chia thành các public subnet và private subnet để tách biệt giữa các thành phần hướng Internet (public-facing) và nội bộ (internal-facing).
Luồng truyền dữ liệu được chia thành ba loại chính: Inbound traffic, Outbound traffic, và Internal traffic.

13.1. Luồng Inbound (từ người dùng vào hệ thống)

Mục tiêu: người dùng truy cập vào Flask App thông qua tên miền được quản lý bởi Route 53.

Trình tự luồng Inbound:

Người dùng nhập địa chỉ: http://app.cloudifyshare.website

Route 53 DNS phân giải domain đến Application Load Balancer (ALB) trong public subnet.

ALB tiếp nhận request HTTP/HTTPS qua cổng 80/443.

ALB chuyển tiếp yêu cầu đến EC2 Flask App trong private subnet (được đăng ký trong Target Group).

EC2 Flask App xử lý yêu cầu, truy vấn dữ liệu từ RDS MySQL hoặc đọc file từ MinIO.

Flask App gửi phản hồi (Response) ngược trở lại ALB.

ALB trả kết quả cuối cùng cho người dùng thông qua Internet Gateway.

Luồng tóm tắt:

Người dùng → Route 53 → Internet Gateway → ALB (Public subnet) → EC2 Flask App (Private subnet) → RDS / MinIO → Người dùng.

Đặc điểm:

ALB là thành phần duy nhất public-facing.

EC2 Flask App không có Public IP, chỉ nhận traffic nội bộ từ ALB.

Luồng này đi từ ngoài vào trong VPC.

13.2. Luồng Outbound (từ hệ thống ra Internet)

Mục tiêu: cho phép EC2 Flask App gọi API bên ngoài, gửi thông báo, hoặc cập nhật gói phần mềm.

Trình tự luồng Outbound:

EC2 Flask App (private subnet) gửi request ra ngoài Internet (ví dụ: gửi dữ liệu đến Firebase hoặc truy cập API).

Request được định tuyến qua Route Table của private subnet, chuyển đến NAT Gateway trong public subnet.

NAT Gateway chuyển request ra ngoài thông qua Internet Gateway.

Dịch vụ bên ngoài (như Firebase) trả dữ liệu phản hồi ngược lại qua NAT → EC2 Flask App.

Luồng tóm tắt:

EC2 Flask App → NAT Gateway (Public subnet) → Internet Gateway → Internet (Firebase, API ngoài).

Đặc điểm:

EC2 Flask App không có Public IP, nhưng vẫn ra Internet được nhờ NAT Gateway.

NAT Gateway giúp duy trì tính bảo mật, vì không cho phép truy cập từ Internet vào private subnet.

Luồng này đi từ trong ra ngoài VPC.

13.3. Luồng Internal (giao tiếp nội bộ trong VPC)

Mục tiêu: các dịch vụ trong hệ thống giao tiếp với nhau nội bộ, không qua Internet.

Trình tự luồng Internal:

EC2 Flask App ↔ RDS MySQL:
Flask App truy vấn cơ sở dữ liệu thông qua endpoint nội bộ của RDS MySQL (port 3306).
Cả hai cùng nằm trong private subnet, thuộc cùng VPC.
Security Group sg-ec2 được phép truy cập vào sg-rds qua port 3306.

EC2 Flask App ↔ MinIO:
Khi người dùng tải lên hoặc tải xuống file, Flask App gọi MinIO thông qua endpoint nội bộ (port 9000).
MinIO hoạt động trong private subnet nên không cần Internet để giao tiếp.
Trường hợp có MinIO backup ở AZ khác, dữ liệu được đồng bộ giữa hai server qua mạng nội bộ VPC.

EC2 Flask App ↔ CloudWatch:
Flask App gửi log và metric đến CloudWatch để giám sát (qua agent hoặc API).

RDS MySQL ↔ AWS Backup:
AWS Backup truy cập trực tiếp RDS để thực hiện sao lưu tự động hàng ngày.

Luồng tóm tắt:

Flask ↔ RDS: truyền dữ liệu cơ sở dữ liệu.

Flask ↔ MinIO: truyền file nội bộ.

RDS ↔ AWS Backup: sao lưu định kỳ.

Flask ↔ CloudWatch: gửi log và thông số hệ thống.

Đặc điểm:

Tất cả kết nối nội bộ đều diễn ra bên trong VPC, không qua Internet.

Độ trễ thấp, bảo mật cao, giảm thiểu rủi ro tấn công từ bên ngoài.

13.4. Luồng Quản trị (SSH)

Mục tiêu: quản trị viên truy cập vào EC2 Flask App trong private subnet thông qua Bastion Host.

Trình tự:

Quản trị viên SSH từ máy cá nhân đến Bastion Host qua địa chỉ Public IP (port 22).

Từ Bastion Host, SSH nội bộ đến EC2 Flask App bằng Private IP.

Sau khi kết nối, có thể kiểm tra log, khởi động Flask, hoặc triển khai cập nhật.

Luồng tóm tắt:

Máy quản trị → Bastion Host (Public subnet) → EC2 Flask App (Private subnet).

Đặc điểm:

Chỉ Bastion Host có Public IP.

Các EC2 Flask App không thể SSH trực tiếp từ Internet.

Security Group sg-bastion cho phép SSH từ IP quản trị; sg-ec2 chỉ nhận SSH từ sg-bastion.

13.5. Tổng hợp các luồng kết nối
Loại luồng	Hướng đi	Mục đích chính	Điểm đầu	Điểm cuối
Inbound	Ngoài → Trong	Người dùng truy cập Flask	User / Route53	EC2 Flask App
Outbound	Trong → Ngoài	Flask gửi API / Firebase	EC2 Flask App	Internet (qua NAT Gateway)
Internal	Nội bộ	Flask ↔ RDS ↔ MinIO ↔ CloudWatch	EC2 Flask App	RDS / MinIO / CloudWatch
SSH	Quản trị	Kết nối kiểm tra hệ thống	Admin PC	EC2 Flask App qua Bastion
13.6. Kết luận

Luồng dữ liệu trong hệ thống CloudifyShare được thiết kế phân tầng rõ ràng:

Public subnet chỉ chứa các thành phần tiếp xúc Internet (ALB, NAT, Bastion).

Private subnet chỉ chứa tài nguyên nội bộ (EC2, RDS, MinIO).

Tất cả truy cập bên ngoài đều đi qua ALB hoặc NAT Gateway.

Quản trị viên truy cập qua Bastion Host, đảm bảo an toàn tuyệt đối cho lớp ứng dụng.