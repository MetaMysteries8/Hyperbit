#pragma once
#include "MicroBit.h"
#include "DataStream.h"
#include "ImaAdpcm.h"

// Audio is drained continuously while the logo is held. Keeping this ring small
// leaves materially more heap/stack headroom for the BLE SoftDevice at runtime.
#define HYPERBIT_MIC_RING_BYTES 512

class MicRecorder : public codal::DataSink {
    codal::DataSource &upstream;
    volatile bool recording;
    volatile bool overflow;
    volatile uint16_t head;
    volatile uint16_t tail;
    volatile uint8_t audioLevel;
    uint32_t sampleCount;
    bool halfNibble;
    uint8_t pendingByte;
    ImaAdpcmState adpcm;

    bool pushByte(uint8_t value);

public:
    explicit MicRecorder(codal::DataSource &source);
    virtual int pullRequest();

    void start();
    void stop();

    bool isRecording() const { return recording; }
    bool overflowed() const { return overflow; }
    uint32_t samples() const { return sampleCount; }
    uint8_t level() const { return audioLevel; }

    int available() const;
    int read(uint8_t *out, int maxLen);
    void markTransportOverflow() { overflow = true; }
};
