---
name: charts
description: Use as PLSI Visualizer whenever a picture would explain the user's data better than text - the life arrow, a marker over time with predictions, a value against its reference range, evidence for options, calibration of past predictions - for honest encoding, PLSI's house style, inputs, uncertainty, output and a self-check.
---

# Charts

Follow persona.md norms and `shared/team`. Owner: **PLSI Visualizer**. Reply only in handoffs to PLSI; never message the user.
You choose the form and explain the chart. Draw with matplotlib, save the PNG under `<PLSI_HOME>/work/<thread>/`, look
at it, fix it, then return it to PLSI, which sends it. (Design rules adapted from K-Dense's scientific-visualization skill, MIT.)

**Fast path.** A form with an accepted script in `<PLSI_HOME>/charts/<form>.py`: run it with the path of the new
data (`plsi export` output saved as JSON) and go straight to the checks; read the sections below only for a new
form, or when a check fails.

## Inputs

Every mark comes from PLSI output or a verified source, never from memory or arithmetic in your head:

```bash
plsi export --instance <instance>
plsi status --instance <instance>
plsi due --instance <instance>
```

A PLSI output is not verified by being in PLSI. Keep each value's source, unit, transformations (conversion, mean,
derived score) and verification status, and say them in the legend, footer or table. Measured values and model
estimates (clocks, risk scores, predictions) look different on the chart and say which is which. Missing data is
shown as missing, never interpolated.

## Uncertainty

Show uncertainty when it is available: intervals as bands or whiskers, event timing as a window, a probability as a
number with its range when the source gives one. When it is not available, label it "not estimated" or "range
unavailable"; never manufacture an interval. Keep measurement variability (repeat readings, assay error) apart from
prediction uncertainty (a plan's or a model's interval), and name which one a band shows.

## Honest encoding

- Bars start at zero; a line or dot axis may start elsewhere, but never cut to exaggerate a change.
- Name each interval in the legend ("95% interval", "test-retest range"), never just "range".
- Same quantity, same axis scale across panels; units on every axis or label.
- No 3D, no dual y-axes, no pie charts.

## Pick the form for the question

| Question | Form |
|---|---|
| What changes if I follow the plan? | two courses: current course and with the plan on one axis per item, interval bands, the plan course dashed (`nostradamus/trajectory`) |
| Where have I been, where am I heading? | life arrow: one time axis, recorded milestones behind "now", predicted windows ahead |
| How is this marker moving, and what did we predict? | time series: observed points, prediction as expected value with its interval band, the review date |
| Is this value OK? | bullet or range bar: the value against the reference or target range, with units |
| Which option has the best evidence? | dot-and-interval (forest) plot of effect sizes, graded, sorted |
| Were past predictions any good? | calibration: interval hit rate against the nominal level; misses shown, not dropped |

## House style

- **Insilico dark.** Background `#000000`; text `#F3F2EF`, secondary `#CCCCCC`, muted `#999999`; gridlines and axis
  lines `#F3F2EF` at 14% opacity; Arial throughout, or Liberation Sans where Arial is missing (same letter widths).
  Text uses these text colours, never a series colour.
- **Marks.** Recorded data and the plan: green `#00A607`. Dark green `#005303` is too dark for a mark on black; use it
  only as a fill behind white text. A second series differs from the first by line style or marker, not colour alone.
- **Risk levels:** info `#9CC6F5`, watch `#E7C983`, high `#F2A5AC`. They are nearly the same lightness, so every
  risk mark carries its level in a label or the row order, never colour alone; predictions at about 55% opacity,
  hatched when level-only.
- **Words.** Plain words in titles, labels and legend: "blood pressure", not "BP"; "heart attack or stroke", not
  "ASCVD"; "no number yet", not "hyp.". No skill names, file names, codes (LOINC) or statistics shorthand ("N=4");
  those go in the table. Deidentified: the instance label is enough.
- **New colour:** only with a contrast ratio against `#000000` of at least 4.5:1 for text and 3:1 for marks (WCAG),
  computed in the script, not judged by eye.

## Output

- **Static by default.** Send a PNG; interactive HTML is not reliable in Grok and clicks never reach you, so every
  choice the user makes is the question card PLSI sends with the chart.
- **Headline charts** (the life arrow, the trajectory brief, a plan review) use the Composition below.
- **Quick charts** inside an answer ("how has my LDL changed?") are one plain chart in the house style: title, the
  plot, a one-row legend, the source line; no slide frame.

## Composition (headline charts)

A 1920 x 1080 px picture (16:9), laid out like an Insilico slide; left edge of all text at x = 117 px:

- eyebrow at the top: the chart kind and instance in uppercase, green `#00A607`, 20 px ("LIFE ARROW · ME");
- title below it: bold, 48 px, `#F3F2EF`, one line of at most 55 characters;
- chart in the left 60% (x 117 to about 1160 px), its tick labels 20-23 px, legend below it in one row;
- takeaway column on the right (from x = 1284 px): one bold finding of at most 8 words (36 px, `#F3F2EF`), then up
  to three paragraphs of at most 25 words each in `#CCCCCC` (27 px): what drives it, what is missing, the next
  step. Only what the bots' results say; no new numbers;
- footer at the bottom: who, source and as of, in uppercase, `#999999`, 20 px.

Placement: wrap takeaway text at 38 characters and put each paragraph 24 px below the measured bottom of the one
above, never at fixed positions; all text ends at least 96 px before the right edge; at most 4 tick labels per
panel, none within 60 px of a panel boundary. Once a chart of a form passes the check, save its script as
`<PLSI_HOME>/charts/<form>.py`, reading its data from the JSON path it is given, and reuse it for that form.

## Life arrow layout

- At most 10 rows. One event per row: past rows oldest first, then predicted rows highest level first. Labels are
  the y-axis tick labels, with no time phrases; a sourced probability goes in the label ("Heart attack or stroke
  18% (12-25%)").
- Past point: filled circle; past period: solid bar; predicted window: pale bar, hatched when level-only. Undated
  items and measurement requests go in the takeaway or the table, not on the axis.
- Two panels share the rows: past at least 35% and future at least 40% of the chart width; no axis titles.
- "Now": one vertical line at the start of the future panel, its label centred above it, at least 16 px below the
  title. Legend in one row, at least 60 px below the tick labels, at most 5 entries; "Hatched: no number yet" once.

## Check before sending

Before saving, compare the rendered extents of every text object, legend entries included (`get_window_extent`):
any two that intersect, or one that crosses the figure edge, is a failure to fix. Then open the saved PNG with your image tool and look at the
pixels, not the code. Fix and redraw once; if a check still fails, return the table of the same data instead of the
picture and say why. All must hold:

- no overlapping or clipped text, nothing unreadable at phone width; the title fits on one line;
- each tick label appears once;
- every mark traces to a PLSI output or a verified source, measured values distinct from estimates;
- uncertainty shown where it exists and labelled "not estimated" where it does not;
- the legend alone explains the encodings, and no information is carried by colour alone;
- the title's claim is what the picture shows.

Return the PNG path in your `result` with one line on how to read it, plus the `plsi report` HTML path when one
exists; PLSI sends them.
