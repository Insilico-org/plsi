"""Every number the journal is tuned by: the thresholds behind its checks, display limits and file caps."""

from __future__ import annotations

from plsi.vocab.journal import WellRole

MiB = 1024 * 1024

CT_SPREAD = 0.5  # cycles between technical replicates before they are flagged
CT_LATE = 35.0  # a mean Ct above this is near the detection limit
STANDARD_R2_MIN = 0.98  # a standard curve below this r² is flagged
CI_BLANK_MAX = 0.1  # a blank xCELLigence well above this cell index holds cells or debris
BAND_TOLERANCE = 0.05  # a genotyping band matches an allele within this share of its size
WEIGHT_LOSS_PCT = 15.0  # an animal this far below its first weight is flagged
EXPECTED_MIN = 5  # chi-square expected counts below this make the p rough
COUNT_TOLERANCE = 0.01  # share by which an exported flow count may differ from the file's
COFACTOR = 150.0  # arcsinh cofactor of the fluorescence axes, unless an entry sets its own

FLOW_GRID = 256  # density grid per side that colours the dots
FLOW_DOTS = 12000  # events drawn per plot
FLOW_HIST_BINS = 160
FLOW_SAMPLES = 24  # FCS files drawn per entry

DAYS_AHEAD = 7  # how far `journal today` looks ahead
FILE_BYTES = 25 * MiB  # a file kept with an entry
FCS_BYTES = 500 * MiB  # an FCS file kept with an entry
PAGE_RELOAD_SECONDS = 120
PAGE_IMAGE_BYTES = 4 * MiB  # a picture embedded in the page
PAGE_IMAGES_BYTES = 40 * MiB  # all pictures embedded in the page
MAP_CUTTERS = 14  # unique cutters labelled on a plasmid map

# a well or group named like this is taken as a control when no role is given (letters and digits only, lower case)
ROLE_NAMES = {"ntc": WellRole.NTC, "notemplate": WellRole.NTC, "nrt": WellRole.NO_RT, "nort": WellRole.NO_RT,
              "minusrt": WellRole.NO_RT, "blank": WellRole.BLANK, "medium": WellRole.BLANK, "mediumonly": WellRole.BLANK,
              "background": WellRole.BLANK, "nocells": WellRole.BLANK}

PAGE = {"weight_loss_pct": WEIGHT_LOSS_PCT, "map_cutters": MAP_CUTTERS}  # what the page draws by
