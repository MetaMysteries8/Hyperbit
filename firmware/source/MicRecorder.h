#pragma once
#include "MicroBit.h"
#include "DataStream.h"
#include "ImaAdpcm.h"

#define HYPERBIT_MAX_MIC_ADPCM 16000

class MicRecorder : public codal::DataSink {
    codal::DataSource &upstream;
    volatile bool recording;
    volatile bool full;
    uint16_t encodedLen;
    uint16_t sampleCount;
    bool halfNibble;
    uint8_t pendingByte;
    ImaAdpcmState adpcm;

public:
    MicRecorder(codal::DataSource &source);
    virtual int pullRequest();
    void start();
    void stop();
    bool isRecording() const { return recording; }
    bool overflowed() const { return full; }
    uint16_t length() const { return encodedLen; }
    uint16_t samples() const { return sampleCount; }
    const uint8_t *data() const;
};
