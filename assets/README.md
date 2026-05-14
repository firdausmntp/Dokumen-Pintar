# <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg> Branding Assets

<a href="../README.md">Home</a>

---

## Logo

- `icon.svg` — primary logo, 256x256 viewBox.
- `icon-small.svg` — compact mark, 64x64 viewBox (use in toolbar / tray).

### Design Concept

- **Navy gradient background** (`#1e3a5f` to `#0f2440`) — professional, clean, non-AI-slop.
- **Stacked documents** — represents multi-format, multi-root capability.
- **Amber checkmark accent** — signals reliability and successful operations.
- **"FSU" text** — branding mark at the bottom of the logo.

### Convert to PNG

PowerShell + ImageMagick:

```powershell
magick icon.svg -resize 1024x1024 icon-1024.png
magick icon.svg -resize 512x512 icon-512.png
magick icon.svg -resize 256x256 icon-256.png
magick icon.svg -resize 128x128 icon-128.png
magick icon-small.svg -resize 64x64 icon-64.png
magick icon-small.svg -resize 32x32 icon-32.png
magick icon-small.svg -resize 16x16 icon-16.png
```

ICO bundle:

```powershell
magick icon-16.png icon-32.png icon-64.png icon-256.png icon.ico
```

### Usage

- **README hero** — `icon.svg` centered, max width 140px.
- **MCP client manifest** — `icon-small.svg` (or `icon-256.png` for raster).
- **Tray / favicon** — `icon-16.png` / `icon-32.png`.
