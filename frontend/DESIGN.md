# hhPulse frontend design system

## Product and audience

hhPulse is a private analytical workstation for one person who studies the
Russian labour market every day. The interface must answer three questions
without making the user decode the crawler internals:

1. Did today's observation finish and can its data be trusted?
2. Where is competition changing across roles and experience strata?
3. What exactly changed in vacancies, resumes and the facets returned by HH?

## Visual tokens

### Colour

- `Archive` `#F4F7FC`: cool paper-like canvas for long analytical sessions.
- `Ink` `#18233B`: primary text and strong axes.
- `Signal blue` `#1E5FD2`: selected data, active controls and the primary series.
- `Ice` `#DCE8F8`: selection surfaces and quiet data regions.
- `Reliable green` `#08785B`: completed observations and positive availability.
- `Fault red` `#C84256`: parser failures and genuinely blocking states only.

Colour is semantic. Blue means a user's current analytical focus; green and
red are not decorative accents.

### Type

- **IBM Plex Sans** is the interface face. Its shapes stay readable in dense
  tables and it has a technical character without looking like a developer
  console.
- **IBM Plex Sans Condensed** is reserved for dates, large measures, chart
  labels and narrow status columns. It gives the product the feel of a serious
  statistical bulletin without copying a newspaper layout.

Body copy is capped at roughly 72 characters per line. Labels use sentence
case; no tracked all-caps eyebrows.

### Layout

Desktop uses a stable navigation rail, a compact status strip and one broad
analytical canvas. Controls belong next to the chart they change. A context
panel appears only for an active job, warning or comparison.

```text
┌──────────────┬─────────────────────────────────────────────────────┐
│ hhPulse      │ Current day · source state · last publication      │
│              ├─────────────────────────────────────────────────────┤
│ Overview     │                                                     │
│ Compare      │           primary analytical canvas                │
│ Snapshot     │        chart / timeline / dense table               │
│ Collection   │                                                     │
│ Alerts       ├─────────────────────────────────────────────────────┤
│ Settings     │ controls that directly affect the canvas            │
└──────────────┴─────────────────────────────────────────────────────┘
```

Mobile turns the rail into a bottom navigation bar, keeps the current-day
status at the top and makes comparison controls a modal sheet.

Alignment is left-first. Numeric table columns align on the right. Charts and
their legends share one vertical datum so the eye can move between them.

## Characteristic element

The memorable element is the **market tape**: one continuous time axis that
shows published days, honest gaps, the current in-progress day and parser
breaks. It is both navigation and data-quality context. The rest of the UI is
deliberately restrained.

## Interaction principles

- Every chart has a table equivalent and an explicit unit.
- Normalisation modes say exactly what they do: absolute, index 100, change %.
- Empty and failed states tell the user what action is possible.
- Destructive or network-changing actions require confirmation.
- Crawler details appear where they explain a state, not as permanent noise.
- Animation only explains state changes; reduced-motion users receive none.

## Generic-design review

The first draft risked becoming a dashboard made of identical metric cards.
That pattern was removed. The overview is organised around the market tape and
one dominant trend canvas; compact measures sit in a ruled statistical strip.
Decorative gradients, generic hero copy, monospace metadata, excessive rounded
containers and hover motion were also rejected because none of them expresses
labour-market analysis. Rounded shapes remain only for interactive controls and
status pills where they communicate affordance or state.

