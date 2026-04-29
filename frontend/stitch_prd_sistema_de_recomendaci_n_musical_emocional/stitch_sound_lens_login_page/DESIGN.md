# Design System Strategy: The Sonic Noir Editorial

This document outlines the visual and behavioral logic for the design system. This is not a standard utility-first framework; it is a high-end editorial language designed to evoke the deep, immersive atmosphere of a late-night listening session. It prioritizes tonal depth over structural lines and movement over static grids.

## 1. Overview & Creative North Star
**Creative North Star: "The Digital Curator"**

The objective of this design system is to move away from the "app-like" feel and toward a "gallery-like" experience. We achieve this through:
*   **Intentional Asymmetry:** Breaking the expected 12-column rigidity to create visual tension and focal points.
*   **Cinematic Depth:** Using a "void-out" philosophy where elements emerge from darkness rather than being placed on top of it.
*   **High-Contrast Scale:** Dramatically oversized typography for headlines (`display-lg`) paired with meticulous, understated labels to create an expensive, editorial feel.

## 2. Colors: Tonal Immersion
The palette is built on a foundation of "Deep Ink" and "Electric Violet." It is designed to be experienced in low-light environments, reducing eye strain while maximizing the "pop" of key musical assets.

### The "No-Line" Rule
**Borders are a failure of hierarchy.** Within this system, you are prohibited from using 1px solid lines to separate sections or cards. Boundaries must be defined solely through:
1.  **Tonal Shifts:** Placing a `surface_container_low` section against a `background` base.
2.  **Negative Space:** Using the spacing scale to create clear mental groupings.
3.  **Shadow Depth:** Allowing an element to "lift" away via ambient shadows rather than a containing stroke.

### Surface Hierarchy & Nesting
Treat the UI as a physical stack of semi-translucent materials.
*   **Base Layer:** `background` (#100c1a) — The infinite void.
*   **Interaction Layer:** `surface_container` (#1c1729) — Standard cards and groupings.
*   **Active/Elevated Layer:** `surface_bright` (#2f2940) — Active states or high-priority modals.

### The "Glass & Gradient" Rule
To avoid a flat, "Material-only" look, use **Glassmorphism** for floating UI elements (like music players or navigation bars).
*   **Recipe:** `surface_variant` at 60% opacity + `backdrop-blur: 20px`.
*   **Signature Gradients:** Use a linear gradient from `primary` (#b1a1ff) to `primary_dim` (#7658f8) for high-impact CTAs to provide a sense of luminous energy.

## 3. Typography: The Editorial Voice
We utilize two distinct typefaces to balance character with readability.

*   **Manrope (The Display Voice):** Used for `display` and `headline` tiers. Manrope’s geometric but open nature provides a modern, premium feel. Use it for artist names, album titles, and hero statements.
*   **Inter (The Functional Voice):** Used for `title`, `body`, and `label` tiers. Inter provides the technical precision needed for tracklists, metadata, and settings.

**Hierarchy Strategy:** Always maintain at least a 2:1 ratio between your `display-lg` (3.5rem) and `title-lg` (1.375rem). The contrast in size is what creates the "SoundWave" editorial signature.

## 4. Elevation & Depth
In a dark UI, traditional shadows are often invisible. We use **Tonal Layering** and **Ambient Glows**.

*   **The Layering Principle:** Stacking order should follow `surface_container_lowest` (deepest) to `surface_container_highest` (closest to user).
*   **Ambient Shadows:** For floating elements, use a shadow with a 32px to 64px blur, set to 6% opacity, using the `on_surface` (#ede4fa) color. This creates a "glow" effect that feels more natural in a dark theme than a black shadow.
*   **The "Ghost Border" Fallback:** If a border is required for accessibility (e.g., in high-contrast mode), use `outline_variant` (#4a4556) at 15% opacity. It should be felt, not seen.

## 5. Components

### Buttons
*   **Primary:** Gradient fill (`primary` to `primary_dim`), `full` roundedness, `label-md` uppercase typography.
*   **Secondary:** Ghost style. No fill, `outline` border at 20% opacity. High-contrast `on_surface` text.
*   **Tertiary:** No border, no fill. Underlined only on hover.

### Input Fields
*   **Base:** `surface_container_high` background.
*   **Border:** Never use a default border. Use a 2px bottom-stroke of `primary` only when the field is `:focus`.
*   **States:** Error states use `error` (#ff6e84) for text and a 5% `error_container` tint for the field background.

### Cards & Lists
*   **Rule:** Forbid divider lines.
*   **Structure:** Use vertical rhythm. A tracklist should use `surface_container_low` for the even rows and `transparent` for odd rows to create "Zebra-striping" without harsh lines.
*   **Radius:** Standard cards use `lg` (0.5rem); immersive hero containers use `xl` (0.75rem).

### The "Pulse" Player (Custom Component)
A signature component for this system. A floating bar using the Glassmorphism recipe. The progress bar should use the `primary` to `primary_dim` gradient, with a subtle `primary_fixed_dim` outer glow to simulate a light-pipe.

## 6. Do's and Don'ts

### Do:
*   **Do** use extreme white space. Let the dark background "breathe."
*   **Do** use `on_surface_variant` (#afa8bc) for secondary metadata to keep the visual hierarchy clear.
*   **Do** apply a subtle `0.25rem` radius to imagery to soften the overall aesthetic.

### Don't:
*   **Don't** use pure white (#FFFFFF) for text. Always use `on_background` (#ede4fa) to prevent "halving" (visual bleeding) on dark backgrounds.
*   **Don't** use 100% opaque borders. They break the immersive, deep-space feel of the "Sonic Noir" aesthetic.
*   **Don't** use standard "drop shadows." Use the ambient glow method described in Section 4.