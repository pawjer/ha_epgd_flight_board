# Gdańsk Airport Integration - Advanced Examples

This document provides detailed examples of how to use the Gdańsk Airport integration in various scenarios.

## Table of Contents

- [Dashboard Examples](#dashboard-examples)
- [Automation Examples](#automation-examples)
- [Template Sensor Examples](#template-sensor-examples)
- [Notification Examples](#notification-examples)
- [Scripts Examples](#scripts-examples)

## Dashboard Examples

### Full Airport Dashboard

Complete dashboard showing all airport information:

```yaml
title: Gdańsk Airport
path: airport
icon: mdi:airplane
badges: []
cards:
  # Header Card
  - type: markdown
    content: |
      # ✈️ Port Lotniczy Gdańsk
      {{ state_attr('sensor.gdansk_airport_arrivals', 'last_updated') | as_timestamp | timestamp_custom('%H:%M - %d.%m.%Y') }}
      {% if state_attr('sensor.gdansk_airport_arrivals', 'data_source') == 'cache' %}
      ⚠️ Używam danych z cache ({{ state_attr('sensor.gdansk_airport_arrivals', 'cache_age_minutes') }} min)
      {% else %}
      ✅ Dane na żywo
      {% endif %}

  # Statistics Row
  - type: horizontal-stack
    cards:
      - type: statistic
        entity: sensor.gdansk_airport_arrivals
        name: Przyloty
        icon: mdi:airplane-landing
        stat_type: state
      - type: statistic
        entity: sensor.gdansk_airport_departures
        name: Odloty
        icon: mdi:airplane-takeoff
        stat_type: state

  # Next Flights
  - type: entities
    title: Najbliższe loty
    entities:
      - entity: sensor.gdansk_airport_next_arrival
        name: Następny przylot
        icon: mdi:airplane-landing
      - entity: sensor.gdansk_airport_next_departure
        name: Następny odlot
        icon: mdi:airplane-takeoff

  # Arrivals Board
  - type: markdown
    title: 📥 Tablica przylotów
    content: |
      | Czas | Z | Lot | Linia | Status |
      |------|---|-----|-------|--------|
      {%- for flight in state_attr('sensor.gdansk_airport_arrivals', 'flights')[:15] %}
      | **{{ flight.scheduled_time }}**{% if flight.expected_time %}<br>→ {{ flight.expected_time }}{% endif %} | {{ flight.origin }} | `{{ flight.flight_number }}` | {{ flight.airline }} | {% if flight.status == 'landed' %}✅{% elif flight.status == 'delayed' %}⏰{% elif flight.status == 'cancelled' %}❌{% else %}🛬{% endif %} {{ flight.status | upper }}{% if flight.delay_minutes %}<br>(+{{ flight.delay_minutes }} min){% endif %} |
      {%- endfor %}

  # Departures Board
  - type: markdown
    title: 📤 Tablica odlotów
    content: |
      | Czas | Do | Lot | Linia | Status |
      |------|---|-----|-------|--------|
      {%- for flight in state_attr('sensor.gdansk_airport_departures', 'flights')[:15] %}
      | **{{ flight.scheduled_time }}**{% if flight.expected_time %}<br>→ {{ flight.expected_time }}{% endif %} | {{ flight.destination }} | `{{ flight.flight_number }}` | {{ flight.airline }} | {% if flight.status == 'departed' %}✅{% elif flight.status == 'delayed' %}⏰{% elif flight.status == 'cancelled' %}❌{% elif flight.status == 'boarding' %}🚪{% else %}🛫{% endif %} {{ flight.status | upper }}{% if flight.delay_minutes %}<br>(+{{ flight.delay_minutes }} min){% endif %} |
      {%- endfor %}
```

### Compact Mobile Dashboard

Optimized for mobile devices:

```yaml
type: vertical-stack
cards:
  - type: glance
    title: Lotnisko Gdańsk
    entities:
      - entity: sensor.gdansk_airport_arrivals
        name: Przyloty
      - entity: sensor.gdansk_airport_departures
        name: Odloty

  - type: markdown
    title: Następne loty
    content: |
      {% set next_arr = state_attr('sensor.gdansk_airport_next_arrival', 'origin') %}
      {% set next_dep = state_attr('sensor.gdansk_airport_next_departure', 'destination') %}

      📥 **{{ states('sensor.gdansk_airport_next_arrival') }}** z {{ next_arr }}
      📤 **{{ states('sensor.gdansk_airport_next_departure') }}** do {{ next_dep }}
```

### Filter-Specific Boards

Show only specific airlines or destinations:

```yaml
type: markdown
title: ✈️ Loty Wizz Air
content: |
  | Czas | Kierunek | Lot | Status |
  |------|----------|-----|--------|
  {%- for flight in state_attr('sensor.gdansk_airport_arrivals', 'flights') %}
  {%- if 'WIZZ' in flight.airline %}
  | {{ flight.scheduled_time }} | 📥 {{ flight.origin }} | {{ flight.flight_number }} | {{ flight.status }} |
  {%- endif %}
  {%- endfor %}
  {%- for flight in state_attr('sensor.gdansk_airport_departures', 'flights') %}
  {%- if 'WIZZ' in flight.airline %}
  | {{ flight.scheduled_time }} | 📤 {{ flight.destination }} | {{ flight.flight_number }} | {{ flight.status }} |
  {%- endif %}
  {%- endfor %}
```

## Automation Examples

### Flight Delay Notification

Notify when any flight is delayed:

```yaml
automation:
  - alias: "Airport: Notify on Flight Delays"
    trigger:
      - platform: state
        entity_id: sensor.gdansk_airport_arrivals
      - platform: state
        entity_id: sensor.gdansk_airport_departures
    condition:
      - condition: template
        value_template: >
          {% set arrivals = state_attr('sensor.gdansk_airport_arrivals', 'flights') | default([]) %}
          {% set departures = state_attr('sensor.gdansk_airport_departures', 'flights') | default([]) %}
          {{ (arrivals + departures) | selectattr('status', 'eq', 'delayed') | list | count > 0 }}
    action:
      - service: notify.mobile_app
        data:
          title: "⏰ Opóźnienia na lotnisku"
          message: >
            {% set arrivals = state_attr('sensor.gdansk_airport_arrivals', 'flights') | default([]) %}
            {% set departures = state_attr('sensor.gdansk_airport_departures', 'flights') | default([]) %}
            {% set delayed = (arrivals + departures) | selectattr('status', 'eq', 'delayed') | list %}
            Opóźnione loty:
            {% for flight in delayed[:5] %}
            - {{ flight.flight_number }} {% if flight.origin %}z {{ flight.origin }}{% else %}do {{ flight.destination }}{% endif %} (+{{ flight.delay_minutes }} min)
            {% endfor %}
```

### Track Specific Flight

Monitor a specific flight number:

```yaml
automation:
  - alias: "Airport: Track Flight W6 1706"
    trigger:
      - platform: state
        entity_id: sensor.gdansk_airport_arrivals
    variables:
      my_flight: >
        {% set flights = state_attr('sensor.gdansk_airport_arrivals', 'flights') | default([]) %}
        {{ flights | selectattr('flight_number', 'eq', 'W6 1706') | list | first | default(none) }}
    condition:
      - condition: template
        value_template: "{{ my_flight != none }}"
    action:
      - choose:
          - conditions:
              - condition: template
                value_template: "{{ my_flight.status == 'landed' }}"
            sequence:
              - service: notify.mobile_app
                data:
                  title: "✅ Lot wylądował"
                  message: "{{ my_flight.flight_number }} z {{ my_flight.origin }} wylądował o {{ my_flight.expected_time | default(my_flight.scheduled_time) }}"

          - conditions:
              - condition: template
                value_template: "{{ my_flight.status == 'delayed' }}"
            sequence:
              - service: notify.mobile_app
                data:
                  title: "⏰ Lot opóźniony"
                  message: "{{ my_flight.flight_number }} z {{ my_flight.origin }} opóźniony o {{ my_flight.delay_minutes }} minut"
```

### Airport Busy Hour Alert

Alert when airport is busy (many flights):

```yaml
automation:
  - alias: "Airport: Busy Hour Alert"
    trigger:
      - platform: state
        entity_id: sensor.gdansk_airport_arrivals
      - platform: state
        entity_id: sensor.gdansk_airport_departures
    condition:
      - condition: template
        value_template: >
          {{ states('sensor.gdansk_airport_arrivals') | int + states('sensor.gdansk_airport_departures') | int > 30 }}
    action:
      - service: notify.mobile_app
        data:
          title: "🛫 Ruch na lotnisku"
          message: "Lotnisko jest zajęte: {{ states('sensor.gdansk_airport_arrivals') }} przylotów + {{ states('sensor.gdansk_airport_departures') }} odlotów"
```

## Template Sensor Examples

### Count Delayed Flights

```yaml
template:
  - sensor:
      - name: "Airport Delayed Flights"
        unique_id: airport_delayed_flights
        icon: mdi:clock-alert
        state: >
          {% set arrivals = state_attr('sensor.gdansk_airport_arrivals', 'flights') | default([]) %}
          {% set departures = state_attr('sensor.gdansk_airport_departures', 'flights') | default([]) %}
          {{ (arrivals + departures) | selectattr('status', 'eq', 'delayed') | list | count }}
```

### Next Flight to Specific City

```yaml
template:
  - sensor:
      - name: "Next Flight to Warsaw"
        unique_id: next_flight_to_warsaw
        icon: mdi:airplane-takeoff
        state: >
          {% set flights = state_attr('sensor.gdansk_airport_departures', 'flights') | default([]) %}
          {% set warsaw = flights | selectattr('destination', 'search', 'Warszawa') | list %}
          {% if warsaw | count > 0 %}
            {{ warsaw[0].scheduled_time }}
          {% else %}
            unavailable
          {% endif %}
        attributes:
          flight_number: >
            {% set flights = state_attr('sensor.gdansk_airport_departures', 'flights') | default([]) %}
            {% set warsaw = flights | selectattr('destination', 'search', 'Warszawa') | list %}
            {{ warsaw[0].flight_number if warsaw | count > 0 else none }}
          airline: >
            {% set flights = state_attr('sensor.gdansk_airport_departures', 'flights') | default([]) %}
            {% set warsaw = flights | selectattr('destination', 'search', 'Warszawa') | list %}
            {{ warsaw[0].airline if warsaw | count > 0 else none }}
```

### Average Delay Time

```yaml
template:
  - sensor:
      - name: "Airport Average Delay"
        unique_id: airport_average_delay
        icon: mdi:timer-sand
        unit_of_measurement: "min"
        state: >
          {% set arrivals = state_attr('sensor.gdansk_airport_arrivals', 'flights') | default([]) %}
          {% set departures = state_attr('sensor.gdansk_airport_departures', 'flights') | default([]) %}
          {% set delayed = (arrivals + departures) | selectattr('delay_minutes', 'ne', none) | map(attribute='delay_minutes') | list %}
          {{ (delayed | sum / (delayed | count)) | round(0) if delayed | count > 0 else 0 }}
```

## Notification Examples

### Daily Airport Summary

```yaml
automation:
  - alias: "Airport: Daily Summary"
    trigger:
      - platform: time
        at: "20:00:00"
    action:
      - service: notify.mobile_app
        data:
          title: "✈️ Podsumowanie z lotniska"
          message: >
            Dzisiaj na lotnisku:
            📥 Przyloty: {{ states('sensor.gdansk_airport_arrivals') }}
            📤 Odloty: {{ states('sensor.gdansk_airport_departures') }}

            {% if state_attr('sensor.gdansk_airport_arrivals', 'data_source') == 'cache' %}
            ⚠️ Dane z cache ({{ state_attr('sensor.gdansk_airport_arrivals', 'cache_age_minutes') }} min)
            {% endif %}
```

### Cancelled Flight Alert

```yaml
automation:
  - alias: "Airport: Cancelled Flight Alert"
    trigger:
      - platform: state
        entity_id: sensor.gdansk_airport_arrivals
      - platform: state
        entity_id: sensor.gdansk_airport_departures
    condition:
      - condition: template
        value_template: >
          {% set arrivals = state_attr('sensor.gdansk_airport_arrivals', 'flights') | default([]) %}
          {% set departures = state_attr('sensor.gdansk_airport_departures', 'flights') | default([]) %}
          {{ (arrivals + departures) | selectattr('status', 'eq', 'cancelled') | list | count > 0 }}
    action:
      - service: persistent_notification.create
        data:
          title: "❌ Odwołany lot"
          message: >
            {% set arrivals = state_attr('sensor.gdansk_airport_arrivals', 'flights') | default([]) %}
            {% set departures = state_attr('sensor.gdansk_airport_departures', 'flights') | default([]) %}
            {% set cancelled = (arrivals + departures) | selectattr('status', 'eq', 'cancelled') | list %}
            Odwołane loty:
            {% for flight in cancelled %}
            - {{ flight.flight_number }} {% if flight.origin %}z {{ flight.origin }}{% else %}do {{ flight.destination }}{% endif %}
            {% endfor %}
```

## Scripts Examples

### Check Flight Status Script

```yaml
script:
  check_flight_status:
    alias: "Check Flight Status"
    icon: mdi:airplane-search
    fields:
      flight_number:
        description: "Flight number to check (e.g., W6 1706)"
        example: "W6 1706"
    sequence:
      - variables:
          arrivals: "{{ state_attr('sensor.gdansk_airport_arrivals', 'flights') | default([]) }}"
          departures: "{{ state_attr('sensor.gdansk_airport_departures', 'flights') | default([]) }}"
          all_flights: "{{ arrivals + departures }}"
          found: "{{ all_flights | selectattr('flight_number', 'eq', flight_number) | list | first | default(none) }}"
      - choose:
          - conditions:
              - condition: template
                value_template: "{{ found != none }}"
            sequence:
              - service: notify.mobile_app
                data:
                  title: "✈️ Status lotu {{ flight_number }}"
                  message: >
                    Lot: {{ found.flight_number }}
                    {% if found.origin %}Z: {{ found.origin }}{% else %}Do: {{ found.destination }}{% endif %}
                    Linia: {{ found.airline }}
                    Zaplanowany: {{ found.scheduled_time }}
                    {% if found.expected_time %}Oczekiwany: {{ found.expected_time }}{% endif %}
                    Status: {{ found.status | upper }}
                    {% if found.delay_minutes %}Opóźnienie: {{ found.delay_minutes }} min{% endif %}
        default:
          - service: notify.mobile_app
            data:
              title: "❓ Lot nieznaleziony"
              message: "Lot {{ flight_number }} nie został znaleziony w systemie"
```

### Refresh Integration Script

```yaml
script:
  refresh_airport_data:
    alias: "Refresh Airport Data"
    icon: mdi:refresh
    sequence:
      - service: homeassistant.update_entity
        target:
          entity_id:
            - sensor.gdansk_airport_arrivals
            - sensor.gdansk_airport_departures
      - delay: "00:00:02"
      - service: persistent_notification.create
        data:
          title: "✅ Dane odświeżone"
          message: >
            Dane lotniska zostały odświeżone.
            Status: {{ state_attr('sensor.gdansk_airport_arrivals', 'data_source') | upper }}
```

## Advanced Use Cases

### Integration with Google Calendar

Create calendar events for flights:

```yaml
automation:
  - alias: "Airport: Add Flight to Calendar"
    trigger:
      - platform: state
        entity_id: sensor.gdansk_airport_next_departure
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.state != trigger.from_state.state }}"
    action:
      - service: calendar.create_event
        target:
          entity_id: calendar.flights
        data:
          summary: "Flight {{ state_attr('sensor.gdansk_airport_next_departure', 'flight_number') }}"
          description: >
            Destination: {{ state_attr('sensor.gdansk_airport_next_departure', 'destination') }}
            Airline: {{ state_attr('sensor.gdansk_airport_next_departure', 'airline') }}
            Status: {{ state_attr('sensor.gdansk_airport_next_departure', 'status') }}
          start_date_time: "{{ today_at(states('sensor.gdansk_airport_next_departure')) }}"
```

### Voice Announcement

Announce flight status via TTS:

```yaml
automation:
  - alias: "Airport: Announce Next Departure"
    trigger:
      - platform: time_pattern
        hours: "/1"
    action:
      - service: tts.google_translate_say
        target:
          entity_id: media_player.living_room
        data:
          message: >
            Następny odlot z lotniska w Gdańsku to lot {{ state_attr('sensor.gdansk_airport_next_departure', 'flight_number') }}
            do {{ state_attr('sensor.gdansk_airport_next_departure', 'destination') }}
            o godzinie {{ states('sensor.gdansk_airport_next_departure') }}.
            Status lotu: {{ state_attr('sensor.gdansk_airport_next_departure', 'status') }}.
```

---

For more information, see the [main README](README.md).
