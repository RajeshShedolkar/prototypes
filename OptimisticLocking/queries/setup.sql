
-- 1. Create Trips table
CREATE TABLE IF NOT EXISTS trips (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL
);

-- 2. Create Users table
CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

-- 3. Create Seats table
CREATE TABLE IF NOT EXISTS seats (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(10) NOT NULL,
    trip_id BIGINT NOT NULL,
    user_id BIGINT NULL,

    CONSTRAINT fk_seat_trip
        FOREIGN KEY (trip_id) REFERENCES trips(id),

    CONSTRAINT fk_seat_user
        FOREIGN KEY (user_id) REFERENCES users(id),

    UNIQUE KEY uk_trip_seat (trip_id, name)
);

-- 4. Insert one trip (fixed ID makes this script repeatable)
INSERT INTO trips (id, name)
VALUES (1, 'Pune to Mumbai')
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- 5. Insert 120 Indian users
INSERT INTO users (id, name) VALUES
(1, 'Aarav Sharma'),
(2, 'Vivaan Patel'),
(3, 'Aditya Verma'),
(4, 'Arjun Singh'),
(5, 'Sai Deshmukh'),
(6, 'Reyansh Joshi'),
(7, 'Ayaan Khan'),
(8, 'Krishna Mehta'),
(9, 'Ishaan Kulkarni'),
(10, 'Rohan Shah'),
(11, 'Rahul Patil'),
(12, 'Amit Gupta'),
(13, 'Karan Malhotra'),
(14, 'Akash Yadav'),
(15, 'Siddharth Rao'),
(16, 'Aniket Pawar'),
(17, 'Omkar Jadhav'),
(18, 'Saurabh Mishra'),
(19, 'Nikhil Chavan'),
(20, 'Harsh Agarwal'),
(21, 'Priya Sharma'),
(22, 'Ananya Patel'),
(23, 'Diya Verma'),
(24, 'Aadhya Singh'),
(25, 'Saanvi Deshmukh'),
(26, 'Isha Joshi'),
(27, 'Aarohi Kulkarni'),
(28, 'Kavya Shah'),
(29, 'Sneha Patil'),
(30, 'Pooja Gupta'),
(31, 'Neha Malhotra'),
(32, 'Riya Yadav'),
(33, 'Meera Rao'),
(34, 'Anjali Pawar'),
(35, 'Shruti Jadhav'),
(36, 'Aditi Mishra'),
(37, 'Tanvi Chavan'),
(38, 'Sakshi Agarwal'),
(39, 'Mrunal Desai'),
(40, 'Swara More'),
(41, 'Vikram Nair'),
(42, 'Manish Reddy'),
(43, 'Deepak Kumar'),
(44, 'Pranav Iyer'),
(45, 'Varun Shetty'),
(46, 'Abhishek Das'),
(47, 'Gaurav Sinha'),
(48, 'Mohit Bansal'),
(49, 'Shubham Tiwari'),
(50, 'Ritesh Kapse'),
(51, 'Kunal Mane'),
(52, 'Sanket Shinde'),
(53, 'Tejas Gokhale'),
(54, 'Pratik Bhosale'),
(55, 'Nitin Pawar'),
(56, 'Ajay Naik'),
(57, 'Vishal Thakur'),
(58, 'Mayank Jain'),
(59, 'Tarun Kapoor'),
(60, 'Abhinav Saxena'),
(61, 'Ira Sharma'),
(62, 'Myra Patel'),
(63, 'Anika Verma'),
(64, 'Pari Singh'),
(65, 'Navya Deshmukh'),
(66, 'Avni Joshi'),
(67, 'Radhika Kulkarni'),
(68, 'Nisha Shah'),
(69, 'Divya Patil'),
(70, 'Shreya Gupta'),
(71, 'Komal Malhotra'),
(72, 'Simran Yadav'),
(73, 'Pallavi Rao'),
(74, 'Mansi Pawar'),
(75, 'Vaishnavi Jadhav'),
(76, 'Rutuja Mishra'),
(77, 'Priti Chavan'),
(78, 'Gauri Agarwal'),
(79, 'Manasi Desai'),
(80, 'Ketaki More'),
(81, 'Yash Thakur'),
(82, 'Atharva Nair'),
(83, 'Dhruv Reddy'),
(84, 'Kabir Kumar'),
(85, 'Parth Iyer'),
(86, 'Rudra Shetty'),
(87, 'Dev Das'),
(88, 'Aryan Sinha'),
(89, 'Samar Bansal'),
(90, 'Aarush Tiwari'),
(91, 'Chirag Kapse'),
(92, 'Sameer Mane'),
(93, 'Abhijeet Shinde'),
(94, 'Rohit Gokhale'),
(95, 'Siddhesh Bhosale'),
(96, 'Akshay Naik'),
(97, 'Pankaj Jain'),
(98, 'Raj Malhotra'),
(99, 'Sachin Kapoor'),
(100, 'Jayant Saxena'),
(101, 'Amruta Sharma'),
(102, 'Prajkta Patel'),
(103, 'Madhura Verma'),
(104, 'Rashmi Singh'),
(105, 'Shivani Deshmukh'),
(106, 'Aishwarya Joshi'),
(107, 'Gayatri Kulkarni'),
(108, 'Bhakti Shah'),
(109, 'Sonal Patil'),
(110, 'Nandini Gupta'),
(111, 'Archana Rao'),
(112, 'Poonam Pawar'),
(113, 'Mugdha Jadhav'),
(114, 'Rupali Mishra'),
(115, 'Sayali Chavan'),
(116, 'Aparna Agarwal'),
(117, 'Prachi Desai'),
(118, 'Revati More'),
(119, 'Suhasini Nair'),
(120, 'Apeksha Reddy')
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- 6. Generate 120 seats: 20 rows x 6 columns
-- Seat names: 1-A to 20-F
-- Every seat initially has user_id = NULL

INSERT INTO seats (id, name, trip_id, user_id)
WITH RECURSIVE seat_numbers AS (
    SELECT 1 AS n
    UNION ALL
    SELECT n + 1
    FROM seat_numbers
    WHERE n < 120
)
SELECT
    n,
    CONCAT(
        CEIL(n / 6),
        '-',
        CHAR(65 + MOD(n - 1, 6))
    ),
    1,
    NULL
FROM seat_numbers
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    trip_id = VALUES(trip_id),
    user_id = NULL;
