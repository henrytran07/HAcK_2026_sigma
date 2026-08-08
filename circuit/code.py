import board, time, digitalio, synthio, audiobusio, analogio
import adafruit_matrixkeypad

audio = audiobusio.I2SOut(bit_clock=board.GP12, word_select=board.GP13, data=board.GP11)
synth = synthio.Synthesizer(sample_rate=44100, channel_count=2)
audio.play(synth)

cols = [digitalio.DigitalInOut(x) for x in (board.GP20, board.GP21, board.GP22)]
rows = [digitalio.DigitalInOut(x) for x in (board.GP16, board.GP17, board.GP18, board.GP19)]
keys = ((1, 2, 3),
        (4, 5, 6),
        (7, 8, 9),
        ('*', 0, '#'))

keypad = adafruit_matrixkeypad.Matrix_Keypad(rows, cols, keys)
volume_pot = analogio.AnalogIn(board.A2)
slide_pot = analogio.AnalogIn(board.A1)

# C Major
low_hz = 261.63 # C4
high_hz = 523.25 # C5

def pot_percent(pot, samples=10):
    total = 0
    for x in range(samples):
        total += pot.value
    avg = total / samples
    if avg > 3000:
        return avg / 65535
    else:
        return 0

def lerp(start, end, frac):
    return start + (end - start) * frac

note = synthio.Note(frequency=low_hz)
playing = False

while True:
    hz = lerp(low_hz, high_hz, pot_percent(slide_pot))
    note.frequency = hz
    note.amplitude = pot_percent(volume_pot)

    keys = keypad.pressed_keys
    if 5 in keys:
        if not playing:
            synth.press(note)
            playing = True
    else:
        if playing:
            synth.release(note)
            playing = False

    time.sleep(0.001)