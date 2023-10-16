import warnings

from html5lib.constants import DataLossWarning

warnings.simplefilter("ignore", category=DataLossWarning)
