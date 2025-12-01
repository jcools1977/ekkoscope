# AN2B Brand Kit

This folder contains the AN2B logo components with the glowing neon effect.

## Installation

1. Copy this entire `brand` folder to your project's `src/components/` directory
2. Add the CSS from `brand-styles.css` to your main stylesheet
3. Make sure you have a `cn` utility function (or use the one below)

## Usage

```tsx
import { LogoFull, LogoMark } from "@/components/brand";

// Full logo with text (bee + "AN2B")
<LogoFull size={32} variant="neon" />       // Glowing cyan
<LogoFull size={32} variant="holographic" /> // Gradient glow  
<LogoFull size={32} variant="flat" />        // No glow, monochrome

// Just the bee icon
<LogoMark size={24} variant="neon" />
```

## Variants

- **neon**: Cyan glow effect with drop shadows
- **holographic**: Gradient colors (cyan → purple → pink) with glow
- **flat**: Simple monochrome, no effects

## Required: cn utility

If you don't have a `cn` function, add this to `@/lib/utils.ts`:

```ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

And install dependencies:
```bash
npm install clsx tailwind-merge
```

## Font

The logo uses `font-heading` class. Make sure you have Space Grotesk or similar:

```css
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@700&display=swap');

.font-heading {
  font-family: 'Space Grotesk', sans-serif;
}
```

## Brand Colors

- Primary Cyan: `#00e5ff`
- Purple: `#7c3aed`  
- Pink: `#f0abfc`
- Blue: `#3b82f6`
