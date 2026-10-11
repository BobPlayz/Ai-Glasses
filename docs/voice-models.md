# Offline voice assets

Setup caches two Piper neural voices locally:
- English: en_US-lessac-medium
- Telugu (India): te_IN-maya-medium

Voice files are downloaded from the Piper voice catalogue and are not committed to this repository. The Telugu model card identifies the voice as Telugu (India), medium quality, trained from the IIT Madras IndicTTS dataset. Review the model card and its dataset license if redistributing the model or presenting the project outside the school exhibition.

At runtime, the assistant selects the Telugu voice when the response contains Telugu-script characters and the English voice otherwise. If Piper fails, Windows SAPI is tried, then eSpeak NG if installed. If all speech engines fail, the answer remains visible as text.

Models are loaded locally from models/tts. No cloud speech service is used.
