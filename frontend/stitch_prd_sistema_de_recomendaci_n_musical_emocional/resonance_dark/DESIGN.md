# Design System Strategy: The Sound Lens

## 1. Overview & Creative North Star
**Creative North Star: "The Synesthetic Stage"**
This design system moves beyond the utility of a music player into the realm of an immersive, atmospheric experience. We are not building a library; we are building a stage where the interface recedes to let the music’s "mood" dictate the environment. 

The aesthetic is driven by **Atmospheric Depth**. By utilizing high-contrast typography scales and intentional asymmetry, we create an editorial layout that feels curated rather than generated. We break the standard "box-in-a-box" grid by overlapping glass layers, letting album art bleed into the UI, and using vibrant mood-based accents to shift the entire emotional state of the application.

---

## 2. Colors: Emotional Spectrum
The color palette is anchored in a deep, nocturnal foundation (`surface: #0e0e11`) to ensure that the accent colors—our emotional triggers—feel luminous and "electric."

### Mood-Based Accents
- **Electric Orange (Animado):** Use `primary` (#ff9157) and `primary_container` (#ff7a2c) for high-energy tracks. This color should drive the UI when the BPM is high.
- **Deep Teal (Neutro):** Use `secondary` (#89e9f6) and `secondary_container` (#006972) for focus, ambient, or balanced states.
- **Soft Indigo (Triste):** Use `tertiary` (#aebaff) and `tertiary_container` (#9facf4) for melancholic or down-tempo experiences.

### The "No-Line" Rule
**Explicit Instruction:** Do not use 1px solid borders to section off content. 
Boundaries are defined strictly through background shifts. A `surface_container_low` (#131316) section should sit against the `surface` (#0e0e11) background to create distinction. High-end design is felt through tonal transitions, not drawn with lines.

### Glass & Gradient Strategy
To achieve a "Liquid UI" feel, use **Glassmorphism** for floating players and navigation bars. 
- **Glass Token:** Use `surface_variant` at 60% opacity with a `20px` to `40px` backdrop-blur. 
- **Signature Gradients:** For CTAs and Audio Metrics, use a linear gradient transitioning from `primary` (#ff9157) to `primary_dim` (#ff7520) at a 135-degree angle. This adds "soul" and a sense of light-emission to the interactive elements.

---

## 3. Typography: Editorial Authority
We use **Inter** for its mathematical precision and readability. The scale is intentionally dramatic to create a sense of hierarchy that mirrors a high-end magazine.

- **Display Scales (`display-lg` to `display-sm`):** Reserved for Artist names or Playback timers. Use `display-lg` (3.5rem) to dominate the screen, creating a bold, unapologetic focal point.
- **Headline & Title:** Use `headline-lg` (2rem) for playlist titles. These should have tight letter-spacing (-0.02em) to feel premium.
- **Body & Labels:** Use `body-md` (0.875rem) for metadata (album info, durations). Use `on_surface_variant` (#acaaae) to de-prioritize this information relative to the music title.

---

## 4. Elevation & Depth: Tonal Layering
In this system, "Up" is "Brighter." We do not use traditional drop shadows to indicate height; we use **Surface Nesting**.

### The Layering Principle
- **Base:** `surface` (#0e0e11).
- **Secondary Content:** `surface_container_low` (#131316).
- **Interactive Cards:** `surface_container` (#19191d).
- **Floating Modals/Overlays:** `surface_bright` (#2c2c30) with a Glassmorphism blur.

### Ambient Shadows
If a floating element (like a FAB) requires a shadow, it must be a "Tinted Glow." Instead of black, use a 10% opacity version of the `primary` color with a `32px` blur and `0px` offset. This mimics the light of the screen reflecting off the "glass" surface.

### Ghost Borders
If accessibility requires a container boundary, use a **Ghost Border**: `outline_variant` (#48474b) at 15% opacity. It should be felt, not seen.

---

## 5. Components: The Fluid Set

### The Playback Bar (Glass Component)
- **Style:** `surface_variant` at 40% opacity, `xl` (1.5rem) corner radius, 24px backdrop-blur.
- **Interaction:** Smooth 300ms cubic-bezier transitions when expanding to full-screen.

### Progress & Metric Visualizations
- **Audio Metrics:** Use `secondary` (#89e9f6) for waveform visualizations. Avoid flat bars; use rounded caps (`full` roundedness) and varying heights to indicate frequency data.
- **The Seek Bar:** A `primary` (#ff9157) track on a `surface_container_highest` (#25252a) background. The "thumb" should only appear on hover to keep the UI clean.

### Buttons & Chips
- **Primary Action:** `primary` background with `on_primary` (#531e00) text. Corner radius: `full`.
- **Mood Chips:** Selection chips that use the `tertiary`, `secondary`, or `primary` tokens based on the selected mood. When inactive, they should use `surface_container_high` (#1f1f23) with no border.

### Cards & Lists
- **Rule:** Forbid divider lines. Use `spacing.8` (2rem) of vertical white space to separate list items or subtle background shifts (`surface_container_low`) on hover.
- **Visuals:** Album art should use the `lg` (1rem) roundedness scale.

---

## 6. Do’s and Don’ts

### Do
- **Use Asymmetry:** Place the "Now Playing" text off-center or overlapping an image to create an editorial feel.
- **Use Motion:** All state changes (e.g., switching from 'Animado' to 'Triste') must include a 500ms cross-fade of the accent colors.
- **Prioritize Negative Space:** Let the dark `surface` breathe. High-end design is defined by what you *don't* put on the screen.

### Don’t
- **No Pure White:** Never use #FFFFFF. Use `on_surface` (#f0edf1) to avoid harsh eye strain in dark mode.
- **No Default Shadows:** Avoid standard CSS `box-shadow: 0 2px 4px rgba(0,0,0,0.5)`. It looks cheap and "bootstrap." Use Tonal Layering.
- **No Hard Grids:** Avoid strictly boxing everything. Let elements like audio waves or artist imagery break the container boundaries to create "Visual Soul."