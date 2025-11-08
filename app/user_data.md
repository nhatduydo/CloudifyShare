# minio
## ver1 đã chạy được
```
#!/bin/bash
# CloudifyShare - Auto Install MinIO on Ubuntu 22.04
# Author: Duy
# Date: $(date)

set -e

# 1. Cập nhật hệ thống
apt update -y
apt install -y wget curl ufw

# 2. Tải và cài đặt MinIO
wget https://dl.min.io/server/minio/release/linux-amd64/minio -O /usr/local/bin/minio
chmod +x /usr/local/bin/minio

# 3. Tạo thư mục dữ liệu
mkdir -p /data
chown ubuntu:ubuntu /data

# 4. Tạo user và password cho MinIO
MINIO_USER="admin"
MINIO_PASS="admin123"

echo "MINIO_ROOT_USER=${MINIO_USER}" >> /etc/environment
echo "MINIO_ROOT_PASSWORD=${MINIO_PASS}" >> /etc/environment
export MINIO_ROOT_USER=${MINIO_USER}
export MINIO_ROOT_PASSWORD=${MINIO_PASS}

# 5. Tạo systemd service để tự chạy khi khởi động
cat <<EOF > /etc/systemd/system/minio.service
[Unit]
Description=MinIO Object Storage
After=network.target

[Service]
User=ubuntu
Group=ubuntu
Environment="MINIO_ROOT_USER=${MINIO_USER}"
Environment="MINIO_ROOT_PASSWORD=${MINIO_PASS}"
ExecStart=/usr/local/bin/minio server /data --console-address ":9001"
Restart=always
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

# 6. Mở firewall (tùy chọn)
ufw allow 22/tcp
ufw allow 9000/tcp
ufw allow 9001/tcp
ufw --force enable

# 7. Khởi động và kích hoạt MinIO
systemctl daemon-reload
systemctl enable minio
systemctl start minio

# 8. In trạng thái ra log
sleep 3
systemctl status minio | head -n 10

echo "===== CÀI ĐẶT THÀNH CÔNG MINIO ====="
echo "Truy cập tại: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):9001"
echo "Tài khoản: ${MINIO_USER}"
echo "Mật khẩu: ${MINIO_PASS}"
```

## ver2 - chưa test
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

# ec2
## đã chạy thành công 
```
#!/bin/bash
# CloudifyShare Auto Deploy Script (Ubuntu 22.04 - Stable)
set -e

# 1. Update system and install dependencies
apt update -y
apt install -y python3 python3-pip git

# 2. Clone project from GitHub (branch main)
cd /home/ubuntu
if [ ! -d "CloudifyShare" ]; then
  git clone -b main https://github.com/nhatduydo/CloudifyShare.git
fi
cd CloudifyShare

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Define log file
LOGFILE="/home/ubuntu/app.log"
touch $LOGFILE
chown ubuntu:ubuntu $LOGFILE
chmod 666 $LOGFILE

echo ">>> CloudifyShare auto-deploy started at $(date)" >> $LOGFILE

# 5. Stop old Flask process if running
pkill -f "python3 run.py" || true

# 6. Fix permissions
chown -R ubuntu:ubuntu /home/ubuntu/CloudifyShare
chmod -R 755 /home/ubuntu/CloudifyShare

# 7. Add cron job to auto start Flask on reboot (run as root)
croncmd="@reboot cd /home/ubuntu/CloudifyShare && nohup python3 run.py --host=0.0.0.0 --port=80 > $LOGFILE 2>&1 &"
(crontab -l 2>/dev/null | grep -F "$croncmd") || (crontab -l 2>/dev/null; echo "$croncmd") | crontab -

# 8. Start Flask app immediately (run as root)
nohup python3 run.py --host=0.0.0.0 --port=80 > $LOGFILE 2>&1 &
```