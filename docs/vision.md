# Local vision integration

The local vision adapter sends one supplied image to the Ollama service on loopback. It does not access a camera or capture images itself.

- Candidate model: moondream:1.8b. Verify the exact model tag and download it while online before relying on it offline.
- Images are limited to 8 MB per request.
- The device layer must enforce the physical privacy switch and show a capture indicator before providing any frame to this module.
- The physical board and transport endpoint are not implemented yet.
- Vision latency and model quality must be tested on the actual laptop. The 8 GB RAM system may need sequential model loading.
