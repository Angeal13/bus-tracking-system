# GPIO Button Wiring Guide

## Components Needed:
- 2x Momentary push buttons
- 2x 10kΩ resistors (for pull-up)
- Breadboard and jumper wires

## Wiring Diagram:

### Advance Button (GPIO17):
- Button pin 1 → GPIO17 (BCM)
- Button pin 2 → GND (with 10kΩ resistor to 3.3V for pull-up)

### Exit Button (GPIO27):
- Button pin 1 → GPIO27 (BCM)  
- Button pin 2 → GND (with 10kΩ resistor to 3.3V for pull-up)

## Physical Pin Numbers:
- GPIO17 = Physical Pin 11
- GPIO27 = Physical Pin 13
- 3.3V = Physical Pin 1 or 17
- GND = Physical Pin 6, 9, 14, 20, 25, 30, 34, or 39

## Alternative Pins:
You can change the GPIO pins in the code:
```python
self.advance_pin = 17  # Change to any free GPIO pin
self.exit_pin = 27     # Change to any free GPIO pin
