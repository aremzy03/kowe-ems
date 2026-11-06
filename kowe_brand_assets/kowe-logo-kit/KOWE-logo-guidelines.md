# Kowe: Logo Guidelines

## 1. The logo
- **Idea**: Kowe comes from the Yoruba *Kọ́ wé*, "to write and record". The mark is the subdotted **ọ** from *Kọwe*: a ring with a dot below it, set on an indigo tile that doubles as the app icon. The same subdot repeats under the "o" in the wordmark.
- **Versions**: horizontal (primary) · stacked · symbol only · wordmark only
- **Files**: `svg/` for everything on screens and in print · `png/` for quick use · `web/` for the favicon and app icons

## 2. Clear space
Keep a clear zone of **½ the tile height** (the indigo tile is the unit) on all sides of every version. The zone scales with the logo, so never use a fixed distance.

## 3. Minimum size
| Version | Screen | Print |
|---|---|---|
| Horizontal | 96 px wide | 25 mm wide |
| Stacked | 64 px wide | 18 mm wide |
| Symbol | 24 px (below that, use `kowe-symbol-small.svg` or `favicon.svg`) | 8 mm |

Use `kowe-symbol-small.svg` for anything under 24 px. It has a thicker ring and a larger dot so the two stay separate.

## 4. Colour
| Name | HEX | RGB | CMYK (approx.) | Use |
|---|---|---|---|---|
| Kowe Indigo | #5B3DE8 | 91, 61, 232 | 61 / 74 / 0 / 9 | Tile, one-colour brand version |
| Kowe Coral | #FF7A45 | 255, 122, 69 | 0 / 52 / 73 / 0 | Subdots only |
| Ink | #211F26 | 33, 31, 38 | 13 / 18 / 0 / 85 | Wordmark |
| Paper | #FBF6EC | 251, 246, 236 | 0 / 2 / 6 / 2 | Reversed tile and wordmark |

CMYK values are straight conversions from RGB. Match print colours against a physical swatch at the printer; Pantone matches have not been chosen.

**Approved pairs**
- Full colour on white or Paper.
- Reversed version (`*-reversed.svg`) on Ink or Indigo.
- One-colour black or white on photos, placed on a calm area.
- Indigo one-colour (`*-mono-5b3de8.svg`) on white or Paper.

**Contrast note**: Coral on Indigo is about 2.5:1 and Coral on Paper about 2.4:1. The subdot is a brand detail rather than text, and logos are exempt from WCAG contrast rules, but never rely on the dot alone to carry information.

## 5. Typography
- The wordmark is **drawn artwork**: custom outlined letters with no font dependency. Never retype it.
- Product UI follows the Paper Brutalism system: Space Grotesk for headings, Inter for body, JetBrains Mono for codes and IDs. All three are open-licence fonts.

## 6. Don'ts
- Don't stretch, squash or rotate the logo.
- Don't recolour outside the palette, and don't make the subdot any other colour.
- Don't place the full-colour logo on Coral. The dot disappears.
- Don't add shadows, outlines, gradients or effects.
- Don't rearrange or resize the parts of a lockup.
- Don't use the large symbol file below 24 px; use the small-size cut.
- Don't place on busy photos without a calm area or a one-colour version.
- Don't recreate the wordmark by typing "kowe" in a font.
- Don't drop the subdot from the wordmark. Without it the name reads as "kowe", not "kọwe".

## 7. File guide
| Need | File |
|---|---|
| Website header, documents | `svg/kowe-horizontal.svg` |
| Dark backgrounds | `svg/kowe-horizontal-reversed.svg` |
| Square spaces, avatars | `svg/kowe-symbol.svg` |
| Tight vertical spaces | `svg/kowe-stacked.svg` |
| Stamps, embossing, one-colour print | `svg/kowe-*-black.svg` / `-white.svg` / `-mono-5b3de8.svg` |
| Browser tab | `web/favicon.svg`, `web/favicon.ico` |
| Home-screen icons | `web/apple-touch-icon.png`, `web/icon-192.png`, `web/icon-512.png`, `web/maskable-512.png` |

## 8. Using it in the Next.js app
- Put `favicon.ico`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png`, `maskable-512.png` and `site.webmanifest` in `public/`, and add the lines from `web/head-snippet.html` to the root layout's `<head>`.
- In the App Router you can instead drop `favicon.ico` and `apple-touch-icon.png` into `app/` and let Next.js generate the tags.
- Use the SVG files directly (`<img src>` or an SVG component) so the logo stays sharp at every density.
- Per the "intensity dial" in the design system: use the horizontal logo large on auth and onboarding screens, and the symbol only in dense dashboards and tables.

## 9. Handover notes
- **Construction**: circles on a 256-unit grid. Tile 224 with a 56 corner radius, ring outer radius 66 and inner 36, subdot radius 16. The wordmark is built from straight segments and arcs.
- **One-colour versions** use real cut-outs (`fill-rule="evenodd"`), so the ring and dot are holes, not white shapes. They work on any background and in vinyl or embroidery workflows.
- **Not done**: the reversed wordmark is not optically thinned, and no PDF, EPS or AI masters were produced. A designer can export those from the SVGs.
- **Trademark**: no clearance has been done. Search the CAC and the trademark registry for "Kowe" before committing to it.
- **Mockups**: the presentation board uses placeholder names and emails (for example "Alex Morgan"). They are not real contacts.
