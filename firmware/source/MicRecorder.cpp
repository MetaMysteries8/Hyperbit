#include "MicRecorder.h"

using namespace codal;

static uint8_t MIC_RING[HYPERBIT_MIC_RING_BYTES];

MicRecorder::MicRecorder(DataSource &source) :
    upstream(source),
    recording(false),
    overflow(false),
    head(0),
    tail(0),
    audioLevel(0),
    sampleCount(0),
    halfNibble(false),
    pendingByte(0)
{
    source.connect(*this);

    // Do NOT keep the microphone pipeline permanently requested.
    source.dataWanted(DATASTREAM_NOT_WANTED);
}

void MicRecorder::start() {
    recording = false;
    head = 0;
    tail = 0;
    audioLevel = 0;
    sampleCount = 0;
    overflow = false;
    halfNibble = false;
    pendingByte = 0;
    adpcm.reset();

    recording = true;
    upstream.dataWanted(DATASTREAM_WANTED);
}

void MicRecorder::stop() {
    recording = false;
    upstream.dataWanted(DATASTREAM_NOT_WANTED);
    audioLevel = 0;

    if (halfNibble) {
        if (!pushByte(pendingByte))
            overflow = true;
        halfNibble = false;
    }
}

bool MicRecorder::pushByte(uint8_t value) {
    uint16_t next = (head + 1) % HYPERBIT_MIC_RING_BYTES;
    if (next == tail)
        return false;

    MIC_RING[head] = value;
    head = next;
    return true;
}

int MicRecorder::available() const {
    uint16_t h = head;
    uint16_t t = tail;
    if (h >= t)
        return h - t;
    return HYPERBIT_MIC_RING_BYTES - t + h;
}

int MicRecorder::read(uint8_t *out, int maxLen) {
    if (!out || maxLen <= 0)
        return 0;

    int count = 0;
    while (count < maxLen && tail != head) {
        out[count++] = MIC_RING[tail];
        tail = (tail + 1) % HYPERBIT_MIC_RING_BYTES;
    }
    return count;
}

int MicRecorder::pullRequest() {
    ManagedBuffer b = upstream.pull();
    if (!recording)
        return DEVICE_OK;

    int peak = 0;

    for (int i = 0; i < b.length(); ++i) {
        int8_t s8 = (int8_t)b[i];
        int mag = s8 < 0 ? -((int)s8) : (int)s8;
        if (mag > peak) peak = mag;

        int16_t sample = ((int16_t)s8) << 8;
        uint8_t nibble = adpcm.encode(sample);

        if (!halfNibble) {
            pendingByte = nibble & 0x0F;
            halfNibble = true;
        } else {
            if (!pushByte(pendingByte | ((nibble & 0x0F) << 4)))
                overflow = true;
            halfNibble = false;
        }

        if (sampleCount < 0x7FFFFF)
            ++sampleCount;
    }

    int mapped = peak * 2;
    if (mapped > 255) mapped = 255;
    // Fast attack, slower release keeps the blob readable instead of flickering.
    if (mapped > audioLevel)
        audioLevel = (uint8_t)mapped;
    else
        audioLevel = (uint8_t)((audioLevel * 3 + mapped) / 4);

    return DEVICE_OK;
}
