#pragma once

#include <cstdint>
#include <cstddef>
#include <cstring>

// PROTOCOL: Frame delimiters and packet identifiers
constexpr uint8_t FRAME_HEADER1  = 0xAA;
constexpr uint8_t FRAME_HEADER2  = 0x55;
constexpr uint8_t PKT_ID_CMD_VEL = 0x01;
constexpr uint8_t PKT_ID_IMU     = 0x10;
constexpr uint8_t PKT_ID_GPS     = 0x11;

#pragma pack(push, 1)
struct CmdVelPayload {
    float v_left;
    float v_right;
};

struct ImuPayload {
    float ax, ay, az;
    float gx, gy, gz;
    float temp;
};

struct GpsPayload {
    double lat;       // Enlem (ondalık derece) - 8 bayt
    double lon;       // Boylam (ondalık derece) - 8 bayt
    float  alt;       // İrtifa (metre) - 4 bayt
    float  speed;     // Yer hızı (m/s) - 4 bayt
    float  course;    // Rota / Course (derece) - 4 bayt
    float  hdop;      // Yatay hassasiyet çarpanı - 4 bayt
    uint8_t fix;      // 0: Yok, 1: Fix - 1 bayt
    uint8_t sats;     // Uydu sayısı - 1 bayt
};
#pragma pack(pop)

class ProtocolParser {
public:
    enum class State { WAIT_H1, WAIT_H2, WAIT_ID, WAIT_LEN, WAIT_PAYLOAD, WAIT_CRC };

    ProtocolParser() { reset(); }

    // PROTOCOL: XOR-based checksum calculation
    static uint8_t calculate_crc(uint8_t id, uint8_t len, const uint8_t *data) {
        uint8_t crc = id ^ len;
        for (size_t i = 0; i < len; ++i) {
            crc ^= data[i];
        }
        return crc;
    }

    // PARSER: Feeds one byte into the state machine; returns true when a valid frame completes
    bool parse_byte(uint8_t byte, uint8_t &out_id, uint8_t *out_payload, uint8_t &out_len) {
        switch (state_) {
            case State::WAIT_H1:
                if (byte == FRAME_HEADER1) state_ = State::WAIT_H2;
                break;

            case State::WAIT_H2:
                state_ = (byte == FRAME_HEADER2) ? State::WAIT_ID : State::WAIT_H1;
                break;

            case State::WAIT_ID:
                id_ = byte;
                state_ = State::WAIT_LEN;
                break;

            case State::WAIT_LEN:
                len_ = byte;
                index_ = 0;
                if (len_ > sizeof(buffer_)) {
                    // SAFETY: Discard malformed packets exceeding internal buffer
                    reset();
                } else {
                    state_ = (len_ == 0) ? State::WAIT_CRC : State::WAIT_PAYLOAD;
                }
                break;

            case State::WAIT_PAYLOAD:
                buffer_[index_++] = byte;
                if (index_ >= len_) {
                    state_ = State::WAIT_CRC;
                }
                break;

            case State::WAIT_CRC: {
                uint8_t computed_crc = calculate_crc(id_, len_, buffer_);
                if (computed_crc == byte) {
                    out_id = id_;
                    out_len = len_;
                    std::memcpy(out_payload, buffer_, len_);
                    reset();
                    return true;
                }
                reset();
                break;
            }
        }
        return false;
    }

    void reset() {
        state_ = State::WAIT_H1;
        index_ = 0;
        id_ = 0;
        len_ = 0;
    }

private:
    State state_;
    uint8_t id_{0};
    uint8_t len_{0};
    uint8_t index_{0};
    uint8_t buffer_[64];
};