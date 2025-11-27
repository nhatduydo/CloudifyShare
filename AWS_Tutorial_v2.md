# 1. Mục tiêu tổng quát
- VPC có 2 Availability Zones (AZ), chia thành các subnet public và private.
- Application Load Balancer (ALB) phân phối yêu cầu đến các EC2 Flask App nằm trong Auto Scaling Group.
- RDS MySQL hoạt động ở chế độ Single (Primary và Replica).
- MinIO được sử dụng để thay thế AWS S3, lưu trữ file người dùng.
- Firebase đảm nhiệm chức năng nhắn tin và thông báo thời gian thực.
- Bastion Host được triển khai ở public subnet để SSH vào các EC2 trong private subnet.
- CloudWatch giám sát tài nguyên.

# 2. Tạo VPC và Subnet
Truy cập AWS Console → VPC → Create VPC.
Chọn kiểu "VPC and more" và cấu hình như sau:

Name:                         cloudify
IPv4 CIDR:                    10.0.0.0/16
Tenancy:                      Default
Availability Zones:           2
Number of public subnets:     2
Number of private subnets:    2
NAT Gateway:                  1 per AZ
DNS hostnames:                Enable
DNS resolution:               Enable

Sau khi tạo, hệ thống sẽ có:
2 public subnet (chứa ALB, NAT Gateway và Bastion Host).
2 private subnet (chứa EC2 Flask App, RDS, MinIO).
1 Internet Gateway (IGW).
2 NAT Gateway (mỗi AZ một NAT).

# 3. Tạo Security Groups
Tạo 5 nhóm bảo mật chính:
  sg-lb: Cho Load Balancer (HTTP/HTTPS từ Internet).
  sg-ec2: Cho EC2 Flask App.
  sg-rds: Cho RDS MySQL.
  sg-bastion: Cho phép SSH từ máy quản trị.
  sg-minio

## 3.1 sg-lb (Load Balancer)
Mục đích: cho phép người dùng ngoài Internet truy cập vào hệ thống qua HTTP/HTTPS qua Route 53
Inbound rules:
Type	   Protocol	    Port	       Source	          Mục đích
HTTP  	    TCP	        80	          0.0.0.0/0	      Cho phép truy cập HTTP từ Internet
HTTPS	    TCP	        443	          0.0.0.0/0	      Cho phép truy cập HTTPS từ Internet
ICMP        All	        -	          0.0.0.0/0	      Ping test (tuỳ chọn)
Outbound rules: giữ mặc định (All traffic).
Luồng: Người dùng → Route 53 → ALB qua port 80/443.

## 3.2 sg-bastion (Bastion Host)
Mục đích: cho phép máy quản trị SSH vào hệ thống.
Inbound rules:
  Type	      Protocol	        Port	        Source	            Ghi chú
  SSH	        TCP	            22	         <IP máy bạn>/32	    Chỉ IP cá nhân của bạn được SSH
  ICMP	        All	            All	          0.0.0.0/0	            Ping test (tùy chọn)

Outbound rules: giữ mặc định.
Luồng: Máy quản trị → Bastion (Public IP) → EC2 Flask (Private IP).


## 3.3 sg-ec2 (Flask App)
Mục đích: cho phép ALB truy cập Flask app và Bastion SSH vào.
Inbound rules:
  Type	      Protocol	      Port	      Source	      Ghi chú
  HTTP	        TCP	          80	        sg-lb	        Chỉ ALB được phép truy cập Flask
  SSH	        TCP	          22	        sg-bastion	    Cho phép Bastion Host SSH vào
  ICMP	        All	          All	        0.0.0.0/0	    Ping nội bộ kiểm tra
Outbound rules: giữ mặc định (All traffic).
Luồng: ALB → EC2 Flask App.
Flask chỉ nhận truy cập từ ALB và SSH từ Bastion.

## 3.4 sg-rds (RDS MySQL)
Mục đích: chỉ cho EC2 Flask được phép kết nối cơ sở dữ liệu.
Inbound rules:
  Type	        Protocol	      Port	      Source	          Ghi chú
  MySQL/Aurora	  TCP	          3306	      sg-ec2-flask	    Chỉ Flask App được kết nối DB

Outbound rules: giữ mặc định.
Luồng: EC2 Flask → RDS MySQL (port 3306).


## 3.5 sg-minio (MinIO Storage)
Mục đích:
Cho phép EC2 Flask App truy cập dịch vụ MinIO nội bộ để đọc/ghi file qua API và Console.
Không mở public Internet để đảm bảo bảo mật dữ liệu người dùng.

Inbound rules:
  Type	      Protocol	          Port	      Source	      Mục đích
  Custom TCP	  TCP	          9000	      sg-ec2	      Flask App gọi API upload/download
  Custom TCP	  TCP	          9001	      sg-ec2	      Flask App hoặc quản trị truy cập console
  ICMP	All	-	0.0.0.0/0	Ping test (tuỳ chọn)
Outbound rules: giữ mặc định.


# 4. Tạo Bastion Host
### tạo bastion public
#### BƯỚC 1: Tạo Bastion Host EC2 (Public Subnet)
Vào AWS Console → EC2 → Launch instance
    Name: bastion-host
    AMI: Ubuntu Server 22.04 LTS
    Instance type: t2.micro (Free tier đủ dùng)
    Key pair: Dùng lại cloudify-key.pem
    Network settings:
    VPC: cloudify-vpc
    Subnet: cloudify-subnet-public1-us-east-1a
    Auto-assign public IP: Enable
    Security group: Chọn sg-bastion

#### BƯỚC 2: Kiểm tra routing
    Bastion nằm trong public subnet, nên route table của subnet đó phải có:
    0.0.0.0/0 → igw-xxxxxxxx (Internet Gateway)

#### BƯỚC 3: Cho phép Bastion SSH vào EC2 Flask
    Chỉnh Security Group của EC2 Flask (sg-ec2):
    Vào EC2 → Security Groups → sg-ec2
    Chọn Edit inbound rules
    Thêm rule:
        Type: SSH
        Port: 22
        Source: sg-bastion

#### BƯỚC 4: Kết nối SSH
    Khi instance Bastion đã chạy, thực hiện:
        ssh -i "cloudify-key.pem" ubuntu@<BASTION_PUBLIC_IP>
        ssh -i "cloudify.pem" ubuntu@ec2-3-232-78-27.compute-1.amazonaws.com
    Sau khi vào Bastion:
        copy file .pem từ máy cá nhân vào bastion
            scp -i "C:\Users\nhatduy\Downloads\cloudify.pem" "C:\Users\nhatduy\Downloads\cloudify.pem" ubuntu@3.81.22.55:/home/ubuntu/
            scp -i "cloudify.pem" cloudify.pem ubuntu@<BASTION_PUBLIC_IP>:/home/ubuntu/
            chmod 400 cloudify.pem

        ssh -i "cloudify-key.pem" ubuntu@<PRIVATE_IP_OF_FLASK_EC2>
        ssh -i "cloudify.pem" ubuntu@10.0.129.44

    Kiểm tra Flask có đang chạy không
        ps aux | grep python3

Kết quả mong muốn:
    Bạn SSH vào Bastion bằng public IP
    Từ Bastion SSH nội bộ vào EC2 Flask bằng private IP
    Sau đó bạn có thể xem log Flask hoặc chạy lệnh kiểm tra app.


# 5. Cấu hình MinIO (thay thế S3)
Cài đặt MinIO trong private subnet (hoặc EC2 riêng).

## hướng dẫn private
Tạo 1 instance mới:
Có thể truy cập web http://<public-ip>:9001

### BƯỚC 1: Mở AWS Console → EC2 → Launch instance
Mục	Giá trị đề xuất
Name	            minio-public
AMI	                Ubuntu Server 22.04 LTS
Instance type	    t3.micro (hoặc t2.micro)
Key pair	        Chọn key bạn đã có (ví dụ: cloudify.pem)

### BƯỚC 2: Cấu hình Network
Tạo EC2 MinIO trong private subnet
Launch EC2
Subnet: cloudify-subnet-private1-us-east-1a
Auto-assign Public IP: Disable
SG: sg-minio
Storage: 20–30 GB là đủ
User data cài MinIO

# 6. Tạo RDS MySQL (trong AWS Academy)
## tạo DB Subnet Group
### bước 1. Basic info
RDS => Subnet groups → Create DB Subnet Group
Field	                Value
Name	                cloudify-db-subnet
Description         	Subnet group for RDS in cloudify VPC
VPC	                    cloudifyshare-vpc

### bước 2. Add subnets
CHỈ cần chọn private subnets
Availability Zones            us-east-1a, us-esat-1b
Subnets
        cloudifyshare-subnet-private1-us-east-1a
        cloudifyshare-subnet-private2-us-east-1b


## tạo RDS - MySQL

RDS → Create Database → Standard create.

Thuộc tính	                                        Giá trị
Engine	                                            MySQL 8.0
Show only versions that support Multi-AZ            Không
Show only versions that support Optimized Writes    Không
Enable RDS Extended Support                         Không
DB identifier	                                    cloudsharedb
Master username	                                    admin
Credentials management                              Self managed
Password	                                        admin123
Instance configuration                              Burstable classes
Storage type                                        gp3


Don’t connect to an EC2 compute resource
Public access	                                    No
VPC	                                                cloudify-vpc
Subnet group	                                    Private subnet
Security group	                                    sg-rds

Availability Zone                  No preference
RDS Proxy                          khoong tick
Database authentication options    Password authentication

Log exports
        Enhanced Monitoring        x
        Audit Log                  x
        Error Log                  v
        General Log                x
        Slow Query Log             x

Flask cấu hình (.env):
```
DB_HOST=<endpoint của RDS nội bộ>
DB_USER=admin
DB_PASS=admin123
DB_NAME=cloudsharedb
```

## kiểm tra kết database 
từ basiotn => ec2 flask 

### test kết nối 
nc -zv cloudsharedb.c7qeeiky0vnm.us-east-1.rds.amazonaws.com 3306
==> nếu thành công: Connection to cloudsharedb.c7qeeiky0vnm.us-east-1.rds.amazonaws.com 3306 port [tcp/mysql] succeeded!

## kết nối mysql
Cài MySQL client
```
sudo apt update
sudo apt install mysql-client -y
```
```
mysql -h cloudsharedb.c7qeeiky0vnm.us-east-1.rds.amazonaws.com -u admin -p
```

admin123
Nếu OK → sẽ thấy:   mysql>

SHOW DATABASES;
CREATE DATABASE cloudifyshare;

# 6.2 tạo database dự phòng 
## Bước 1: Tạo RDS MySQL Read Replica cho cloudsharedb
AWS Console → RDS → Databases => cloudsharedb
Nhấn vào “Actions” → Create read replica.

Cấu hình Read Replica:
DB Identifier:              cloudsharedb-replica
Instance type:              Chọn instance size tương tự hoặc nhỏ hơn (ví dụ: db.t3.micro).
VPC:                        Chọn cùng VPC với cloudsharedb.
Subnet group:               Chọn Private subnets.
Public access:              Chọn No (Để replica không được public).
VPC Security group:         Chọn sg-rds (Security group của RDS).
Multi-AZ:                   Bỏ chọn.
Database authentication:    Chọn Password authentication.
Nhấn Create read replica.

## Bước 2: Kiểm tra trạng thái của Read Replica
Sau khi hoàn tất, AWS sẽ tạo Read Replica cho cloudsharedb.
Kết nối đến replica qua endpoint cloudsharedb-replica.cjzdt6vrob6s.us-east-1.rds.amazonaws.com (replica endpoint) để kiểm tra tính sẵn sàng của nó.

## Bước 3: Cập nhật ứng dụng Flask để kết nối với Replica
Trong file .env của Flask, bạn cần thay đổi DB_HOST để trỏ đến replica.
DB_HOST=cloudsharedb-replica.cjzdt6vrob6s.us-east-1.rds.amazonaws.com
DB_USER=admin
DB_PASS=admin123
DB_NAME=cloudsharedb

## Bước 4: Failover (nếu cần thiết)
Nếu cloudsharedb (Master DB) gặp sự cố và bạn cần chuyển sang replica, bạn có thể promote replica thành master để tiếp tục hoạt động:
Truy cập RDS → Databases.
Chọn cloudsharedb-replica.
Nhấn “Promote” để chuyển cloudsharedb-replica thành Master.
Ứng dụng Flask sẽ cần cập nhật lại thông tin DB_HOST để trỏ tới cloudsharedb-replica (nay đã là Master).

## Giải pháp 2: Sử dụng Snapshot và Backup thủ công
Nếu bạn không muốn sử dụng MySQL replication, bạn có thể làm theo cách đơn giản hơn:
Tạo snapshot của cloudsharedb.
Tạo một RDS instance mới từ snapshot này, đặt tên ví dụ là cloudsharedb-backup.
Cập nhật .env trong Flask nếu bạn cần sử dụng backup.
Lưu ý: Phương pháp này yêu cầu bạn khôi phục thủ công khi có sự cố xảy ra, và không có tính năng tự động failover như MySQL replication.

## công dụng 
Giảm tải cho Master DB
Chia tải đọc: Nếu ứng dụng của bạn có rất nhiều truy vấn đọc (SELECT) và chỉ một số ít ghi (INSERT, UPDATE, DELETE), thì Read Replica sẽ giúp chia sẻ tải cho Master DB.
Hiệu suất: Việc chuyển các truy vấn đọc sang Read Replica giúp Master DB tập trung vào các truy vấn ghi và giảm tải cho nó, cải thiện hiệu suất tổng thể của hệ thống.
Lợi ích: Hệ thống có thể xử lý nhiều truy vấn đọc mà không làm ảnh hưởng đến việc ghi dữ liệu trên Master DB.

2. Nâng cao độ tin cậy và khả năng phục hồi (Disaster Recovery)
Khả năng phục hồi: Nếu Master DB gặp sự cố, bạn có thể promote Read Replica thành Master để hệ thống tiếp tục hoạt động mà không bị gián đoạn.
Giảm thời gian downtime: Việc promote Read Replica thành Master giúp phục hồi hệ thống nhanh chóng mà không cần phải khôi phục từ sao lưu.

3. Sao lưu dữ liệu mà không làm gián đoạn hoạt động
Sao lưu mà không làm gián đoạn: Bạn có thể sử dụng Read Replica để sao lưu dữ liệu mà không ảnh hưởng đến Master DB. Vì các sao lưu dữ liệu thường chỉ yêu cầu đọc, bạn có thể làm việc với Read Replica để sao lưu mà không làm ảnh hưởng đến hiệu suất ghi của Master DB.

4. Cải thiện khả năng mở rộng (Scalability)
Mở rộng quy mô đọc: Nếu hệ thống của bạn cần xử lý một lượng lớn truy vấn đọc (ví dụ, khi bạn có nhiều người dùng truy cập hệ thống đồng thời), bạn có thể sử dụng nhiều Read Replica để xử lý các truy vấn đọc thay vì làm chậm lại Master DB.
Hỗ trợ Load Balancing: Bạn có thể cấu hình load balancing để phân phối các truy vấn đọc giữa các Read Replica nhằm tối ưu hóa hiệu suất.

5. Dễ dàng triển khai các phân tích và báo cáo
Độc lập với Master DB: Nếu bạn cần thực hiện phân tích hoặc báo cáo nặng (các truy vấn phức tạp hoặc yêu cầu tính toán dữ liệu), bạn có thể chuyển chúng sang Read Replica, tránh làm ảnh hưởng đến hiệu suất của Master DB.
Phân tách giữa đọc và ghi: Điều này giúp bạn đảm bảo rằng Master DB chỉ thực hiện các tác vụ quan trọng liên quan đến ghi dữ liệu.

## “Nếu Master chết thì còn ghi dữ liệu được không?”
Không.
Replica là read-only, bạn không thể INSERT, UPDATE, DELETE lên Replica.
➡ Khi master chết: app của bạn chỉ còn có thể đọc.

Nhưng đây là tình huống thực tế:
### Giải pháp khi master chết:
### Bước 1 — Promote Replica thành Master (1 click)
Trong AWS Console → RDS → chọn Replica → Actions → Promote.
Sau khi promote:
Replica trở thành Master mới
Cho phép ghi lại bình thường

### Bước 2 — Update lại .env
Đổi .env:
DATABASE_URL=mysql+pymysql://admin:admin123@<new-master-endpoint>:3306/cloudifyshare
Rồi deploy lại Flask.
Xong → hệ thống chạy bình thường như chưa từng xảy ra lỗi.
Khi master chết → hệ thống của bạn KHÔNG bị down hoàn toàn
Vì:
Các API SELECT (dashboard, list file, xem message) → vẫn chạy
Các API tạo mới (đăng ký, gửi tin nhắn, upload file) → sẽ báo lỗi tạm thời
Nhưng toàn bộ dữ liệu vẫn nguyên vẹn vì Replica vẫn có bản sao.

# 7. Tạo EC2 Flask App (Launch Template)
#### Bước 1 — Mở Launch Template
- EC2 → Launch Template → Create Launch Template
BƯỚC 3: Tạo EC2 Launch Template (Flask App)
    Mục	                            Giá trị
    Name	                        flask-template
    Description	                    Template for Flask EC2 instances
    Auto Scaling guidance	        Enabled

Cấu hình:
    Quick Start
    AMI: Ubuntu Server 22.04 LTS (Free tier eligible)
    Instance type: t2.micro
    Key pair: cloudify-key.pem (tạo mới nếu chưa có)
    Network: Không chọn subnet
    Auto-assign public IP: Disable (vì ở private subnet)
    Availability Zone: Để trống	Auto chọn
    Security group: sg-ec2
    Volume: 8 GiB gp3
    Tag: Project=CloudifyShare

#### Bước 2 - Advanced network configuration
- Subnet: Remove subnet (nếu còn hiện dòng đỏ)	Không được chọn subnet cho Auto Scaling
- Security groups: sg-ec2-flask
- Auto-assign public IP: Disable	Vì EC2 Flask nằm trong private subnet, không có IP public
Các phần khác (Primary IP, IPv6, Prefixes, Description, …)	Để mặc định (Don't include)	Không cần chỉnh

#### Bước 3 — Advanced details → User data (rất quan trọng)
Trong ô User data, dán đoạn script sau để EC2 tự cài app Flask khi khởi động:

```
EC2 cài Python, pip, git
Clone repo CloudifyShare (nhánh main)
Cài thư viện Flask
Tự động thêm crontab để Flask chạy lại sau mỗi lần reboot
Chạy Flask ngay lần đầu EC2 khởi động
```
### Bước 4 — Review & Create
Nhấn Create launch template
→ AWS sẽ tạo mẫu máy chủ EC2 Flask của bạn.

Bạn có thể kiểm tra bằng cách:
- Vào EC2 → Launch Template → flask-template → Launch instance from template
- Chạy thử 1 máy để kiểm tra:
    Khi khởi động xong → SSH vào máy
Dùng lệnh:
    ps aux | grep python
Nếu thấy python3 run.py đang chạy → script hoạt động tốt 



# 8. Tạo Auto Scaling Group
- EC2 → Auto Scaling Groups → Create
- Name:                         asg-flask
- Launch template:              flask-template
- Version:                      Latest
- VPC:                          cloudify-vpc
- Availability Zones and subnets: private1 và private2
- Balanced best effort

#### Integrate with other services - optional - Load balancing 
- Select Load balancing options: Attach to an existing load balancer
- chọn tg-flask

- Load balancer type:                           Application Load Balancer (ALB) (HTTP, HTTPS)
- Load balancer name:                           asg-flask-lb
- Load balancer scheme:                         Internet-facing
- Availability Zones and subnets:               Chọn 2 public subnets
- Listeners and routing: Protocol:              HTTP - Port: 80
- Default routing (target group):               Create a target group

#### Health Checks:
EC2 health checks: Enabled
ELB health checks: Enabled
Health check grace period: 300 giây

#### VPC Lattice integration options
- Select VPC Lattice service to attach:                 No VPC Lattice service
- Application Recovery Controller (ARC) zonal shift:    không tick Health checks
- EC2 health checks:                                    Always enabled
- Turn on Elastic Load Balancing health checks:         Bật
- Turn on Amazon EBS health checks:                     Không bật
- Health check grace period:                            300

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
- chọn:                                                     Launch before terminating
- Capacity Reservation preference:                          Default
- Enable instance scale-in protection:                      Không bật
- Enable group metrics collection within CloudWatch:        Bật
- Enable default instance warmu:p                           Bật, 180 seconds

- Add tags: Project = CloudifyShare
==> Create Auto Scaling group

### kiểm tra hoạt động thực tế của hệ thống
Sau khi nhấn Create và đợi vài phút (~3-5 phút):
    Vào EC2 → Auto Scaling Groups → Instance management → kiểm tra Health = Healthy.
    Vào EC2 → Load Balancers → cloudify-lb → copy DNS name → dán vào trình duyệt.


- AWS Console → EC2 → Load Balancers
- Chọn Application Load Balancer bạn đã tạo
- Chuyển sang tab “instance management” bạn sẽ thấy dòng: 
    Kiểm tra Status = running và Health = healthy.


# hướng dẫn kêt nối load banlancer - ec2 instance  private
## Bước 1. Tạo ALB
Vào:
AWS Console → EC2 → Load Balancers → Create Load Balancer → Application Load Balancer

Mục	Giá trị
Name	                            cloudify-lb
Scheme	                          Internet-facing
Load balancer IP address type	    IPv4
VPC	                              cloudify-vpc
IP pools                          bỏ trống
Mappings	                        Chọn 2 public subnets
Security group	                  Chọn sg-lb (HTTP/HTTPS từ Internet)
Listeners	                        HTTP port 80
Routing action                    Forward to target groups
## Bước 2. Tạo Target Group
Khi AWS hỏi "Target group" → chọn Create target group.==> 
                tg-flask
Mục	                Giá trị
Target type	        Instances
Protocol	          HTTP
Port	              80
VPC	                cloudify-vpc
Health check path	  / (nếu Flask có trang chủ)
→ Create target group
Sau đó, Add target manually → chọn EC2 Flask instance private subnet → Add to registered.

## Bước 3. Gắn Target Group vào ALB
Trong giao diện ALB đang tạo, chọn Listener: HTTP:80 → Forward to target group vừa tạo ở bước trên.
Nhấn Create Load Balancer.

## Bước 4. Kiểm tra
Sau vài phút (khi trạng thái target = healthy):
Vào EC2 → Load Balancers → cloudify-lb
Copy dòng DNS name (ví dụ: cloudify-lb-123456789.us-east-1.elb.amazonaws.com)
Dán lên trình duyệt: http://cloudify-lb-123456789.us-east-1.elb.amazonaws.com
  Nếu thấy giao diện Flask → thành công rồi!
  Cấu trúc sau bước này:
      User (browser)
          ↓
      Internet
          ↓
      Application Load Balancer (Public Subnet)
          ↓
      EC2 Flask App (Private Subnet)
→ Không cần public IP cho EC2.
→ Security group sg-ec2 chỉ cần cho phép HTTP từ sg-lb.
→ Đây là cách production thực hiện 100%.

## Nhấn vào dòng “Create target group” (chữ xanh bên phải)
Một cửa sổ hoặc trang mới sẽ hiện ra để bạn tạo Target Group.
Tạo theo thông số sau:
Trường      	                      Giá trị
Target type	                        Instances
Target group name	                  tg-flask
Protocol	                          HTTP1
Port	                              80
VPC	                                cloudify-vpc
Health check protocol	              HTTP
Health check path	                  / (hoặc đường dẫn nào Flask có, ví dụ /login)

Rồi nhấn Next.

### Chọn Target (instance)
Ở phần “Register targets”, bạn sẽ thấy danh sách các EC2 trong VPC.
  → Chọn EC2 Flask instance private subnet mà bạn đã chạy Flask.
  → Click Add to registered (bên dưới)
  → Nhấn Create target group.


# 9. CloudWatch Monitoring 
CloudWatch:
Theo dõi CPU, RAM, Network của EC2 Flask App.
Tạo alarm khi CPU > 60% để scale out, < 30% để scale in.
AWS Backup:
Tạo Backup Plan: cloudify-backup-plan
Chọn tài nguyên: RDS, EC2
Frequency: Daily
Retention: 30 days

## PHẦN 1 — Thiết lập CloudWatch Monitoring + Auto Scaling Alarms
(để EC2 Flask App tự scale dựa trên CPU)
Bạn đã có Auto Scaling Group (asg-flask), nên chỉ cần tạo 2 alarm:
CPU > 60% → scale out
CPU < 30% → scale in
### BƯỚC 1 — Mở Auto Scaling Group
EC2 → Auto Scaling Groups → asg-flask
### BƯỚC 2 — Tạo Scaling Policy cho Scale Out (CPU > 70%)
Tab Automatic scaling
Nhấn Create dynamic scaling policy
Chọn:
1. Policy type                          Target tracking scaling
2. Scaling Policy Name                  asg-flask-scale-out
3. Metric type                          Average CPU Utilization
4. Target Value                         60%    (AWS tự tăng giảm để duy trì CPU ~60% → tương đương CPU > 70% sẽ scale out)
5. Instance warmup                      180 seconds
Nhấn Create.


### KẾT LUẬN CLOUDWATCH
Bạn đã có:
✔ Auto Scale Out khi traffic cao
✔ Auto Scale In khi traffic giảm
✔ Monitoring CPU trong CloudWatch
✔ Không cần tạo alarm thủ công (đã nằm trong scaling policy)


# 10.1 Route 53 và Domain => bỏ qua vì không có quyền

# 10.2 thực hiện SSL thông qua [cloudflare](https://cloudflare.com/)
### Bước 1: Tạo tài khoản Cloudflare và add domain
Vào trang cloudflare.com, đăng ký tài khoản (Free).
 chọn:                                      Add a site (hoặc Add domain).
Nhập domain:                                systemaccommodation.online
Chọn gói:                                   Free Plan
Cloudflare sẽ scan DNS hiện có. Cứ để nó chạy xong rồi qua bước sau.
### Bước 2. Domain gốc trỏ về ALB
Nếu bạn muốn truy cập thẳng:                https://systemaccommodation.online
thì thêm một bản ghi nữa:
Type:                       CNAME
Name:                       @
Target:                     cloudify-lb-450309802.us-east-1.elb.amazonaws.com
Proxy status:               bật (Proxied)
### Bước 3: Đổi Nameserver bên Namecheap sang Cloudflare
Khi add site xong, Cloudflare sẽ hiện 2 nameserver dạng:
    xxxxx.ns.cloudflare.com
    yyyyy.ns.cloudflare.com
Vào Namecheap → Domain List → chọn systemaccommodation.online → Manage.
Ở mục Nameservers:  Chọn: Custom DNS
Nhập 2 giá trị nameserver Cloudflare vừa cho.
Nhấn Save.
Sau đó chờ Cloudflare cập nhật.
Trong trang Cloudflare, ở phần Overview của domain, nó sẽ báo khi nào status chuyển sang “Active”. Thường mất 5-30 phút.    

### Bước 4: Bật SSL trên Cloudflare
Khi Cloudflare báo domain “Active”:
Vào trang quản lý domain trong Cloudflare.
Vào mục: SSL/TLS.
Ở phần SSL/TLS encryption mode, chọn:           Flexible
Giải thích:
    Trình duyệt ↔ Cloudflare: HTTPS
    Cloudflare ↔ ALB: HTTP (port 80)
    Hoàn toàn phù hợp với kiến trúc hiện tại của bạn, không cần certificate trên AWS.

### Bước 5: Bắt buộc chuyển HTTP sang HTTPS
Vẫn trong Cloudflare:
Vào mục SSL/TLS → Edge Certificates:
Bật “Always Use HTTPS”.
Bật “Automatic HTTPS Rewrites” (nếu có).
Như vậy, khi người dùng gõ http://app.systemaccommodation.online, Cloudflare sẽ tự redirect sang https://app.systemaccommodation.online.


# 11. Kết quả tổng thể
Thành phần	Nơi triển khai	Vai trò
VPC, EC2, ALB, Auto Scaling, Bastion, CloudWatch, Backup	AWS Academy	Toàn bộ hệ thống ứng dụng
RDS MySQL	AWS Academy (Private subnet)	Lưu trữ dữ liệu chính
MinIO (Main + Backup)	AWS Academy (Private subnet)	Lưu trữ và sao lưu file
Firebase	Dịch vụ ngoài AWS	Gửi thông báo realtime
Route 53 + Domain	AWS	Quản lý DNS truy cập web

# 12. MÔ TẢ LUỒNG KẾT NỐI MẠNG HỆ THỐNG CLOUDIFYSHARE
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