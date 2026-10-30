---
name: arrow
description: Use as PLSI when the user tells their life story or health history in free form, asks PLSI to continue it, or wants to see their health past and likely future on one picture - the life arrow (key events behind, recorded state now, predicted events and risks ahead).
---

# Life arrow

Follow persona.md norms and `shared/team`. Owner: **PLSI**.
One exception to the persona.md style: the story in step 4 is vivid narrative prose, not bullets. Data Processor
(`processor/history`), Nostradamus (`nostradamus/risks`) and Visualizer (`visualizer/dashboard`, `visualizer/charts`)
do their parts in their own skills; PLSI relays on one thread, writes the story (step 4) and shows the result.

The life arrow is one timeline: meaningful health events in the past, the recorded state now, and predicted events
ahead with their windows and probabilities. Every point on it comes from the log, a projection, a recorded prediction
or a verified source; the story is written around those points, never the other way round.

## When to use

- The user shares a life story, a health history or "what happened to me so far", whether or not they ask to
  continue it, and also when part of it is already recorded (the setup interview): every step runs, the picture and
  the "Work on" card included.
- The user asks "where am I heading", "what are my main risks", or to see their history as a picture.
- After `reviewer/review` scored predictions, to redraw the arrow.

## Steps

1. **Save** the story unopened to `<PLSI_HOME>/inbox/` (a story typed in chat: save the text as a file).

2. **Past and present (Data Processor).** Send Data Processor a `request` (skill `processor/history`, the file in
   `files`). It records the events after ONE record `question` (with every assumed date) and returns the past events
   and the new `states`. Then go on to step 3 at once, also when the user only told the story: never ask whether to
   continue. A story whose facts are already on file records only the new items (or nothing) and still goes on to
   step 3.

3. **Future (Nostradamus).** Send Nostradamus a `request` (skill `nostradamus/risks`) with the `states` and past
   events in `summary`. It returns 3-7 future events with windows, sourced probabilities or levels, and the top
   modifiable risk.

4. **PLSI:** continue the story. Write it vividly, in the second person, in short chapters along the arrow (the past in two or
   three lines, then "Now", then one chapter per stretch of the future). Name each predicted event in **bold** with
   its window and probability as on the arrow. Write the likely course if nothing changes. If plans exist, add a
   second course for the adopted plan, using only its recorded predictions (`nostradamus/trajectory` gives both courses).
   At most about 200 words, in the plain words of `orchestrator/conduct` step 7: everyday names for events ("type 2
   diabetes", "high blood pressure", "heart disease"), no thresholds, codes or study jargon ("incident", "age-band",
   "absolute number"); the basis of each number goes in the HTML report.

5. **Draw (Visualizer).** Send Visualizer a `request` (skill `visualizer/dashboard`, scope "life arrow", work folder
   `<PLSI_HOME>/work/<thread>/`) with the past events and states from step 2, the future events from step 3 (each with
   its window, level, probability, basis and source link) and the story from step 4. Visualizer builds `arrow.json`
   (a `timeline` block and a `markdown` block "Your story, continued"), renders the HTML report and draws the arrow
   (`visualizer/charts`, Composition, Life arrow layout), and returns both files.

6. **PLSI:** show it. Check that the image holds every event from steps 2-3 and nothing else (a gap or an extra
   point goes back to Visualizer once), then send it with the HTML report attached. End with one question card naming the top risk in plain words ("Weight and blood pressure are what you
   could change most. Work on them?"): "Make a plan to lower it" hands off to `nostradamus/plan`; "Get the missing
   tests first" turns the matching gaps into measurement requests; "Not now".

## Rules

- No event on the arrow without a source: a recorded observation, a projection, a recorded prediction or a verified
  reference. Probabilities are never estimated by hand.
- The story is model-derived; it never changes the log, plans or predictions. New facts the user adds while reading go
  through step 2.
- Name no intervention or medication as a cure in the story; changes of course come only from plans that passed
  screening.
- Redraw after new results or scored predictions; past arrows stay as earlier reports.
