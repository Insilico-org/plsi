<!-- plsi-mothership-consent: 0.7.1 -->
<!-- Draft: have the wording reviewed (data protection, research ethics) before public release; any change bumps the version. -->

# Longevity Mothership: what joining means

The Longevity Mothership is a longevity research initiative run by Insilico Medicine, a company. It pools
deidentified health data from PLSI users who choose to take part, to learn how health states change with age and
which actions shift them. Joining is for science; it is optional, PLSI works the same without it, and you get
nothing in return beyond occasional pooled findings.

**What can be shared** (you pick each one):

- **Your health states:** the values PLSI computed from your records (for example blood markers, and the
  medications and conditions on your list as standard medical codes, a medication with its dose as an amount and
  unit such as 10 mg when PLSI recorded one), dated to the month. A value worked out from your age (your age itself,
  a biological age or its gap to your age, or anything computed from those) is not shared, nor the months since your
  final period, which with your age at menopause would give your age.
- **Your life story:** the health events PLSI recorded from your history (conditions, treatments, medications,
  allergies, lifestyle periods, symptoms) as standard medical codes, a medication with its dose as an amount and
  unit, dated to the year. An event PLSI has no code for is not shared.
- **Your prediction scores:** how well PLSI's predictions matched your later results, only as counts and averages.

**What is never shared:** your name, contact details, addresses, employer, facility names, record or ID numbers,
exact dates, your birth year or age (only a 5-year age band and sex), the documents you uploaded, any words you or your
records used (only codes, numbers and units leave), your goals and preferences, and the records of other people you
added to PLSI.

**How:** PLSI sends one file at most once a week over an encrypted connection to Insilico's relay
(plsi-mothership-relay.pages.dev, run on Cloudflare). The relay holds the file unchanged until the Mothership collects
it, at most one day, and then keeps only the Mothership's receipt (stored or refused, never your data) for seven days
so PLSI can confirm it arrived. Inside, the file carries a random contributor code made on your computer instead of
your identity; it is not the install code PLSI uses to connect, and the relay never passes the install code on. Like
any website, the relay sees your computer's internet address when PLSI connects; it keeps no logs of it, and the file
itself never contains it. Insilico stores what arrives in its corporate Google Drive, in a shared drive only its data
stewards can open. To join, you open the relay's join page once and give PLSI the one-time code it shows. PLSI keeps a
copy of everything it sent; ask "what have I shared?" any time.

**Your choices:** stop sharing any time ("stop sharing with the Mothership"), or ask the Mothership to delete
everything it received under your contributor code. A deletion request carries a secret only your PLSI holds, which
proves it comes from you; the Mothership records a deletion receipt. Deidentified data can never be made fully anonymous;
joining means accepting a small risk that someone could link it back to you.
