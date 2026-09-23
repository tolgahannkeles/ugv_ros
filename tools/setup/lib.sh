#!/bin/bash
# setup_pc_sim.sh ve setup_robot.sh için ortak fonksiyonlar. Doğrudan çalıştırılmaz.
# Ayrıntılar: docs/SETUP.md

set -eo pipefail

ROS_DISTRO_NAME=jazzy
DEPS_WS="${DEPS_WS:-$HOME/ugv_deps_ws}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Hem robotta hem simülasyonda gereken ROS paketleri
ROBOT_APT_PACKAGES=(
  python3-colcon-common-extensions python3-rosdep git
  ros-jazzy-rmw-cyclonedds-cpp
  ros-jazzy-ros2-control ros-jazzy-ros2-controllers ros-jazzy-ros2controlcli
  ros-jazzy-ros2-control-cmake
  ros-jazzy-twist-mux ros-jazzy-robot-localization ros-jazzy-imu-filter-madgwick
  ros-jazzy-xacro ros-jazzy-robot-state-publisher
  ros-jazzy-web-video-server ros-jazzy-rosbridge-server ros-jazzy-cv-bridge
)

log()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[!] %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m[x] %s\033[0m\n' "$*"; exit 1; }

check_os() {
  log "Isletim sistemi kontrolu"
  . /etc/os-release
  [ "$VERSION_CODENAME" = "noble" ] || die "Ubuntu 24.04 (noble) gerekli, bulunan: $PRETTY_NAME"
  [ -f "/opt/ros/$ROS_DISTRO_NAME/setup.bash" ] || die "ROS 2 Jazzy kurulu degil: https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html"
  echo "$PRETTY_NAME, $(dpkg --print-architecture), ROS 2 $ROS_DISTRO_NAME"
}

apt_install() {
  log "apt paketleri: $*"
  sudo apt-get update -qq
  sudo apt-get install -y "$@"
}

source_ros() {
  # ROS setup betikleri 'set -u' ile uyumlu değil
  set +u
  # shellcheck disable=SC1090
  source "/opt/ros/$ROS_DISTRO_NAME/setup.bash"
}

# diff_drive_controller 4.42.1 (apt) komut yokken "Velocity command timed out" uyarısını
# saniyede bir basıyor; upstream jazzy dalı sadece geçişte basıyor. apt'de daha yeni
# sürüm çıkınca bu overlay silinmeli (docs/SETUP.md).
build_deps_overlay() {
  local apt_ver
  apt_ver=$(dpkg-query -W -f='${Version}' ros-jazzy-diff-drive-controller 2>/dev/null | cut -d- -f1)
  if [ -n "$apt_ver" ] && dpkg --compare-versions "$apt_ver" gt 4.42.1; then
    warn "apt diff_drive_controller $apt_ver > 4.42.1: overlay gereksiz, atlaniyor ($DEPS_WS silinebilir)"
    return
  fi
  log "diff_drive_controller overlay: $DEPS_WS"
  mkdir -p "$DEPS_WS/src"
  if [ ! -d "$DEPS_WS/src/ros2_controllers" ]; then
    git clone --depth 1 --filter=blob:none --sparse -b jazzy \
      https://github.com/ros-controls/ros2_controllers.git "$DEPS_WS/src/ros2_controllers"
    git -C "$DEPS_WS/src/ros2_controllers" sparse-checkout set diff_drive_controller
  fi
  (
    source_ros
    cd "$DEPS_WS"
    colcon build --cmake-args -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release
  )
}

# Workspace'i overlay'in üstüne derler. $1: workspace kökü, kalanlar: ek colcon argümanları
build_workspace() {
  local ws="$1"; shift
  log "workspace derleniyor: $ws"
  (
    source_ros
    # shellcheck disable=SC1091
    [ -f "$DEPS_WS/install/setup.bash" ] && source "$DEPS_WS/install/setup.bash"
    cd "$ws"
    colcon build "$@"
  )
}

# ~/.bashrc içinde işaretli bir blok yazar; tekrar çalıştırınca bloğu günceller.
# $1: blok içeriği
write_bashrc_block() {
  local begin='# >>> ugv_ros (tools/setup) >>>' end='# <<< ugv_ros (tools/setup) <<<'
  log "~/.bashrc guncelleniyor"
  touch ~/.bashrc
  if grep -qF "$begin" ~/.bashrc; then
    sed -i "\|$begin|,\|$end|d" ~/.bashrc
  fi
  # Sondaki boş satırları at ($(...) kırpar), sonra bloğu tek boş satırla ekle
  local body
  body="$(cat ~/.bashrc)"
  printf '%s\n\n%s\n%s\n%s\n' "$body" "$begin" "$1" "$end" > ~/.bashrc
  echo "$1"
}

# CycloneDDS: aynı ağdaki PC ve robotun birbirini bulması için unicast peer listesi
write_cyclonedds_config() {
  local peer="$1" dest="$HOME/cyclonedds.xml"
  if [ -f "$dest" ]; then
    warn "$dest zaten var, dokunulmadi (peer'ler: $(grep -o 'address="[^"]*"' "$dest" | tr '\n' ' '))"
    return
  fi
  log "$dest olusturuluyor (peer: $peer)"
  sed "s|PEER_ADDRESS|$peer|" "$REPO_ROOT/tools/setup/cyclonedds.xml.template" > "$dest"
}
