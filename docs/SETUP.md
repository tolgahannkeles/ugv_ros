# Ortam Kurulumu

Bu projenin çalıştığı iki makinenin kurulumu, neden böyle kurulduğu ve karşılaşılan sorunların çözümleri.

| | Geliştirme PC'si (simülasyon) | Robot |
|---|---|---|
| Donanım | Windows 11 + WSL2 | Raspberry Pi 5 + ESP32 (UART) |
| İşletim sistemi | Ubuntu 24.04 (WSL) | Ubuntu 24.04 arm64 |
| Workspace | `~/ugv_ws` (`src` → repodaki `src/`'ye symlink) | Repo kökü: `~/ugv_ros` |
| Çalıştırma | `ros2 launch ugv_gazebo sim.launch.py` | `ros2 launch ugv_bringup robot.launch.py` |
| IP (yerel ağ) | 192.168.1.105 | 192.168.1.155 |

## Hızlı kurulum

Her iki betik de tekrar çalıştırılabilir: eksikleri kurar, workspace'i derler, `~/.bashrc`'yi günceller.

**PC (WSL içinden):**
```bash
bash /mnt/c/Users/<kullanici>/Desktop/projects/ugv_ros/tools/setup/setup_pc_sim.sh --peer 192.168.1.155
```

**Robot (Pi'de, repo kökünden):**
```bash
cd ~/ugv_ros && git pull
bash tools/setup/setup_robot.sh --peer 192.168.1.105
```

Betikten sonra **yeni bir terminal açın**. Eski terminaller eski ortam değişkenlerini tutar (bkz. [Sorunlar](#sorunlar-ve-çözümleri)).

Kod değiştikten sonra sadece derlemek yeterli:
```bash
cd ~/ugv_ws && colcon build                                                   # PC
cd ~/ugv_ros && colcon build --packages-up-to ugv_bringup --parallel-workers 2   # Pi
```

## Ne kuruluyor, neden

### ROS 2 Jazzy ve paketler

ROS 2 Jazzy'nin kendisi betiklerin dışında kurulur ([resmi kurulum](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html)). Betikler üzerine şunları kurar:

| Grup | Paketler | Nerede |
|---|---|---|
| Derleme | `python3-colcon-common-extensions`, `python3-rosdep`, `git` | ikisi |
| İletişim | `ros-jazzy-rmw-cyclonedds-cpp` | ikisi |
| Kontrol | `ros2-control`, `ros2-controllers`, `ros2controlcli`, `ros2-control-cmake`, `twist-mux` | ikisi |
| Konum | `robot-localization`, `imu-filter-madgwick` | ikisi |
| Model | `xacro`, `robot-state-publisher` | ikisi |
| Web | `web-video-server`, `rosbridge-server`, `cv-bridge` | ikisi |
| Simülasyon | `ros-gz`, `gz-ros2-control`, `joint-state-publisher-gui`, `rviz2`, `tf2-tools` | sadece PC |
| Kamera | `camera_ros` (kaynaktan, Raspberry Pi libcamera ile) | sadece Pi, **betik kurmaz** |

`ros2-control-cmake` doğrudan kullanılmaz, ama aşağıdaki overlay onsuz derlenmez. Pi'deki ros2_control kurulumuyla birlikte gelmedi.

`rosdep` yerine doğrudan apt kullanılır. `rosdep install` Gazebo'yu da (`ugv_gazebo`) çekmeye çalışır ve `--packages-up-to` seçeneği yoktur.

### `diff_drive_controller` overlay'i (`~/ugv_deps_ws`)

apt'deki `ros-jazzy-diff-drive-controller` **4.42.1**, komut gelmediği sürece `Velocity command timed out. Braking.` uyarısını her saniye basar. Upstream `jazzy` dalında bu düzeltildi (uyarı sadece zaman aşımına girişte bir kez basılır), ama henüz apt'ye çıkmadı. Bu yüzden sadece bu paket kaynaktan, ayrı bir workspace'te derlenir:

```
/opt/ros/jazzy  →  ~/ugv_deps_ws (diff_drive_controller)  →  ~/ugv_ws veya ~/ugv_ros
```

- Sıra önemlidir: proje workspace'i, overlay source edilmişken derlenmelidir. Betikler bunu kendisi yapar.
- Kontrol: `ros2 pkg prefix diff_drive_controller` → `.../ugv_deps_ws/...` göstermeli.
- **Kaldırma:** apt'de 4.42.1'den yeni bir sürüm çıkınca `rm -rf ~/ugv_deps_ws`, sonra proje workspace'ini `rm -rf build install log` ile temizleyip yeniden derleyin. Betikler apt sürümü yeterince yeniyse overlay'i zaten atlar.

### Workspace düzeni

- **PC:** Kod Windows tarafında (`C:\...\ugv_ros`), derleme Linux diskinde (`~/ugv_ws`). `~/ugv_ws/src` repodaki `src/`'ye symlink'tir. `/mnt/c` altında derlemek çok yavaştır ve colcon'un symlink/izin işlemleri orada bozulur.
- **Pi:** Repo kökü aynı zamanda workspace'tir (`~/ugv_ros/{src,build,install,log}`). Pi'de bellek sınırlı olduğu için `--parallel-workers 2` ile ve sadece robot paketleri (`--packages-up-to ugv_bringup`) derlenir.

### `~/.bashrc`

Betikler `# >>> ugv_ros (tools/setup) >>>` işaretli bir blok yazar ve tekrar çalıştırınca bu bloğu günceller:

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file://$HOME/cyclonedds.xml
export LIBGL_ALWAYS_SOFTWARE=1          # sadece PC (WSL'de GPU'suz render)
[ -f <workspace>/install/setup.bash ] && source <workspace>/install/setup.bash
```

Workspace'in `install/setup.bash` dosyası overlay'i ve `/opt/ros`'u zincirleme yükler; ayrıca source etmeye gerek yoktur.

### Ağ: CycloneDDS

- İki makinede de `ROS_DOMAIN_ID=42` ve `rmw_cyclonedds_cpp` aynı olmalı.
- `~/cyclonedds.xml`, karşı makineyi unicast peer olarak listeler (PC'de robotun, robotta PC'nin IP'si). Şablon: [tools/setup/cyclonedds.xml.template](../tools/setup/cyclonedds.xml.template). Dosya varsa betik ona dokunmaz.
- WSL `mirrored` ağ modunda çalışır, yani WSL, Windows'un IP'sini kullanır. Windows'ta `C:\Users\<kullanici>\.wslconfig`:
  ```ini
  [wsl2]
  networkingMode=mirrored
  ```
  WSL içinde `/etc/wsl.conf`: `[boot] systemd=true`.

### Robot donanımı (Pi)

- **UART:** `/boot/firmware/config.txt` içinde `dtparam=uart0=on`. `cmdline.txt`'te seri konsol (`console=serial0,...`) olmamalı. ESP32 `/dev/ttyAMA0` (GPIO 14/15), 115200 baud.
- **İzin:** kullanıcı `dialout` grubunda olmalı (betik ekler; oturumu yeniden açın).
- **Gerçek zamanlı:** `/etc/security/limits.d/ros2.conf` → `<kullanici> - rtprio 99`. Yoksa controller_manager sadece "Could not enable FIFO RT scheduling" uyarısı basar, çalışmaya devam eder.
- **Kamera:** `camera_ros`, Pi 5'in RP1-CFE kamera arayüzü için Raspberry Pi'nin libcamera'sıyla kaynaktan derlenir. apt'deki sürüm Pi 5 kamerasını desteklemeyebilir.
- **İlk çalıştırma:** paletler havadayken yapın.

### Yardımcı araçlar (isteğe bağlı)

| Araç | Kurulum | Ne için |
|---|---|---|
| Parkur dönüştürücü ([tools/parkur_to_gazebo.py](../tools/parkur_to_gazebo.py)) | `python3 -m venv ~/.venvs/cad && ~/.venvs/cad/bin/pip install cadquery-ocp trimesh rtree scipy` | TEKNOFEST STEP → Gazebo modeli |
| Engel dedektörü ([tools/pc_obstacle_detector.py](../tools/pc_obstacle_detector.py)) | `pip install ultralytics opencv-python` (PC'de) | Otonom Destek (`/obstacle_zones`) |
| `depth_node` (kapalı) | `pip install onnxruntime` | ONNX derinlik tahmini |

## Test edilmiş sürümler

| Bileşen | Sürüm |
|---|---|
| Ubuntu | 24.04.5 LTS (PC x86_64, Pi arm64) |
| ROS 2 | Jazzy |
| Gazebo | Harmonic 8.15 |
| ros2_control (`hardware_interface`) | 4.48.0 |
| ros2_controllers | 4.42.1 (+ `diff_drive_controller` jazzy dalı overlay) |
| gz_ros2_control | 1.2.20 |
| robot_localization | 3.8.3 |
| twist_mux | 4.5.0 |
| rmw_cyclonedds_cpp | 2.2.4 |

## Sorunlar ve çözümleri

| Belirti | Sebep | Çözüm |
|---|---|---|
| `ros2 topic list` hiçbir şey dönmüyor (`/rosout` bile yok) | Hiç node çalışmıyor ya da `ros2 daemon` takılmış | Launch'ın çalıştığından emin olun; `ros2 daemon stop` |
| Değişiklikler etkisiz, eski davranış (ör. robot joystick'le hareket etmiyor) | Terminal eski ya da yanlış bir `install/` source etmiş (ör. `/mnt/c/.../install`) | Yeni terminal açın; `ros2 pkg prefix ugv_gazebo` doğru workspace'i göstermeli |
| `Velocity command timed out. Braking.` her saniye | Overlay yüklü değil, apt'deki 4.42.1 çalışıyor | `ros2 pkg prefix diff_drive_controller` → `ugv_deps_ws` olmalı; değilse overlay'i kurup workspace'i overlay source'luyken yeniden derleyin, yeni terminal açın |
| Aynı uyarı joystick her bırakıldığında bir kez | Normal: komut akışı bitti, controller fren yaptı | Bir şey yapmaya gerek yok |
| `Could not find ... hardware_interfaceConfig.cmake` | ros2_control kurulu değil | `sudo apt install ros-jazzy-ros2-control ros-jazzy-ros2-controllers` |
| Overlay derlerken `ros2_control_cmakeConfig.cmake` bulunamadı | Upstream dal bu pakete ihtiyaç duyuyor | `sudo apt install ros-jazzy-ros2-control-cmake` |
| `rosdep: error: no such option: --packages-up-to` | O seçenek colcon'a ait | Betikleri ya da doğrudan apt'yi kullanın |
| `colcon: command not found` | colcon pip ile `~/.local/bin`'e kurulmuş, PATH'te değil | `sudo apt install python3-colcon-common-extensions` |
| `rmw_create_node: failed to create domain` / `failed to bind to ANY:17900` | Aynı domain'de (42) çakışan başka bir ROS süreci ya da takılı kalmış bir süreç | Diğer launch'ları kapatın, `ros2 daemon stop`; `ps aux \| grep -E "ros2\|gz sim"` |
| Gazebo: `Unable to resolve uri[model://...] ... does not contain a model.config` | Çalışma dizininde aynı adlı bir klasör var (Gazebo önce oraya bakar) | Model adı `teknofest_ika_parkur` olarak ayrıştırıldı; yeni modellerde de benzersiz ad kullanın |
| Gazebo: `does not support mimic constraints` | Fizik motoru mimic desteklemiyor; tekerleri gz_ros2_control bağlıyor | Zararsız |
| Kapanışta `process has died` / `RCLError ... context is not valid` | Ctrl+C sırasında rclpy kapanış yarışı | Zararsız |
| Simülasyon gerçek zamandan yavaş | WSL'de GPU'suz yazılım render (`LIBGL_ALWAYS_SOFTWARE=1`) | Beklenen davranış; `headless:=true` biraz hızlandırır |
| Gazebo arayüzü açılmıyor | WSLg yok ya da eski | Windows'ta `wsl --update` |
