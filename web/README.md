# PlayerProfile.astro — web-component port

Astro port of the player-profile card, staged here for asiaprogolf.com (Astro).
**Do not hand-edit `PlayerProfile.astro`** — it is GENERATED from the canonical
renderer so the design can never fork:

```bash
python3 ../reference/render_profile.py --emit-astro PlayerProfile.astro
```

The `<style>` block is `CARD_CSS` verbatim from `reference/render_profile.py`;
the theme (brand base + per-tour accent) is injected as inline CSS variables on
the card. Edit the design in `render_profile.py`, then regenerate.

## Usage

Copy `PlayerProfile.astro` into the site (e.g. `src/components/`), then:

```astro
---
import PlayerProfile from "../components/PlayerProfile.astro";
import player from "../data/sample-player.json";   // same JSON contract as the CLI
---
<PlayerProfile player={player} brand="36media" />
```

Props: `player` (the per-player record) and `brand` (`"36media"` default | `"tgh"`).
Fonts: the site provides Inter (the component does not embed fonts). Verified with
`astro build` (Astro 4.x).
