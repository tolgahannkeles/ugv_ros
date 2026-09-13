#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include <sensor_msgs/msg/imu.hpp>
#include <sensor_msgs/msg/nav_sat_fix.hpp>
#include <sensor_msgs/msg/nav_sat_status.hpp>

#include <thread>
#include <atomic>
#include <algorithm>
#include <vector>

#include "tracked_hardware/protocol.hpp"
#include "tracked_hardware/uart_driver.hpp"

class ESP32Bridge : public rclcpp::Node {
public:
    ESP32Bridge() : Node("esp32_bridge"), running_(false) {
        // PARAMETERS: Robot kinematics and serial communication options
        this->declare_parameter<std::string>("port", "/dev/ttyAMA0");
        this->declare_parameter<int>("baudrate", 115200);
        this->declare_parameter<double>("track_width", 0.22);
        this->declare_parameter<double>("slip_factor", 1.25);
        this->declare_parameter<std::string>("imu_frame_id", "imu_link");
        this->declare_parameter<std::string>("gps_frame_id", "gps_link");

        std::string port = this->get_parameter("port").as_string();
        int baudrate = this->get_parameter("baudrate").as_int();
        double track_width = this->get_parameter("track_width").as_double();
        double slip_factor = this->get_parameter("slip_factor").as_double();

        effective_width_ = track_width * slip_factor;
        imu_frame_id_ = this->get_parameter("imu_frame_id").as_string();
        gps_frame_id_ = this->get_parameter("gps_frame_id").as_string();

        if (!uart_.open_port(port, baudrate)) {
            RCLCPP_FATAL(this->get_logger(), "Failed to open UART port: %s", port.c_str());
            throw std::runtime_error("UART connection error");
        }
        RCLCPP_INFO(this->get_logger(), "UART initialized: %s @ %d baud", port.c_str(), baudrate);

        // ROS: Publishers and subscriptions
        sub_cmd_vel_ = this->create_subscription<geometry_msgs::msg::Twist>(
            "/cmd_vel", 10, std::bind(&ESP32Bridge::cmd_vel_callback, this, std::placeholders::_1));
        pub_imu_ = this->create_publisher<sensor_msgs::msg::Imu>("/imu/data_raw", 10);
        pub_gps_ = this->create_publisher<sensor_msgs::msg::NavSatFix>("/gps/fix", 10);

        // CONCURRENCY: Background receiver worker
        running_ = true;
        rx_thread_ = std::thread(&ESP32Bridge::rx_loop, this);
    }

    ~ESP32Bridge() override {
        running_ = false;
        if (rx_thread_.joinable()) {
            rx_thread_.join();
        }
        uart_.close_port();
    }

private:
    UartDriver uart_;
    ProtocolParser parser_;
    std::atomic<bool> running_;
    std::thread rx_thread_;

    double effective_width_;
    std::string imu_frame_id_;
    std::string gps_frame_id_;

    rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr sub_cmd_vel_;
    rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr pub_imu_;
    rclcpp::Publisher<sensor_msgs::msg::NavSatFix>::SharedPtr pub_gps_;

    // KINEMATICS: Converts Twist to skid-steer wheel speeds with 0.6 m/s clamp
    void cmd_vel_callback(const geometry_msgs::msg::Twist::SharedPtr msg) {
        double vx = msg->linear.x;
        double wz = msg->angular.z;

        double v_left = vx - (wz * effective_width_ / 2.0);
        double v_right = vx + (wz * effective_width_ / 2.0);

        // ROBOTICS: Proportional velocity scaling to preserve steering radius
        constexpr double MAX_SPEED = 0.6;
        double largest = std::max(std::abs(v_left), std::abs(v_right));
        if (largest > MAX_SPEED) {
            v_left = (v_left / largest) * MAX_SPEED;
            v_right = (v_right / largest) * MAX_SPEED;
        }

        CmdVelPayload payload{static_cast<float>(v_left), static_cast<float>(v_right)};
        send_packet(PKT_ID_CMD_VEL, reinterpret_cast<const uint8_t *>(&payload), sizeof(payload));
    }

    // PROTOCOL: Packages payload into protocol frame and sends via UART
    void send_packet(uint8_t pkt_id, const uint8_t *payload, uint8_t len) {
        uint8_t crc = ProtocolParser::calculate_crc(pkt_id, len, payload);

        std::vector<uint8_t> frame;
        frame.reserve(len + 5);
        frame.push_back(FRAME_HEADER1);
        frame.push_back(FRAME_HEADER2);
        frame.push_back(pkt_id);
        frame.push_back(len);
        frame.insert(frame.end(), payload, payload + len);
        frame.push_back(crc);

        uart_.write_bytes(frame.data(), frame.size());
    }

    // WORKER: Dedicated serial reception loop
    void rx_loop() {
        uint8_t byte = 0;
        uint8_t pkt_id = 0;
        uint8_t payload_len = 0;
        uint8_t payload[64];

        while (running_ && rclcpp::ok()) {
            ssize_t n = uart_.read_byte(byte);
            if (n <= 0) continue;

            if (parser_.parse_byte(byte, pkt_id, payload, payload_len)) {
                handle_incoming_packet(pkt_id, payload, payload_len);
            }
        }
    }

    // TELEMETRY: Routes unpacked payload to target ROS publisher
    void handle_incoming_packet(uint8_t pkt_id, const uint8_t *payload, uint8_t len) {
        auto stamp = this->now();

        if (pkt_id == PKT_ID_IMU && len == sizeof(ImuPayload)) {
            ImuPayload data;
            std::memcpy(&data, payload, sizeof(ImuPayload));

            auto msg = sensor_msgs::msg::Imu();
            msg.header.stamp = stamp;
            msg.header.frame_id = imu_frame_id_;
            msg.linear_acceleration.x = data.ax;
            msg.linear_acceleration.y = data.ay;
            msg.linear_acceleration.z = data.az;
            msg.angular_velocity.x = data.gx;
            msg.angular_velocity.y = data.gy;
            msg.angular_velocity.z = data.gz;
            msg.orientation_covariance[0] = -1.0;
            pub_imu_->publish(msg);
        } else if (pkt_id == PKT_ID_GPS && len == sizeof(GpsPayload)) {
            GpsPayload data;
            std::memcpy(&data, payload, sizeof(GpsPayload));

            auto msg = sensor_msgs::msg::NavSatFix();
            msg.header.stamp = stamp;
            msg.header.frame_id = gps_frame_id_;
            msg.status.status = (data.fix > 0) ? sensor_msgs::msg::NavSatStatus::STATUS_FIX
                                               : sensor_msgs::msg::NavSatStatus::STATUS_NO_FIX;
            msg.status.service = sensor_msgs::msg::NavSatStatus::SERVICE_GPS;
            msg.latitude = data.lat;
            msg.longitude = data.lon;
            msg.altitude = 0.0;
            pub_gps_->publish(msg);
        }
    }
};

int main(int argc, char **argv) {
    rclcpp::init(argc, argv);
    auto node = std::make_shared<ESP32Bridge>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}