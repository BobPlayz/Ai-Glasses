# Voice assets and defaults

## Online neural speech
A fresh setup defaults to online neural TTS:
- English: `en-US-AvaNeural`
- Telugu: `te-IN-ShrutiNeural`

This mode requires internet and sends the text being spoken to the online speech provider. It is controlled independently from Gen Z wording in Settings → Voice & wake phrase.

## Offline fallback
The project setup expects cached Piper assets:
- English: `en_GB-alan-medium`
- Telugu (India): `te_IN-venkatesh-medium`

Voice files are downloaded during setup and are not committed to this repository. If online synthesis fails, the code attempts local Piper speech; English may fall back to an installed Windows speech voice. Verify both language paths before the exhibition.

## Offline rehearsal
Disable Natural online voice in Settings, test English and Telugu output, then disconnect the internet and repeat the demo. Do not describe the whole speech path as offline while the online voice toggle is enabled.
