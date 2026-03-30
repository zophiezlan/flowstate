# FlowState v1 Consolidation Spec Pack
_Last updated: 2026-03-30 (Australia/Sydney)_

## Purpose

This document is the ground-truth product and architecture specification for refactoring FlowState into a simpler, clearer v1.

It exists to stop architectural drift and prevent AI coding agents from making assumptions that expand scope or reintroduce complexity.

## Context

The current repository already contains multiple directions at once: Raspberry Pi tap stations, an Android/mobile path, a two-station wait-time model, dashboards, admin tooling, service configuration, and an extension system. The repo README currently describes FlowState as "a simple, reliable system for tracking wait times at festival harm reduction services using NFC tap stations," while also exposing optional features including mobile app support, substance return confirmation, human error handling, and a modular extension system with 12 built-in extensions. This pack intentionally narrows and clarifies the product direction to a single coherent v1 target. 

## Product definition

**FlowState v1 is a local-network, multi-device checkpoint system for fixed harm reduction service environments.**

It tracks anonymous service episodes as they move through a small number of physical checkpoints using NFC tokens and a shared local backend.

FlowState v1 exists to:

- provide live visibility of service flow
- support operational decision-making during service delivery
- create simple, reliable timing data across checkpoints
- remain usable in chaotic festival or mobile harm reduction environments
- work fully offline on a local network without internet

## Product boundary

FlowState v1 is:

- a shared local service-flow tracker
- a checkpoint-based timing system
- a lightweight operational visibility tool

FlowState v1 is **not**:

- a general platform for all harm reduction data
- a surveillance or identity system
- a cloud SaaS product
- a configurable plugin ecosystem
- a complex sample/result management platform

## Non-negotiable principles

### Harm reduction first
- No personally identifying information is required.
- NFC tokens are not identities.
- The system must not create a surveillance-like feel.
- Participant interaction should remain minimal, safe, and non-intrusive.

### Simplicity over features
- Every core action must be obvious and fast.
- Core usage should require little to no training.
- If a feature adds cognitive load at a checkpoint, it should not be part of v1.

### Local-first and offline-first
- Core operation must not depend on internet access.
- The event deployment must function entirely on a local network.
- Cloud sync and remote hosting are out of scope for v1.

### Failure tolerance
- The system must degrade gracefully when staff miss scans or devices briefly disconnect.
- Recovery should be manual and simple, not highly automated.

## Canonical architecture

### Architecture statement
**FlowState v1 uses a Raspberry Pi as the canonical local backend for each event deployment.**

This is a centralised local event system with distributed checkpoint clients.

### Source of truth
For each deployment, one Raspberry Pi is the source of truth.

The Raspberry Pi is responsible for:
- running the local application server/API
- hosting the canonical local database
- storing all event data
- serving dashboard and admin interfaces
- handling export functions

### Database
- Canonical database lives on the Raspberry Pi.
- SQLite is acceptable and preferred for v1.
- The database persists for the event deployment.
- Client devices must not be treated as independent canonical databases.

### Client devices
Multiple client devices connect to the Raspberry Pi over a local Wi-Fi network.

Client devices are checkpoint devices. They are not standalone systems.

Checkpoint devices may be:
- Android phones or tablets
- dedicated Raspberry Pi tap stations where relevant
- other local clients only if they do not complicate the architecture

Each checkpoint client:
- scans an NFC token
- is assigned to a single stage/checkpoint
- sends stage transitions to the Raspberry Pi
- shows immediate confirmation to staff

### Dashboard
A dashboard reads from the same shared backend and shows live operational state.

The dashboard may run on:
- laptop
- tablet
- TV-connected browser
- another Pi-connected display

### Network model
- Local network only
- Internet not required
- No cloud dependency in core flow
- No assumption of remote database, hosted backend, or browser-only architecture

### Constraint on mobile and PWA assumptions
Do not assume a browser-only or PWA-only architecture for core NFC workflows. If browser-based interfaces exist, they are secondary to the canonical local backend model.

## Core domain model

### Service episode
A **Service Episode** is the main tracked object.

A service episode:
- is anonymous
- is created on first valid entry scan
- represents a participant or group moving through the service
- accumulates timestamps as it moves through checkpoints
- has one current stage at any given time

### NFC token
An NFC token is:
- a physical pointer to a service episode
- not a person
- not a persistent identity across events
- not a long-term account object

The token may be a card, sticker, or other simple NFC medium.

### Station/checkpoint
A station is a physical checkpoint in the service with a dedicated client device.

Each station has:
- `station_id`
- `assigned_stage`
- optional human-readable label

For v1, stations should be treated as **fixed-stage clients**.

## Episode lifecycle

FlowState v1 is based on a small linear stage model.

### Default stage model
1. ENTERED
2. FIRST_CONTACT
3. SAMPLE_LOGGED
4. TESTING
5. RESULT_READY
6. COMPLETED

### Lifecycle rules
- New episode can only be created at an entry-capable station.
- Existing episode can be updated when scanned at a later-stage station.
- Stations should normally represent a fixed assigned stage.
- Avoid branching workflow logic in v1.
- Avoid deeply configurable per-event workflow engines in v1.

## Core behaviours

### 1. Create episode
When a new/unknown NFC token is scanned at an entry-capable station, the system:
- creates a new service episode
- records the token identifier
- records timestamp
- sets current stage to `ENTERED`

### 2. Advance/update episode by checkpoint
When an existing token is scanned at another checkpoint:
- locate the existing episode
- append stage event
- update current stage to that station's assigned stage
- store timestamp
- return immediate confirmation to the client device

### 3. Shared live state
At any time, the system should be able to answer:
- how many active episodes exist
- how many episodes are at each stage
- which episodes appear stalled
- elapsed time since entry
- elapsed time in current stage

### 4. Dashboard visibility
The dashboard should support a minimal live operational view:
- active count
- counts per stage
- elapsed times / simple wait visibility
- stalled or long-running episodes if implemented simply

### 5. Export
Export should be simple and reliable.

Minimum export target:
- CSV

Export should include, where available:
- episode ID
- token ID
- current stage
- timestamps by stage
- total elapsed time
- creation timestamp
- completion timestamp if completed

## Station model

### v1 station design
Use fixed-stage station devices where possible.

Examples:
- Entry station
- First contact station
- Sample logged station
- Testing station
- Result ready station
- Completion station

### Why fixed-stage stations
This reduces:
- cognitive load
- UI complexity
- wrong-stage scans
- training burden
- menu-driven operator mistakes

### What not to build for v1
Do not default to a highly flexible station UI that allows arbitrary stage selection on every device unless there is a specific, documented operational need.

## Minimal UI requirements

### Checkpoint client UI
The checkpoint UI should be extremely simple:
- clearly show station identity
- indicate ready-to-scan state
- show result of last scan
- give immediate success/error feedback
- require minimal taps beyond scanning

### Dashboard UI
The dashboard should prioritise operational usefulness over detail.

Recommended dashboard elements:
- total active episodes
- count per stage
- recent scan activity
- simple elapsed-time indicators

Do not build dense analytics-heavy interfaces for v1.

## Data model (conceptual)

### Episode
- `episode_id`
- `token_uid`
- `created_at`
- `current_stage`
- `is_active`
- `completed_at` (optional)

### Stage event
- `event_id`
- `episode_id`
- `station_id`
- `stage`
- `timestamp`
- `recorded_by_device_id` (optional)

### Station
- `station_id`
- `stage`
- `label`
- `is_entry_capable`
- `is_active`

### Device
- `device_id`
- `device_type`
- `station_id`
- `last_seen_at` (optional)

## Error and recovery behaviour

### Principles
- Do not over-automate error handling in v1.
- Prefer simple manual recovery over complex inference.
- Preserve staff trust in the system.

### Minimum required cases
- unknown token scanned at non-entry station -> clear operator message
- duplicate/repeat scan -> do not crash; handle safely
- missed scan -> allow simple manual stage correction
- disconnected checkpoint client -> clear local message, retry path, or queue action if intentionally supported
- lost token -> no complex relinking required for v1 unless already trivial in codebase

## Explicitly in scope for v1

### Keep / build / preserve
- Raspberry Pi local hub architecture
- local SQLite database
- local API/server
- multi-device checkpoint model
- fixed-stage clients
- NFC scanning at checkpoints
- shared live dashboard
- simple export
- small linear stage model
- simple manual correction if already easy to keep
- clear station configuration

## Explicitly out of scope for v1

The following must not shape the v1 architecture and should be removed, disabled, or deprioritised where practical:

- plugin/extension platform as a core product concept
- deeply configurable workflow engine
- substance accountability workflows as core
- substance return confirmation as core
- complex role/permission systems
- cloud-first or SaaS assumptions
- independent mobile databases with complex sync
- advanced analytics as a primary build goal
- client-facing personalised participant UI
- cross-event tracking or persistent identity
- broad note-taking and general case-management logic

## Refactor intent for current repository

The current repository already contains useful work, but it mixes multiple product identities. The refactor goal is not to discard all prior work. The goal is to consolidate around one coherent architecture and product boundary.

### Refactor priorities
1. Make the Raspberry Pi local hub architecture explicit and dominant.
2. Treat checkpoint devices as stage/station clients.
3. Reduce product identity to service-flow tracking.
4. Simplify or isolate optional/legacy features so they do not distort v1.
5. Prefer deletion, disabling, or quarantine of non-core systems over clever abstraction.

## Implementation guidance for AI coding agent

### General rules
- Do not invent cloud architecture.
- Do not invent multi-master sync.
- Do not convert the product into a standalone Android-first architecture.
- Do not introduce a new plugin system.
- Do not expand configurability unless necessary to support fixed-stage checkpoint assignment.

### Preferred bias
- Prefer simple, explicit code paths.
- Prefer one clear source of truth.
- Prefer deletion over refactoring when safe.
- Prefer hardcoded v1 assumptions over abstract future-proofing.
- Prefer operational reliability over architectural elegance.

## Success criteria

FlowState v1 is successful if:
- multiple checkpoint devices can update shared event state through one local backend
- the dashboard reflects the shared live state accurately enough to be operationally useful
- staff can use checkpoint devices with minimal thought
- the system works without internet
- event exports are simple and reliable
- the product feels smaller, clearer, and more trustworthy than the current mixed-scope version

## Final constraint

If a proposed change makes FlowState feel more like a platform than a tool, it is probably the wrong change for v1.
