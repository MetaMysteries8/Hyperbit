#include "MicRecorder.h"

using namespace codal;

static uint8_t MIC_BUFFER[HYPERBIT_MAX_MIC_ADPCM];

MicRecorder::MicRecorder(DataSource &source) : upstream(source), recording(false), full(false), encodedLen(0), sampleCount(0), halfNibble(false), pendingByte(0) {
    source.connect(*this);
    source.dataWanted(DATASTREAM_WANTED);
}

void MicRecorder::start() {
    recording = false;
    encodedLen = 0;
    sampleCount = 0;
    full = false;
    halfNibble = false;
    pendingByte = 0;
    adpcm.reset();
    recording = true;
}

void MicRecorder::stop() {
    recording = false;
    if (halfNibble && encodedLen < HYPERBIT_MAX_MIC_ADPCM) {
        MIC_BUFFER[encodedLen++] = pendingByte;
        halfNibble = false;
    }
}

const uint8_t *MicRecorder::data() const { return MIC_BUFFER; }

int MicRecorder::pullRequest() {
    ManagedBuffer b = upstream.pull();
    if (!recording || full) return DEVICE_OK;
    for (int i = 0; i < b.length(); i++) {
        int8_t s8 = (int8_t)b[i];
        int16_t sample = ((int16_t)s8) << 8;
        uint8_t nibble = adpcm.encode(sample);
        if (!halfNibble) {
            pendingByte = nibble & 0x0F;
            halfNibble = true;
        } else {
            if (encodedLen >= HYPERBIT_MAX_MIC_ADPCM) {
                full = true;
                recording = false;
                break;
            }
            MIC_BUFFER[encodedLen++] = pendingByte | ((nibble & 0x0F) << 4);
            halfNibble = false;
        }
        if (sampleCount < 65535) sampleCount++;
    }
    return DEVICE_OK;
}
