#pragma once

#include <string>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>

class UartDriver {
public:
    UartDriver() : fd_(-1) {}
    ~UartDriver() { close_port(); }

    // POSIX: Initializes raw 8N1 serial communication
    bool open_port(const std::string &device, int baudrate) {
        close_port();

        fd_ = open(device.c_str(), O_RDWR | O_NOCTTY | O_NDELAY);
        if (fd_ < 0) return false;

        // Apply blocking mode with timeout
        fcntl(fd_, F_SETFL, 0);

        struct termios tty;
        if (tcgetattr(fd_, &tty) != 0) {
            close_port();
            return false;
        }

        speed_t speed = B115200;
        if (baudrate == 9600) speed = B9600;
        else if (baudrate == 57600) speed = B57600;
        else if (baudrate == 460800) speed = B460800;
        else if (baudrate == 921600) speed = B921600;

        cfsetospeed(&tty, speed);
        cfsetispeed(&tty, speed);

        // Configure standard 8N1 raw mode
        tty.c_cflag &= ~PARENB;
        tty.c_cflag &= ~CSTOPB;
        tty.c_cflag &= ~CSIZE;
        tty.c_cflag |= CS8;
        tty.c_cflag &= ~CRTSCTS;
        tty.c_cflag |= (CREAD | CLOCAL);

        tty.c_lflag &= ~(ICANON | ECHO | ECHOE | ISIG);
        tty.c_iflag &= ~(IXON | IXOFF | IXANY | IGNBRK | BRKINT | PARMRK | ISTRIP | INLCR | IGNCR | ICRNL);
        tty.c_oflag &= ~OPOST;

        tty.c_cc[VMIN] = 0;   // Non-blocking read limit
        tty.c_cc[VTIME] = 1;  // 100 ms timeout

        if (tcsetattr(fd_, TCSANOW, &tty) != 0) {
            close_port();
            return false;
        }

        return true;
    }

    void close_port() {
        if (fd_ >= 0) {
            close(fd_);
            fd_ = -1;
        }
    }

    bool is_open() const { return fd_ >= 0; }

    // IO: Transmits raw bytes over serial interface
    bool write_bytes(const uint8_t *data, size_t size) {
        if (fd_ < 0) return false;
        return write(fd_, data, size) == static_cast<ssize_t>(size);
    }

    // IO: Reads raw bytes; returns number of bytes read
    ssize_t read_byte(uint8_t &byte) {
        if (fd_ < 0) return -1;
        return read(fd_, &byte, 1);
    }

private:
    int fd_;
};