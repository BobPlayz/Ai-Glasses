# Hardware selection checklist

## Candidate selected for software targeting
Seeed Studio XIAO ESP32-S3 Sense with its camera/microphone expansion board is the current firmware target, but it is not confirmed purchased or tested. Verify the exact product listing, board revision, and inclusion of the Sense expansion before ordering.

## Candidate pin assumptions
- Camera pins follow the candidate XIAO ESP32-S3 Sense pin map.
- Onboard PDM microphone: GPIO 41 data, GPIO 42 clock.
- Privacy switch input: GPIO 2 to GND, using internal pull-up.
- Capture indicator: GPIO 21 through an appropriate current-limiting resistor. GPIO 21 also has board-specific functions; verify conflicts on the exact expansion board and do not use the microSD interface in this prototype.
- The camera is initialized only when both dashboard permission and the physical switch are enabled.

These are source-based candidate mappings, not proof that a particular purchased unit works.

## Build and safety
- Prototype on USB power first. Do not improvise lithium battery wiring or charging.
- Use a removable mount so the board can be removed from the glasses frame.
- Get an experienced adult/electronics helper to verify wiring before power-up.
- The switch is read by firmware and prevents capture; it is not an electrical camera power disconnect. If the exhibition requires power isolation, have a qualified helper review a suitable power-gating circuit.
- Keep the board near the laptop, as planned. Device and laptop communicate over trusted local Wi-Fi.
- The laptop's built-in speakers are the initial speech output; no additional speaker is required.

## Budget discipline
Total budget: ₹3,000–₹6,000. Check the board plus camera/microphone expansion, delivery, switch, indicator/resistor, USB cable, frame mount, and wiring together before purchasing. Do not order a board listing that omits the required expansion.
