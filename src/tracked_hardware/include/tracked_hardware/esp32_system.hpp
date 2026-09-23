#pragma once

#include <atomic>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include <hardware_interface/system_interface.hpp>
#include <hardware_interface/types/hardware_interface_return_values.hpp>
#include <rclcpp/rclcpp.hpp>
#include <rclcpp_lifecycle/state.hpp>
#include <geometry_msgs/msg/twist_with_covariance_stamped.hpp>
#include <sensor_msgs/msg/imu.hpp>
#include <sensor_msgs/msg/nav_sat_fix.hpp>
#include <sensor_msgs/msg/temperature.hpp>

#include "tracked_hardware/protocol.hpp"
#include "tracked_hardware/uart_driver.hpp"

namespace tracked_hardware
{

// ros2_control donanım arayüzü: ESP32 motor sürücüsü + IMU/GPS telemetrisi (UART).
//
// Komut: diff_drive_controller'dan gelen teker hızları (rad/s) -> palet hızı (m/s)
//        -> CmdVelPayload olarak ESP32'ye.
// Durum: ESP32 enkoder verisi göndermediği için teker durumları komutu yansıtır
//        (açık çevrim). Odometri bu yüzden komut tabanlıdır.
// Telemetri: ESP32'nin IMU/GPS paketleri RX thread'inden doğrudan yayınlanır
//        (/imu/data_raw, /imu/temperature, /gps/fix, /gps/fix_velocity).
class ESP32System : public hardware_interface::SystemInterface
{
public:
  RCLCPP_SHARED_PTR_DEFINITIONS(ESP32System)

  ~ESP32System() override;

  hardware_interface::CallbackReturn on_init(
    const hardware_interface::HardwareComponentInterfaceParams & params) override;

  hardware_interface::CallbackReturn on_configure(const rclcpp_lifecycle::State & previous_state) override;
  hardware_interface::CallbackReturn on_activate(const rclcpp_lifecycle::State & previous_state) override;
  hardware_interface::CallbackReturn on_deactivate(const rclcpp_lifecycle::State & previous_state) override;
  hardware_interface::CallbackReturn on_cleanup(const rclcpp_lifecycle::State & previous_state) override;

  hardware_interface::return_type read(const rclcpp::Time & time, const rclcpp::Duration & period) override;
  hardware_interface::return_type write(const rclcpp::Time & time, const rclcpp::Duration & period) override;

private:
  void send_packet(uint8_t pkt_id, const uint8_t * payload, uint8_t len);
  void send_track_speeds(double v_left, double v_right);
  double mean_command(const std::vector<std::string> & joints) const;
  void start_rx();
  void stop_rx();
  void rx_loop();
  void handle_incoming_packet(uint8_t pkt_id, const uint8_t * payload, uint8_t len);

  // Parametreler (URDF <hardware><param>)
  std::string serial_port_;
  int baudrate_{115200};
  double wheel_radius_{0.05};
  double max_track_speed_{0.6};
  std::string imu_frame_id_{"imu_link"};
  std::string gps_frame_id_{"gps_link"};

  // Joint adları: her palet birden fazla yol tekeriyle modellenir; ESP32'ye palet başına
  // tek hız gider (diff_drive_controller bir taraftaki tüm tekerlere aynı komutu verir)
  std::vector<std::string> left_joints_;
  std::vector<std::string> right_joints_;
  std::vector<std::string> all_joints_;

  UartDriver uart_;
  std::mutex uart_write_mutex_;
  ProtocolParser parser_;
  std::atomic<bool> running_{false};
  std::thread rx_thread_;

  // Telemetri yayını için düğüm (controller_manager executor'ında döner)
  rclcpp::Node::SharedPtr node_;
  rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr pub_imu_;
  rclcpp::Publisher<sensor_msgs::msg::Temperature>::SharedPtr pub_temp_;
  rclcpp::Publisher<sensor_msgs::msg::NavSatFix>::SharedPtr pub_gps_;
  rclcpp::Publisher<geometry_msgs::msg::TwistWithCovarianceStamped>::SharedPtr pub_gps_vel_;
};

}  // namespace tracked_hardware
