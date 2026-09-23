#include "tracked_hardware/esp32_system.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <vector>

#include <hardware_interface/types/hardware_interface_type_values.hpp>
#include <pluginlib/class_list_macros.hpp>
#include <sensor_msgs/msg/nav_sat_status.hpp>

namespace tracked_hardware
{

using hardware_interface::CallbackReturn;
using hardware_interface::return_type;

namespace
{
std::string param_or(
  const hardware_interface::HardwareInfo & info, const std::string & key, const std::string & fallback)
{
  auto it = info.hardware_parameters.find(key);
  return it != info.hardware_parameters.end() ? it->second : fallback;
}
}  // namespace

ESP32System::~ESP32System()
{
  stop_rx();
  uart_.close_port();
}

CallbackReturn ESP32System::on_init(const hardware_interface::HardwareComponentInterfaceParams & params)
{
  if (SystemInterface::on_init(params) != CallbackReturn::SUCCESS) {
    return CallbackReturn::ERROR;
  }
  const auto & info = get_hardware_info();

  // PARAMETERS: URDF <ros2_control><hardware><param> (tracked_description/urdf/ros2_control.xacro)
  serial_port_ = param_or(info, "serial_port", "/dev/ttyAMA0");
  baudrate_ = std::stoi(param_or(info, "baudrate", "115200"));
  wheel_radius_ = std::stod(param_or(info, "wheel_radius", "0.05"));
  max_track_speed_ = std::stod(param_or(info, "max_track_speed", "0.6"));
  imu_frame_id_ = param_or(info, "imu_frame_id", imu_frame_id_);
  gps_frame_id_ = param_or(info, "gps_frame_id", gps_frame_id_);

  // JOINTS: her palette bir ya da daha fazla yol tekeri; her biri velocity komut +
  // position/velocity durum. Taraf, joint adındaki 'left' / 'right' ile belirlenir.
  for (const auto & joint : info.joints) {
    if (joint.command_interfaces.size() != 1 ||
      joint.command_interfaces[0].name != hardware_interface::HW_IF_VELOCITY)
    {
      RCLCPP_FATAL(get_logger(), "Joint '%s' tek bir velocity komut arayuzu olmali", joint.name.c_str());
      return CallbackReturn::ERROR;
    }
    if (joint.name.find("left") != std::string::npos) {
      left_joints_.push_back(joint.name);
    } else if (joint.name.find("right") != std::string::npos) {
      right_joints_.push_back(joint.name);
    } else {
      RCLCPP_FATAL(get_logger(), "Joint '%s' adinda 'left' ya da 'right' yok", joint.name.c_str());
      return CallbackReturn::ERROR;
    }
    all_joints_.push_back(joint.name);
  }
  if (left_joints_.empty() || right_joints_.empty()) {
    RCLCPP_FATAL(get_logger(), "Her iki palet icin de en az bir joint gerekli");
    return CallbackReturn::ERROR;
  }

  // TELEMETRY: controller_manager'ın donanım düğümü üzerinden yayın
  node_ = get_node();
  if (!node_) {
    RCLCPP_FATAL(get_logger(), "Donanim bileseni dugumu yok; telemetri yayinlanamaz");
    return CallbackReturn::ERROR;
  }
  pub_imu_ = node_->create_publisher<sensor_msgs::msg::Imu>("/imu/data_raw", rclcpp::SensorDataQoS());
  pub_temp_ = node_->create_publisher<sensor_msgs::msg::Temperature>("/imu/temperature", 10);
  pub_gps_ = node_->create_publisher<sensor_msgs::msg::NavSatFix>("/gps/fix", 10);
  pub_gps_vel_ =
    node_->create_publisher<geometry_msgs::msg::TwistWithCovarianceStamped>("/gps/fix_velocity", 10);

  return CallbackReturn::SUCCESS;
}

CallbackReturn ESP32System::on_configure(const rclcpp_lifecycle::State &)
{
  if (!uart_.open_port(serial_port_, baudrate_)) {
    RCLCPP_FATAL(get_logger(), "UART acilamadi: %s", serial_port_.c_str());
    return CallbackReturn::ERROR;
  }
  RCLCPP_INFO(get_logger(), "UART hazir: %s @ %d baud", serial_port_.c_str(), baudrate_);

  for (const auto & joint : all_joints_) {
    set_state(joint + "/" + hardware_interface::HW_IF_POSITION, 0.0);
    set_state(joint + "/" + hardware_interface::HW_IF_VELOCITY, 0.0);
    set_command(joint + "/" + hardware_interface::HW_IF_VELOCITY, 0.0);
  }

  // Telemetri controller'lar aktif olmadan da akar
  start_rx();
  return CallbackReturn::SUCCESS;
}

CallbackReturn ESP32System::on_activate(const rclcpp_lifecycle::State &)
{
  for (const auto & joint : all_joints_) {
    set_command(joint + "/" + hardware_interface::HW_IF_VELOCITY, 0.0);
  }
  send_track_speeds(0.0, 0.0);
  RCLCPP_INFO(get_logger(), "ESP32 motor kontrolu aktif");
  return CallbackReturn::SUCCESS;
}

CallbackReturn ESP32System::on_deactivate(const rclcpp_lifecycle::State &)
{
  // SAFETY: Kontrol bırakılırken paletleri durdur
  send_track_speeds(0.0, 0.0);
  return CallbackReturn::SUCCESS;
}

CallbackReturn ESP32System::on_cleanup(const rclcpp_lifecycle::State &)
{
  stop_rx();
  uart_.close_port();
  return CallbackReturn::SUCCESS;
}

return_type ESP32System::read(const rclcpp::Time &, const rclcpp::Duration & period)
{
  // Enkoder yok: durum = son komut (açık çevrim), konum komuttan integre edilir
  const double dt = period.seconds();
  for (const auto & joint : all_joints_) {
    double vel = get_command(joint + "/" + hardware_interface::HW_IF_VELOCITY);
    if (!std::isfinite(vel)) {
      vel = 0.0;
    }
    const auto pos_name = joint + "/" + hardware_interface::HW_IF_POSITION;
    set_state(pos_name, get_state(pos_name) + vel * dt);
    set_state(joint + "/" + hardware_interface::HW_IF_VELOCITY, vel);
  }
  return return_type::OK;
}

double ESP32System::mean_command(const std::vector<std::string> & joints) const
{
  // diff_drive_controller bir taraftaki tüm tekerlere aynı hızı verir; ortalama NaN'ları eler
  double sum = 0.0;
  int count = 0;
  for (const auto & joint : joints) {
    const double vel = get_command(joint + "/" + hardware_interface::HW_IF_VELOCITY);
    if (std::isfinite(vel)) {
      sum += vel;
      ++count;
    }
  }
  return count > 0 ? sum / count : 0.0;
}

return_type ESP32System::write(const rclcpp::Time &, const rclcpp::Duration &)
{
  // rad/s -> m/s (ESP32 palet hızını m/s bekler)
  send_track_speeds(mean_command(left_joints_) * wheel_radius_,
    mean_command(right_joints_) * wheel_radius_);
  return return_type::OK;
}

void ESP32System::send_track_speeds(double v_left, double v_right)
{
  // ROBOTICS: Oransal ölçekleme dönüş yarıçapını korur (eski esp32_bridge ile aynı)
  const double largest = std::max(std::abs(v_left), std::abs(v_right));
  if (largest > max_track_speed_) {
    v_left = v_left / largest * max_track_speed_;
    v_right = v_right / largest * max_track_speed_;
  }

  CmdVelPayload payload{static_cast<float>(v_left), static_cast<float>(v_right)};
  send_packet(PKT_ID_CMD_VEL, reinterpret_cast<const uint8_t *>(&payload), sizeof(payload));
}

void ESP32System::send_packet(uint8_t pkt_id, const uint8_t * payload, uint8_t len)
{
  const uint8_t crc = ProtocolParser::calculate_crc(pkt_id, len, payload);

  std::vector<uint8_t> frame;
  frame.reserve(len + 5);
  frame.push_back(FRAME_HEADER1);
  frame.push_back(FRAME_HEADER2);
  frame.push_back(pkt_id);
  frame.push_back(len);
  frame.insert(frame.end(), payload, payload + len);
  frame.push_back(crc);

  std::lock_guard<std::mutex> lock(uart_write_mutex_);
  uart_.write_bytes(frame.data(), frame.size());
}

void ESP32System::start_rx()
{
  if (running_) {
    return;
  }
  parser_.reset();
  running_ = true;
  rx_thread_ = std::thread(&ESP32System::rx_loop, this);
}

void ESP32System::stop_rx()
{
  running_ = false;
  if (rx_thread_.joinable()) {
    rx_thread_.join();
  }
}

void ESP32System::rx_loop()
{
  uint8_t byte = 0;
  uint8_t pkt_id = 0;
  uint8_t payload_len = 0;
  uint8_t payload[64];

  // read_byte en fazla 100 ms bekler (VTIME), böylece kapanışta thread takılmaz
  while (running_) {
    if (uart_.read_byte(byte) <= 0) {
      continue;
    }
    if (parser_.parse_byte(byte, pkt_id, payload, payload_len)) {
      handle_incoming_packet(pkt_id, payload, payload_len);
    }
  }
}

void ESP32System::handle_incoming_packet(uint8_t pkt_id, const uint8_t * payload, uint8_t len)
{
  const auto stamp = node_->now();

  if (pkt_id == PKT_ID_IMU && len == sizeof(ImuPayload)) {
    ImuPayload data;
    std::memcpy(&data, payload, sizeof(ImuPayload));

    sensor_msgs::msg::Imu msg;
    msg.header.stamp = stamp;
    msg.header.frame_id = imu_frame_id_;
    msg.linear_acceleration.x = data.ax;
    msg.linear_acceleration.y = data.ay;
    msg.linear_acceleration.z = data.az;
    msg.angular_velocity.x = data.gx;
    msg.angular_velocity.y = data.gy;
    msg.angular_velocity.z = data.gz;
    msg.orientation_covariance[0] = -1.0;  // Ham IMU: yönelim yok (Madgwick hesaplar)
    pub_imu_->publish(msg);

    sensor_msgs::msg::Temperature temp;
    temp.header = msg.header;
    temp.temperature = data.temp;
    temp.variance = 0.0;
    pub_temp_->publish(temp);

  } else if (pkt_id == PKT_ID_GPS && len == sizeof(GpsPayload)) {
    GpsPayload data;
    std::memcpy(&data, payload, sizeof(GpsPayload));

    sensor_msgs::msg::NavSatFix msg;
    msg.header.stamp = stamp;
    msg.header.frame_id = gps_frame_id_;
    msg.status.status = data.fix > 0 ?
      sensor_msgs::msg::NavSatStatus::STATUS_FIX : sensor_msgs::msg::NavSatStatus::STATUS_NO_FIX;
    msg.status.service = sensor_msgs::msg::NavSatStatus::SERVICE_GPS;
    msg.latitude = data.lat;
    msg.longitude = data.lon;
    msg.altitude = static_cast<double>(data.alt);

    // Kovaryans: HDOP * tipik GPS standart sapması (~2.5 m)
    if (data.fix > 0 && data.hdop > 0.0f) {
      const double accuracy = data.hdop * 2.5;
      const double variance = accuracy * accuracy;
      msg.position_covariance[0] = variance;        // Doğu-Batı
      msg.position_covariance[4] = variance;        // Kuzey-Güney
      msg.position_covariance[8] = variance * 4.0;  // İrtifa
      msg.position_covariance_type = sensor_msgs::msg::NavSatFix::COVARIANCE_TYPE_APPROXIMATED;
    } else {
      msg.position_covariance_type = sensor_msgs::msg::NavSatFix::COVARIANCE_TYPE_UNKNOWN;
    }
    pub_gps_->publish(msg);

    if (data.fix > 0) {
      geometry_msgs::msg::TwistWithCovarianceStamped vel;
      vel.header.stamp = stamp;
      vel.header.frame_id = "base_link";
      vel.twist.twist.linear.x = static_cast<double>(data.speed);  // m/s, işaretsiz
      vel.twist.covariance[0] = 0.05;
      pub_gps_vel_->publish(vel);
    }
  }
}

}  // namespace tracked_hardware

PLUGINLIB_EXPORT_CLASS(tracked_hardware::ESP32System, hardware_interface::SystemInterface)
