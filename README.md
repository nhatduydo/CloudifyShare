# CloudifyShare
Xây dựng hệ thống nhắn tin, gởi nhận, chia sẻ dữ liệu trên nền tảng cloud computing

- thực hiện tạo database trên AWS => Aurora and RDS => Databases:
    + name: cloudsharedb
    + user: admin
    + pass: admin#123

- bật “Public access” cho RDS để cố thể thực hiện kết nối từ bên ngoài 
    + Vào Modify database => modify
    + Connectivity => Public access => yes

- bật public port 3306 ra ngoài, để có thể truy cập từ máy tính
    + Aurora and RDS => Databases => cloudsharedb
    + VPC security groups => click vào link để vào EC2
    + Edit inbound rules => MySQL/Aurora – TCP – 3306 – Source: 0.0.0.0/0

- thực hiện kết nối và tạo schema trên database cloud
    + mysql -h cloudsharedb.cclau0qkccdx.us-east-1.rds.amazonaws.com -u admin -p
    + Admin#123

    <!-- tạo database -->
    + CREATE DATABASE cloudsharedb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    + SHOW DATABASES;
    <!-- sử dụng database -->
    + USE cloudsharedb;

    <!-- xem các table trong database -->
    + SHOW TABLES;

    <!-- xem dữ liệu  -->
    + SELECT * FROM files;
    + SELECT * FROM messages;
    + SELECT * FROM users;

    <!-- xem các trường của table -->
    + DESCRIBE users;
    + DESC users;


    <!-- tạo firebase nhatduy096@gmail.com -->
    
    <!-- tạo nơi lưu trữ file aws cloud - S3 -->

- AWS S3
tạo thùng chứa S3, lưu trữ dữ liệu file

- TẠO IAM USER để Flask có quyền truy cập S3
    + create 1 user
    + tạo Access Key / Secret Key
