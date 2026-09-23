#!/bin/bash
# Robot (Raspberry Pi 5, Ubuntu 24.04 arm64) ortam kurulumu.
# Tekrar çalıştırmak güvenlidir. Ayrıntılar: docs/SETUP.md
#
# Kullanım (Pi üzerinde, repo kökünden):
#   bash tools/setup/setup_robot.sh [--peer <pc-ip>]
#
#   --peer  CycloneDDS için geliştirme PC'sinin IP'si (varsayılan 192.168.1.105)
#
# Repo kökü aynı zamanda colcon workspace'idir (~/ugv_ros/{src,build,install}).
# camera_ros bu betikle kurulmaz: Pi 5 (RP1-CFE) için Raspberry Pi libcamera'sı gerekir.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

PEER=192.168.1.105
while [ $# -gt 0 ]; do
  case "$1" in
    --peer) PEER="$2"; shift 2 ;;
    *) die "bilinmeyen arguman: $1" ;;
  esac
done

check_os
apt_install "${ROBOT_APT_PACKAGES[@]}"
build_deps_overlay

# Pi'de bellek sınırlı: simülasyon paketleri atlanır, paralel iş sayısı düşük tutulur
build_workspace "$REPO_ROOT" --packages-up-to tracked_bringup --parallel-workers 2

log "Donanim kontrolleri"
if id -nG "$USER" | grep -qw dialout; then
  echo "dialout grubu: tamam"
else
  sudo usermod -aG dialout "$USER"
  warn "$USER dialout grubuna eklendi; oturumu kapatip acin (ya da yeniden baslatin)"
fi
CONFIG_TXT=/boot/firmware/config.txt
if [ -f "$CONFIG_TXT" ] && ! grep -qE '^\s*dtparam=uart0=on' "$CONFIG_TXT"; then
  warn "$CONFIG_TXT icinde 'dtparam=uart0=on' yok: ESP32 UART'i (/dev/ttyAMA0, GPIO 14/15) icin ekleyip yeniden baslatin"
fi
if grep -qE 'console=(serial0|ttyAMA0)' /boot/firmware/cmdline.txt 2>/dev/null; then
  warn "cmdline.txt seri konsolu UART'ta aciyor; 'console=serial0,...' kismini silin (ESP32 ile cakisir)"
fi
[ -e /dev/ttyAMA0 ] && echo "/dev/ttyAMA0: var" || warn "/dev/ttyAMA0 yok (UART acik degil ya da yeniden baslatma gerekli)"
if ! ros2_prefix=$(source_ros; ros2 pkg prefix camera_ros 2>/dev/null); then
  warn "camera_ros bulunamadi: Pi 5 kamerasi icin kaynaktan kurun (docs/SETUP.md)"
fi
# controller_manager FIFO gerçek zamanlı zamanlama isteği (yoksa sadece uyarı basar)
if [ ! -f /etc/security/limits.d/ros2.conf ]; then
  echo "$USER - rtprio 99" | sudo tee /etc/security/limits.d/ros2.conf > /dev/null
  echo "rtprio izni eklendi (yeniden oturum acinca gecerli)"
fi

write_cyclonedds_config "$PEER"
write_bashrc_block "source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file://\$HOME/cyclonedds.xml
# Workspace (overlay'i ve /opt/ros'u zincirleme yükler)
[ -f $REPO_ROOT/install/setup.bash ] && source $REPO_ROOT/install/setup.bash"

log "Tamam. Yeni bir terminal acip (paletler havadayken ilk deneme):"
echo "  ros2 launch tracked_bringup robot.launch.py"
