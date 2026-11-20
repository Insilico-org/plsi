"""The thresholds and caps of `plsi bio`. Each floor is the least code accepts; a protocol may freeze a stricter one."""

ALPHA = 0.05  # significance level unless a command is given another
MIN_OVERLAP = 10  # genes shared by discovery and replication before agreement means anything
MIN_CELL = 3  # reports in the drug-event cell before a disproportionality ratio is stable
MIN_EVENTS = 10  # events per survival group before the group carries a comparison
MIN_ORDER_RHO = 0.8  # Spearman between two orderings of the same cells before the order is trusted
SIZE_BIAS_RHO = 0.5  # Spearman of set size with -log10 p above which ranks follow size
SIZE_BIAS_MIN_SETS, SIZE_BIAS_MIN_SPREAD = 10, 2.0  # the check needs this many sets, the largest this many times the smallest
NULL_CALIBRATION = 2.0  # a null flagging more than this many times alpha is not a null
NULL_DRAWS, MIN_NULL_DRAWS, MAX_NULL_DRAWS = 1000, 100, 100_000
MATCH_BINS = 10  # mean-expression bins for a matched null
MIN_STUDIES = 2  # studies a pooled estimate needs
MIN_SET, MAX_SET = 10, 500  # gene-set sizes tested, after the cut to the universe
SURVIVAL_GROUPS = (2, 6)
MAX_METHODS, MAX_RESULTS, MAX_CRITERION = 1200, 12, 400  # a step page: characters of methods, key numbers, criterion chars
MAX_ROWS_SHOWN, MAX_OVERLAP_SHOWN = 50, 25  # rows of a ranked table and genes per set in a command's output
FIGURE_ROWS = 15  # rows a ranked figure draws
MAX_PANELS = 4  # panels of an embedding figure
KO_TOP_RANK = 5  # a knocked-out gene must rank within this many of its own most perturbed genes
DIRECTION_UNIFORM_SHARE, DIRECTION_MIN_GENES = 0.9, 10  # one direction this share of at least this many responders
