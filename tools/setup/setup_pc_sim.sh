#!/bin/bash
# Geliştirme PC'si (Windows 11 + WSL2 Ubuntu 24.04) için simülasyon ortamı kurulumu.
# Tekrar çalıştırmak güvenlidir. Ayrıntılar: docs/SETUP.md
#
# Kullanım (WSL içinden, repo nerede olursa olsun):
#   bash tools/setup/setup_pc_sim.sh [--peer <robot-ip>] [--ws <workspace>]
#
#   --peer  CycloneDDS için robotun IP'si (varsayılan 192.168.1.155)
#   --ws    Linux dosya sistemindeki workspace (varsayılan ~/ugv_ws); src/ buradan
#           repodaki src/ klasörüne symlink olur, derleme çıktıları Linux diskinde kalır.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

PEER=192.168.1.155
WS="$HOME/ugv_ws"
while [ $# -gt 0 ]; do
  case "$1" in
    --peer) PEER="$2"; shift 2 ;;
    --ws)   WS="$2"; shift 2 ;;
    *) die "bilinmeyen arguman: $1" ;;
  esac
done

SIM_APT_PACKAGES=(
  ros-jazzy-ros-gz ros-jazzy-gz-ros2-control
  ros-jazzy-joint-state-publisher-gui ros-jazzy-rviz2 ros-jazzy-tf2-tools
)

check_os
apt_install "${ROBOT_APT_PACKAGES[@]}" "${SIM_APT_PACKAGES[@]}"
build_deps_overlay

log "workspace: $WS (src -> $REPO_ROOT/src)"
mkdir -p "$WS"
if [ -L "$WS/src" ]; then
  [ "$(readlink -f "$WS/src")" = "$(readlink -f "$REPO_ROOT/src")" ] || \
    die "$WS/src baska bir yere isaret ediyor: $(readlink "$WS/src")"
elif [ -e "$WS/src" ]; then
  die "$WS/src symlink degil; tasiyin ya da --ws ile baska bir yer verin"
else
  ln -s "$REPO_ROOT/src" "$WS/src"
fi
build_workspace "$WS"

write_cyclonedds_config "$PEER"
write_bashrc_block "source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file://\$HOME/cyclonedds.xml
# WSL: GPU'suz yazılım render (Gazebo sensörleri ve arayüzü)
export LIBGL_ALWAYS_SOFTWARE=1
# Workspace (overlay'i ve /opt/ros'u zincirleme yükler)
[ -f $WS/install/setup.bash ] && source $WS/install/setup.bash"

log "Tamam. Yeni bir terminal acip calistirin:"
echo "  ros2 launch ugv_gazebo sim.launch.py"
